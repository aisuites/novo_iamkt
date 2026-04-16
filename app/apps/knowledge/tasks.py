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
    Callback do chord. Recebe a lista de resultados dos batches e marca
    o brandguide como completed ou error.
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

    brandguide.processing_status = 'completed'
    brandguide.completed_at = timezone.now()
    brandguide.save(update_fields=['processing_status', 'completed_at'])

    logger.info(
        '[brandguide] finalize OK brandguide_id=%s paginas=%s lotes=%s',
        brandguide_id, pages_created, len(successful)
    )


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
