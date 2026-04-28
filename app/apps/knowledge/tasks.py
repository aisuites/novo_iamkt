"""
Celery tasks do app knowledge.

Pipeline de processamento de brandguide em 3 tasks coordenadas:
    setup_brandguide_task          -> descobre total de paginas, dispara chord
    convert_pages_batch_task (xN)  -> converte um lote de paginas em paralelo
    finalize_brandguide_task       -> callback do chord, marca como completed

Todas rodam na fila dedicada 'brandguide' (worker separado) para nao bloquear
outros workers (geracao de posts, pautas, etc).
"""

import io
import logging
from typing import Dict, List, Optional

from celery import chord, shared_task
from django.conf import settings
from django.utils import timezone

from apps.core.services import S3Service
from apps.knowledge.models import BrandguidePage, BrandguideUpload

logger = logging.getLogger(__name__)


# ============================================================
# ENTRY POINT - setup
# ============================================================

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue='brandguide',
)
def setup_brandguide_task(self, brandguide_id: int):
    """
    Ponto de entrada. Prepara o brandguide para processamento em lotes paralelos.

    Fluxo:
        1. Baixa PDF do S3 (para inspecao)
        2. Descobre total_pages via pdfinfo_from_bytes (sem renderizar imagens)
        3. Atualiza BrandguideUpload (status=converting, total_pages)
        4. Limpa paginas antigas (re-processamento)
        5. Dispara chord de convert_pages_batch_task, callback finalize
    """
    logger.info('[brandguide] setup iniciado brandguide_id=%s', brandguide_id)

    try:
        brandguide = BrandguideUpload.objects.get(id=brandguide_id)
    except BrandguideUpload.DoesNotExist:
        logger.error('[brandguide] BrandguideUpload %s nao existe', brandguide_id)
        return {'success': False, 'error': 'not_found'}

    try:
        from pdf2image import pdfinfo_from_bytes
    except ImportError as exc:
        _mark_error(brandguide, f'Dependencias ausentes: {exc}')
        return {'success': False, 'error': 'deps_missing'}

    brandguide.processing_status = 'converting'
    brandguide.save(update_fields=['processing_status'])

    try:
        pdf_bytes = _download_from_s3(brandguide.s3_key_pdf)
        info = pdfinfo_from_bytes(pdf_bytes)
        total_pages = int(info.get('Pages', 0))

        if total_pages <= 0:
            _mark_error(brandguide, 'PDF invalido ou sem paginas')
            return {'success': False, 'error': 'empty_pdf'}

        max_pages = getattr(settings, 'BRANDGUIDE_MAX_PAGES', 200)
        if total_pages > max_pages:
            _mark_error(
                brandguide,
                f'PDF excede o limite de {max_pages} paginas ({total_pages} recebidas)'
            )
            return {'success': False, 'error': 'too_many_pages'}

        brandguide.total_pages = total_pages
        brandguide.save(update_fields=['total_pages'])

        # Limpa paginas antigas em caso de re-processamento
        brandguide.pages.all().delete()

        # Monta os lotes
        batch_size = getattr(settings, 'BRANDGUIDE_BATCH_SIZE', 5)
        batch_tasks = []
        for start in range(1, total_pages + 1, batch_size):
            end = min(start + batch_size - 1, total_pages)
            batch_tasks.append(convert_pages_batch_task.s(brandguide_id, start, end))

        logger.info(
            '[brandguide] Disparando chord: %s lotes para %s paginas (brandguide_id=%s)',
            len(batch_tasks), total_pages, brandguide_id
        )

        # chord: executa todos os batch_tasks em paralelo, depois chama finalize
        chord(batch_tasks)(finalize_brandguide_task.s(brandguide_id))

        return {
            'success': True,
            'brandguide_id': brandguide_id,
            'total_pages': total_pages,
            'batches': len(batch_tasks),
        }

    except Exception as exc:
        logger.exception('[brandguide] setup falhou brandguide_id=%s', brandguide_id)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            _mark_error(brandguide, f'Falhou apos retries (setup): {exc}')
            return {'success': False, 'error': str(exc)}


# ============================================================
# BATCH - processa um intervalo de paginas
# ============================================================

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    queue='brandguide',
)
def convert_pages_batch_task(
    self,
    brandguide_id: int,
    start_page: int,
    end_page: int,
) -> Dict:
    """
    Converte um intervalo de paginas do PDF em PNGs, extrai texto e cria
    BrandguidePage para cada uma.

    Cada sub-task baixa o PDF do S3 independentemente (fast, <2s) para manter
    a task stateless e evitar dependencia de cache compartilhado entre workers.
    """
    logger.info(
        '[brandguide] batch brandguide_id=%s paginas %s-%s',
        brandguide_id, start_page, end_page
    )

    try:
        brandguide = BrandguideUpload.objects.get(id=brandguide_id)
    except BrandguideUpload.DoesNotExist:
        return {'success': False, 'start': start_page, 'end': end_page, 'error': 'not_found'}

    try:
        from pdf2image import convert_from_bytes

        pdf_bytes = _download_from_s3(brandguide.s3_key_pdf)

        dpi = getattr(settings, 'BRANDGUIDE_DPI', 200)
        images = convert_from_bytes(
            pdf_bytes,
            dpi=dpi,
            fmt='png',
            first_page=start_page,
            last_page=end_page,
        )

        # Extrai texto das paginas do lote (pdfplumber eh rapido; faz so o range)
        texts = _extract_texts_range(pdf_bytes, start_page, end_page)

        pages_prefix = _pages_prefix_from_pdf_key(brandguide.s3_key_pdf)
        created = 0

        for offset, img in enumerate(images):
            page_num = start_page + offset
            page_png_bytes = _image_to_png_bytes(img)
            page_s3_key = f'{pages_prefix}page_{page_num:03d}.png'

            _upload_png_to_s3(page_s3_key, page_png_bytes)
            page_url = S3Service.get_public_url(page_s3_key)

            # use update_or_create para ser idempotente em retries
            BrandguidePage.objects.update_or_create(
                brandguide=brandguide,
                page_number=page_num,
                defaults={
                    's3_key': page_s3_key,
                    's3_url': page_url,
                    'width': img.width,
                    'height': img.height,
                    'extracted_text': texts.get(page_num, '')[:50000],
                    'category': 'outro',
                    'relevance': 'medium',
                },
            )
            created += 1
            img.close()

        # Libera memoria explicitamente antes de retornar
        del images

        logger.info(
            '[brandguide] batch OK brandguide_id=%s paginas %s-%s (%s criadas)',
            brandguide_id, start_page, end_page, created
        )

        return {
            'success': True,
            'brandguide_id': brandguide_id,
            'start': start_page,
            'end': end_page,
            'created': created,
        }

    except Exception as exc:
        logger.exception(
            '[brandguide] batch falhou brandguide_id=%s paginas %s-%s',
            brandguide_id, start_page, end_page
        )
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {
                'success': False,
                'brandguide_id': brandguide_id,
                'start': start_page,
                'end': end_page,
                'error': str(exc),
            }


# ============================================================
# FINALIZE - callback do chord
# ============================================================

@shared_task(queue='brandguide')
def finalize_brandguide_task(batch_results: List[Dict], brandguide_id: int):
    """
    Callback do chord. Recebe a lista de resultados dos batches, valida todos
    os lotes e decide o proximo passo:

    - Todos OK + N8N configurado -> encadeia analyze_brandguide_task (status=analyzing)
    - Todos OK + N8N nao configurado -> marca status=completed
    - Qualquer falha -> status=error com detalhes
    """
    try:
        brandguide = BrandguideUpload.objects.get(id=brandguide_id)
    except BrandguideUpload.DoesNotExist:
        logger.error('[brandguide] finalize: BrandguideUpload %s nao existe', brandguide_id)
        return

    successful = [r for r in batch_results if r and r.get('success')]
    failed = [r for r in batch_results if r and not r.get('success')]

    pages_created = sum(r.get('created', 0) for r in successful)

    if failed:
        error_lines = [
            f"paginas {r.get('start')}-{r.get('end')}: {r.get('error', 'erro desconhecido')}"
            for r in failed
        ]
        _mark_error(
            brandguide,
            f'{len(failed)} de {len(batch_results)} lotes falharam:\n' + '\n'.join(error_lines)
        )
        logger.error(
            '[brandguide] finalize com falhas brandguide_id=%s failed=%s',
            brandguide_id, len(failed)
        )
        return

    logger.info(
        '[brandguide] conversao OK brandguide_id=%s paginas=%s lotes=%s',
        brandguide_id, pages_created, len(successful)
    )

    # Se N8N configurado, encadeia analise por IA (Fase 3).
    # Caso contrario, encerra como completed (funciona sem IA para testar Fase 2).
    webhook_url = getattr(settings, 'N8N_WEBHOOK_ANALYZE_BRANDGUIDE', '')
    if webhook_url:
        brandguide.processing_status = 'analyzing'
        brandguide.save(update_fields=['processing_status'])
        logger.info(
            '[brandguide] disparando analise IA brandguide_id=%s',
            brandguide_id
        )
        analyze_brandguide_task.delay(brandguide_id)
    else:
        brandguide.processing_status = 'completed'
        brandguide.completed_at = timezone.now()
        brandguide.save(update_fields=['processing_status', 'completed_at'])
        logger.info(
            '[brandguide] finalize OK (sem analise IA) brandguide_id=%s',
            brandguide_id
        )


# ============================================================
# FASE 3 - ANALISE POR IA VIA N8N
# ============================================================

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue='brandguide',
)
def analyze_brandguide_task(self, brandguide_id: int):
    """
    Envia paginas do brandguide processado para N8N para analise por IA.

    N8N orquestra os agentes (triagem, analise profunda, brand visual spec)
    e retorna via webhook brandguide_analysis_callback.

    Payload enviado:
        {
            "brandguide_id": int,
            "knowledge_base_id": int,
            "organization_id": int,
            "total_pages": int,
            "pages": [{page_number, s3_url, extracted_text}],
            "callback_url": str,   # onde o N8N deve postar o resultado
            "existing_kb": {...}   # dados atuais da KB para contexto
        }

    A chamada para o N8N eh fire-and-forget (N8N responde via callback).
    """
    import requests

    logger.info('[brandguide] analyze iniciado brandguide_id=%s', brandguide_id)

    try:
        brandguide = (
            BrandguideUpload.objects
            .select_related('knowledge_base__organization')
            .get(id=brandguide_id)
        )
    except BrandguideUpload.DoesNotExist:
        logger.error('[brandguide] analyze: BrandguideUpload %s nao existe', brandguide_id)
        return {'success': False, 'error': 'not_found'}

    webhook_url = getattr(settings, 'N8N_WEBHOOK_ANALYZE_BRANDGUIDE', '')
    if not webhook_url:
        _mark_error(brandguide, 'N8N_WEBHOOK_ANALYZE_BRANDGUIDE nao configurado')
        return {'success': False, 'error': 'webhook_not_configured'}

    try:
        kb = brandguide.knowledge_base

        # Gerar presigned URLs para cada pagina (as URLs publicas sao privadas no S3).
        # OpenAI precisa acessar as imagens diretamente, entao precisam ser presigned.
        pages_qs = brandguide.pages.all().order_by('page_number')
        pages_payload = []
        for page in pages_qs:
            presigned_url = S3Service.generate_presigned_download_url(page.s3_key)
            pages_payload.append({
                'page_number': page.page_number,
                's3_url': presigned_url,
                'extracted_text': page.extracted_text,
            })

        # Callback URL: o N8N vai postar o resultado aqui
        site_url = getattr(settings, 'SITE_URL', '').rstrip('/')
        callback_url = f'{site_url}/knowledge/webhook/brandguide/'

        payload = {
            'brandguide_id': brandguide.id,
            'knowledge_base_id': kb.id,
            'organization_id': kb.organization_id,
            'total_pages': brandguide.total_pages,
            'pdf_url': brandguide.s3_url_pdf,
            'pages': pages_payload,
            'callback_url': callback_url,
            'existing_kb': {
                'nome_empresa': kb.nome_empresa,
                'missao': kb.missao,
                'visao': kb.visao,
                'valores': kb.valores,
                'posicionamento': kb.posicionamento,
                'tom_voz_externo': kb.tom_voz_externo,
                'brand_visual_spec': kb.brand_visual_spec,
            },
        }

        headers = {
            'Content-Type': 'application/json',
            'X-INTERNAL-TOKEN': getattr(settings, 'N8N_WEBHOOK_SECRET', ''),
        }

        timeout = getattr(settings, 'N8N_WEBHOOK_TIMEOUT', 30)

        logger.info(
            '[brandguide] POST para N8N webhook brandguide_id=%s paginas=%s',
            brandguide_id, len(payload['pages'])
        )

        response = requests.post(
            webhook_url,
            json=payload,
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()

        logger.info(
            '[brandguide] N8N aceitou analise brandguide_id=%s status=%s',
            brandguide_id, response.status_code
        )

        # A task termina aqui. N8N vai processar assincronamente e bater
        # no callback com o resultado.
        return {
            'success': True,
            'brandguide_id': brandguide_id,
            'n8n_response_status': response.status_code,
        }

    except requests.exceptions.RequestException as exc:
        logger.exception('[brandguide] analyze falha de rede brandguide_id=%s', brandguide_id)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            _mark_error(brandguide, f'Falha ao contatar N8N apos retries: {exc}')
            return {'success': False, 'error': str(exc)}
    except Exception as exc:
        logger.exception('[brandguide] analyze falhou brandguide_id=%s', brandguide_id)
        _mark_error(brandguide, f'Erro na analise: {exc}')
        return {'success': False, 'error': str(exc)}


# ============================================================
# BACKWARD COMPATIBILITY
# ============================================================

@shared_task(queue='brandguide')
def convert_brandguide_pdf_task(brandguide_id: int):
    """
    Nome legado: redireciona para a nova orquestracao.
    Mantido para nao quebrar qualquer chamada antiga pendente na fila.
    """
    return setup_brandguide_task(brandguide_id)


# ============================================================
# HELPERS
# ============================================================

def _download_from_s3(s3_key: str) -> bytes:
    """Baixa um objeto do S3 e retorna bytes."""
    client = S3Service._get_s3_client()
    response = client.get_object(
        Bucket=settings.AWS_BUCKET_NAME,
        Key=s3_key,
    )
    return response['Body'].read()


def _upload_png_to_s3(s3_key: str, png_bytes: bytes) -> None:
    """Upload de um PNG para S3 com storage class otimizado."""
    client = S3Service._get_s3_client()
    client.put_object(
        Bucket=settings.AWS_BUCKET_NAME,
        Key=s3_key,
        Body=png_bytes,
        ContentType='image/png',
        ServerSideEncryption='AES256',
        StorageClass='INTELLIGENT_TIERING',
    )


def _image_to_png_bytes(image) -> bytes:
    """Converte um objeto PIL Image em bytes PNG."""
    buf = io.BytesIO()
    image.save(buf, format='PNG', optimize=True)
    return buf.getvalue()


def _extract_texts_range(pdf_bytes: bytes, start_page: int, end_page: int) -> Dict[int, str]:
    """
    Extrai texto apenas das paginas [start_page, end_page] do PDF.
    Retorna dict {page_number: text}.
    """
    import pdfplumber

    texts: Dict[int, str] = {}
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            # pdfplumber usa indexacao 0-based
            for idx in range(start_page - 1, min(end_page, len(pdf.pages))):
                try:
                    texts[idx + 1] = pdf.pages[idx].extract_text() or ''
                except Exception:
                    logger.warning('[brandguide] Falha ao extrair texto pag %s', idx + 1)
                    texts[idx + 1] = ''
    except Exception:
        logger.exception('[brandguide] Falha global do pdfplumber no range %s-%s', start_page, end_page)
    return texts


def _pages_prefix_from_pdf_key(pdf_key: str) -> str:
    """
    'org-23/brandguides/1776292563/original.pdf'
    -> 'org-23/brandguides/1776292563/pages/'
    """
    directory = pdf_key.rsplit('/', 1)[0]
    return f'{directory}/pages/'


def _mark_error(brandguide: BrandguideUpload, message: str) -> None:
    """Marca o brandguide com status de erro."""
    brandguide.processing_status = 'error'
    brandguide.error_message = message[:5000]
    brandguide.save(update_fields=['processing_status', 'error_message'])


# ============================================================
# FASE 4 - APLICACAO DOS DADOS EXTRAIDOS NA KB
# ============================================================

# Campos textuais simples da KB que podem ser preenchidos pela IA.
# Mapeamento: chave em suggested_kb_fields -> nome do campo no model KnowledgeBase.
_BRANDGUIDE_TEXT_FIELDS = {
    'nome_empresa': 'nome_empresa',
    'missao': 'missao',
    'visao': 'visao',
    'valores': 'valores',
    'descricao_produto': 'descricao_produto',
    'publico_externo': 'publico_externo',
    'publico_interno': 'publico_interno',
    'posicionamento': 'posicionamento',
    'diferenciais': 'diferenciais',
    'proposta_valor': 'proposta_valor',
    'tom_voz_externo': 'tom_voz_externo',
    'tom_voz_interno': 'tom_voz_interno',
}

# Campos do tipo lista (JSONField com default=list).
_BRANDGUIDE_LIST_FIELDS = {
    'palavras_recomendadas': 'palavras_recomendadas',
    'palavras_evitar': 'palavras_evitar',
    'concorrentes': 'concorrentes',
    'fontes_confiaveis': 'fontes_confiaveis',
    'canais_trends': 'canais_trends',
    'palavras_chave_trends': 'palavras_chave_trends',
}


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    queue='brandguide',
)
def apply_brandguide_to_kb_task(self, brandguide_id: int):
    """
    Aplica os dados extraidos pelo brandguide nos campos da KB e cria
    registros relacionados (ColorPalette, Typography). Roda na fila brandguide
    para nao bloquear workers principais nem o gunicorn que recebeu o callback.

    Idempotente: pode ser re-executada sem duplicar dados.
    Em caso de falha, marca status='error' (nao deixa preso em 'analyzing').
    Ao final do sucesso, marca status='completed'.
    """
    from apps.knowledge.models import (
        BrandguideUpload, ColorPalette, Typography,
    )

    try:
        brandguide = BrandguideUpload.objects.select_related(
            'knowledge_base'
        ).get(id=brandguide_id)
    except BrandguideUpload.DoesNotExist:
        logger.error('[brandguide_apply] BrandguideUpload %s nao existe', brandguide_id)
        return {'success': False, 'error': 'not_found'}

    try:
        return _apply_brandguide_inner(brandguide)
    except Exception as exc:
        logger.exception(
            '[brandguide_apply] Falha ao aplicar brandguide_id=%s', brandguide_id
        )
        # Tentar de novo em retries
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            pass
        # Esgotadas as retries: marcar erro para nao deixar preso em 'analyzing'
        brandguide.processing_status = 'error'
        brandguide.error_message = (
            f'Falha ao aplicar dados do brandguide na KB: {exc}'
        )[:5000]
        brandguide.save(update_fields=['processing_status', 'error_message'])
        return {'success': False, 'brandguide_id': brandguide_id, 'error': str(exc)}


def _apply_brandguide_inner(brandguide):
    """Logica de aplicacao isolada para permitir retry/error handling limpo."""
    from apps.knowledge.models import ColorPalette, Typography

    kb = brandguide.knowledge_base
    spec = kb.brand_visual_spec or {}
    suggested = ((kb.n8n_analysis or {}).get('brandguide') or {}).get('suggested_fields') or {}

    filled_fields: List[str] = []
    update_fields: List[str] = []

    # ----------------------------------------------------------
    # 1. Campos textuais simples
    # ----------------------------------------------------------
    for src_key, dst_field in _BRANDGUIDE_TEXT_FIELDS.items():
        value = suggested.get(src_key)
        if not value or not isinstance(value, str):
            continue
        value = value.strip()
        if not value:
            continue
        setattr(kb, dst_field, value)
        filled_fields.append(dst_field)
        update_fields.append(dst_field)

    # ----------------------------------------------------------
    # 2. Campos lista
    # ----------------------------------------------------------
    for src_key, dst_field in _BRANDGUIDE_LIST_FIELDS.items():
        value = suggested.get(src_key)
        if not isinstance(value, list) or not value:
            continue
        # Higieniza: remove vazios, deduplica preservando ordem
        cleaned: List[str] = []
        seen = set()
        for item in value:
            if not isinstance(item, str):
                continue
            item = item.strip()
            if not item or item.lower() in seen:
                continue
            cleaned.append(item)
            seen.add(item.lower())
        if cleaned:
            setattr(kb, dst_field, cleaned)
            filled_fields.append(dst_field)
            update_fields.append(dst_field)

    # ----------------------------------------------------------
    # 3. Notas de uso do logo (a partir do brand_visual_spec.logo)
    # ----------------------------------------------------------
    logo_data = spec.get('logo') or {}
    notes_parts: List[str] = []
    desc = logo_data.get('descricao_visual')
    if desc:
        notes_parts.append(f'Descricao: {desc}')
    variacoes = logo_data.get('variacoes')
    if isinstance(variacoes, list) and variacoes:
        notes_parts.append('Variacoes: ' + ', '.join(str(v) for v in variacoes if v))
    area = logo_data.get('area_seguranca')
    if area:
        notes_parts.append(f'Area de seguranca: {area}')
    red_digital = logo_data.get('reducao_minima_digital_px')
    if red_digital:
        notes_parts.append(f'Reducao minima digital: {red_digital}px')
    red_impresso = logo_data.get('reducao_minima_impresso_mm')
    if red_impresso:
        notes_parts.append(f'Reducao minima impresso: {red_impresso}mm')
    if notes_parts:
        kb.logo_usage_notes = '\n'.join(notes_parts)
        filled_fields.append('logo_usage_notes')
        update_fields.append('logo_usage_notes')

    # ----------------------------------------------------------
    # 4. Persistir KB com a lista de campos preenchidos
    # ----------------------------------------------------------
    if filled_fields:
        kb.brandguide_filled_fields = filled_fields
        update_fields.append('brandguide_filled_fields')
        kb.save(update_fields=update_fields)

    # ----------------------------------------------------------
    # 5. ColorPalette: cria a partir de brand_visual_spec.cores
    # ----------------------------------------------------------
    cores_data = spec.get('cores') or {}
    colors_created = 0
    color_order_base = (
        ColorPalette.objects.filter(knowledge_base=kb).count() * 10
    )
    for group_key, color_type in (
        ('institucional', 'primary'),
        ('iniciativas', 'accent'),
    ):
        for cor in (cores_data.get(group_key) or []):
            if not isinstance(cor, dict):
                continue
            hex_code = (cor.get('hex') or '').strip()
            if not hex_code or not hex_code.startswith('#'):
                continue
            hex_code = hex_code[:7].upper()
            if ColorPalette.objects.filter(
                knowledge_base=kb, hex_code__iexact=hex_code
            ).exists():
                continue
            base_name = (cor.get('nome') or hex_code).strip()
            unique_name = base_name[:100]
            counter = 2
            while ColorPalette.objects.filter(
                knowledge_base=kb, name=unique_name
            ).exists():
                suffix = f' ({counter})'
                unique_name = (base_name[: 100 - len(suffix)] + suffix)
                counter += 1
            ColorPalette.objects.create(
                knowledge_base=kb,
                name=unique_name,
                hex_code=hex_code,
                color_type=color_type,
                order=color_order_base + colors_created * 10,
                created_from_brandguide=brandguide,
            )
            colors_created += 1

    # ----------------------------------------------------------
    # 6. Typography: cria a partir de brand_visual_spec.tipografia
    # ----------------------------------------------------------
    tipo_data = spec.get('tipografia') or {}
    typo_created = 0
    typo_order_base = (
        Typography.objects.filter(knowledge_base=kb).count() * 10
    )
    # Sempre usa rotulo padrao para 'usage' (ignora valor livre do prompt N8N).
    # Cria Typography apenas se a fonte for uma Google Font validada — caso
    # contrario o slot fica em branco para o usuario preencher manualmente.
    from apps.knowledge.google_fonts import normalize_google_font_name

    typo_skipped: List[str] = []
    for slot_key, default_usage in (
        ('primaria', 'Títulos'),
        ('secundaria', 'Texto corrido'),
    ):
        slot = tipo_data.get(slot_key) or {}
        if not isinstance(slot, dict):
            continue
        familia_raw = (slot.get('familia') or '').strip()
        if not familia_raw:
            continue
        # Tenta a familia principal e o fallback se houver
        canonical = normalize_google_font_name(familia_raw)
        if not canonical:
            fallback = (slot.get('fallback') or '').strip()
            canonical = normalize_google_font_name(fallback) if fallback else None
            if canonical:
                logger.info(
                    '[brandguide_apply] usando fallback %s no lugar de %s (nao e Google Font)',
                    canonical, familia_raw,
                )
        if not canonical:
            typo_skipped.append(familia_raw)
            logger.info(
                '[brandguide_apply] fonte %s nao e Google Font - slot ficara em branco',
                familia_raw,
            )
            continue
        if Typography.objects.filter(
            knowledge_base=kb,
            font_source='google',
            google_font_name__iexact=canonical,
        ).exists():
            continue
        peso = (slot.get('peso_padrao') or 'Regular').strip() or 'Regular'
        Typography.objects.create(
            knowledge_base=kb,
            usage=default_usage,
            font_source='google',
            google_font_name=canonical[:200],
            google_font_weight=peso[:20],
            order=typo_order_base + typo_created * 10,
            created_from_brandguide=brandguide,
        )
        typo_created += 1

    # ----------------------------------------------------------
    # 7. Marcar brandguide como completed
    # ----------------------------------------------------------
    brandguide.processing_status = 'completed'
    brandguide.completed_at = timezone.now()
    brandguide.save(update_fields=['processing_status', 'completed_at'])

    logger.info(
        '[brandguide_apply] OK brandguide_id=%s text/list=%s cores=%s typo=%s typo_skipped=%s',
        brandguide.id, len(filled_fields), colors_created, typo_created, typo_skipped,
    )
    return {
        'success': True,
        'brandguide_id': brandguide.id,
        'fields_filled': filled_fields,
        'colors_created': colors_created,
        'typography_created': typo_created,
        'typography_skipped': typo_skipped,
    }


def wipe_brandguide_data_from_kb(kb, brandguide=None):
    """
    Remove dados aplicados pelo brandguide na KB:
      - Limpa campos textuais listados em kb.brandguide_filled_fields
      - Apaga ColorPalette/Typography com created_from_brandguide setado
      - Limpa kb.brand_visual_spec e metadados

    Se brandguide for fornecido, apaga apenas registros vinculados a ele.
    Caso contrario, apaga tudo o que veio de qualquer brandguide.

    Edicoes manuais do usuario (registros sem created_from_brandguide e
    campos fora de brandguide_filled_fields) sao preservadas.
    """
    from apps.knowledge.models import ColorPalette, Typography

    # Apagar registros relacionados
    color_qs = ColorPalette.objects.filter(knowledge_base=kb)
    typo_qs = Typography.objects.filter(knowledge_base=kb)
    if brandguide is not None:
        color_qs = color_qs.filter(created_from_brandguide=brandguide)
        typo_qs = typo_qs.filter(created_from_brandguide=brandguide)
    else:
        color_qs = color_qs.filter(created_from_brandguide__isnull=False)
        typo_qs = typo_qs.filter(created_from_brandguide__isnull=False)
    colors_deleted, _ = color_qs.delete()
    typos_deleted, _ = typo_qs.delete()

    # Limpar campos textuais que foram preenchidos pelo brandguide
    fields_to_clear = list(kb.brandguide_filled_fields or [])
    update_fields: List[str] = []
    for f in fields_to_clear:
        if f in _BRANDGUIDE_LIST_FIELDS.values():
            setattr(kb, f, [])
        elif hasattr(kb, f):
            setattr(kb, f, '')
        else:
            continue
        update_fields.append(f)

    # Limpar metadados do brand visual spec
    kb.brand_visual_spec = None
    kb.brand_visual_spec_source = None
    kb.brand_visual_spec_confidence = None
    kb.brand_visual_spec_validated = False
    kb.brandguide_filled_fields = []
    update_fields.extend([
        'brand_visual_spec',
        'brand_visual_spec_source',
        'brand_visual_spec_confidence',
        'brand_visual_spec_validated',
        'brandguide_filled_fields',
    ])
    kb.save(update_fields=update_fields)

    return {
        'colors_deleted': colors_deleted,
        'typography_deleted': typos_deleted,
        'fields_cleared': fields_to_clear,
    }
