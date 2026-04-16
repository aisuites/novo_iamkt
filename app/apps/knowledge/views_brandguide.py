"""
Views do pipeline de Brandguide.

Fase 2: upload de PDF, consulta de status, delecao.
Fase 3: callback do N8N com resultado da analise IA.
Fase 4: upload de templates visuais e assets de grafismo.
"""

import json
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django_ratelimit.decorators import ratelimit

from apps.core.services import S3Service
from apps.core.utils.upload_validators import FileUploadValidator
from apps.knowledge.models import (
    BrandgraficModule, BrandguidePage, BrandguideUpload,
    KnowledgeBase, VisualTemplate,
)

logger = logging.getLogger(__name__)


# ============================================================
# UPLOAD DO PDF BRANDGUIDE
# ============================================================

@login_required
@ratelimit(key='user', rate='5/m', method='POST', block=True)
@require_http_methods(["POST"])
def generate_brandguide_upload_url(request):
    """
    Gera presigned URL para upload de um PDF de brandguide no S3.

    POST params:
        - fileName: Nome do arquivo (.pdf)
        - fileType: MIME type (deve ser application/pdf)
        - fileSize: Tamanho em bytes (max 50 MB)

    Returns:
        {
            'success': bool,
            'data': {
                'upload_url': str,
                's3_key': str,
                'expires_in': int,
                'signed_headers': dict
            }
        }
    """
    try:
        organization = request.organization

        file_name = request.POST.get('fileName')
        file_type = request.POST.get('fileType')
        file_size = request.POST.get('fileSize')

        if not all([file_name, file_type, file_size]):
            return JsonResponse({
                'success': False,
                'error': 'Parametros obrigatorios: fileName, fileType, fileSize'
            }, status=400)

        try:
            file_size_int = int(file_size)
        except (TypeError, ValueError):
            return JsonResponse({
                'success': False,
                'error': 'fileSize invalido'
            }, status=400)

        # Validacao especifica de brandguide (tipo + tamanho maximo maior)
        if file_type != 'application/pdf':
            return JsonResponse({
                'success': False,
                'error': 'Apenas arquivos PDF sao aceitos para brandguide'
            }, status=400)

        if file_size_int > settings.BRANDGUIDE_MAX_FILE_SIZE:
            max_mb = settings.BRANDGUIDE_MAX_FILE_SIZE // (1024 * 1024)
            return JsonResponse({
                'success': False,
                'error': f'Arquivo excede o limite de {max_mb} MB'
            }, status=400)

        # Gerar presigned URL
        result = S3Service.generate_presigned_upload_url(
            file_name=file_name,
            file_type=file_type,
            file_size=file_size_int,
            category='brandguides',
            organization_id=organization.id,
        )

        result['organization_id'] = organization.id

        return JsonResponse({'success': True, 'data': result})

    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except Exception:
        logger.exception('Erro ao gerar URL de upload de brandguide')
        return JsonResponse({
            'success': False,
            'error': 'Erro ao gerar URL de upload'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def create_brandguide(request):
    """
    Registra um BrandguideUpload apos confirmacao de upload no S3.
    Dispara Celery task para conversao PDF -> PNGs.

    POST params:
        - s3Key: chave do objeto no S3
        - originalFilename: nome original do arquivo
        - fileSize: tamanho em bytes

    Returns:
        {
            'success': bool,
            'data': {
                'brandguideId': int,
                'status': str
            }
        }
    """
    try:
        organization = request.organization

        # Garantir knowledge_base existente
        knowledge_base, _ = KnowledgeBase.objects.get_or_create(
            organization=organization,
            defaults={'nome_empresa': organization.name}
        )

        s3_key = request.POST.get('s3Key')
        original_filename = request.POST.get('originalFilename', 'brandguide.pdf')
        file_size = request.POST.get('fileSize', 0)

        if not s3_key:
            return JsonResponse({
                'success': False,
                'error': 'Parametro obrigatorio: s3Key'
            }, status=400)

        # Validar que o s3_key pertence a organizacao (seguranca multi-tenant)
        S3Service.validate_organization_access(s3_key, organization.id)

        s3_url = S3Service.get_public_url(s3_key)

        try:
            file_size_int = int(file_size)
        except (TypeError, ValueError):
            file_size_int = 0

        brandguide = BrandguideUpload.objects.create(
            knowledge_base=knowledge_base,
            original_filename=original_filename,
            s3_key_pdf=s3_key,
            s3_url_pdf=s3_url,
            file_size=file_size_int,
            processing_status='uploaded',
            uploaded_by=request.user,
        )

        # Disparar orquestracao assincrona na fila dedicada 'brandguide'
        # setup -> chord(convert_pages_batch_task * N) -> finalize
        try:
            from apps.knowledge.tasks import setup_brandguide_task
            setup_brandguide_task.delay(brandguide.id)
        except Exception:
            # Se a task falhar em ser disparada, registro ja esta salvo -
            # usuario pode reprocessar depois.
            logger.exception(
                'Falha ao disparar conversao do brandguide id=%s', brandguide.id
            )

        return JsonResponse({
            'success': True,
            'data': {
                'brandguideId': brandguide.id,
                'status': brandguide.processing_status,
            }
        })

    except Exception:
        logger.exception('Erro ao criar brandguide')
        return JsonResponse({
            'success': False,
            'error': 'Erro ao registrar brandguide'
        }, status=500)


@login_required
@require_http_methods(["GET"])
def get_brandguide_status(request, brandguide_id=None):
    """
    Consulta status do processamento de um brandguide.

    Se brandguide_id nao for informado, retorna o upload mais recente da KB.
    """
    try:
        organization = request.organization
        knowledge_base = KnowledgeBase.objects.filter(
            organization=organization
        ).first()

        if not knowledge_base:
            return JsonResponse({
                'success': False,
                'error': 'Knowledge base nao encontrada'
            }, status=404)

        qs = BrandguideUpload.objects.filter(knowledge_base=knowledge_base)

        if brandguide_id:
            brandguide = qs.filter(id=brandguide_id).first()
        else:
            brandguide = qs.order_by('-created_at').first()

        if not brandguide:
            return JsonResponse({
                'success': True,
                'data': None
            })

        # Gerar presigned URL para download do PDF original
        # (S3 eh privado, entao URL publica nao funciona)
        pdf_download_url = None
        if brandguide.s3_key_pdf:
            try:
                pdf_download_url = S3Service.generate_presigned_download_url(
                    brandguide.s3_key_pdf
                )
            except Exception:
                logger.exception(
                    '[brandguide] Falha ao gerar URL de download pdf_id=%s',
                    brandguide.id
                )

        return JsonResponse({
            'success': True,
            'data': {
                'brandguideId': brandguide.id,
                'originalFilename': brandguide.original_filename,
                'status': brandguide.processing_status,
                'totalPages': brandguide.total_pages,
                'fileSize': brandguide.file_size,
                'errorMessage': brandguide.error_message,
                'createdAt': brandguide.created_at.isoformat(),
                'completedAt': brandguide.completed_at.isoformat() if brandguide.completed_at else None,
                'pagesProcessed': brandguide.pages.count(),
                'pdfDownloadUrl': pdf_download_url,
            }
        })

    except Exception:
        logger.exception('Erro ao consultar status do brandguide')
        return JsonResponse({
            'success': False,
            'error': 'Erro ao consultar status'
        }, status=500)


@login_required
@require_http_methods(["POST", "DELETE"])
def delete_brandguide(request, brandguide_id):
    """
    Deleta um BrandguideUpload completamente: DB + S3.

    S3: remove todos os objetos do prefixo org-{id}/brandguides/{timestamp}/
        (PDF original + todas as paginas PNG convertidas + assets extraidos).
    DB: remove BrandguideUpload (cascade em BrandguidePage e BrandgraficModule).
    """
    try:
        organization = request.organization
        brandguide = get_object_or_404(
            BrandguideUpload,
            id=brandguide_id,
            knowledge_base__organization=organization,
        )

        # Deletar do S3 primeiro. Se falhar aqui, DB ainda tem a referencia
        # e o usuario pode tentar novamente.
        s3_prefix = _s3_prefix_from_pdf_key(brandguide.s3_key_pdf, organization.id)
        s3_deleted = 0
        if s3_prefix:
            try:
                s3_deleted = S3Service.delete_prefix(s3_prefix)
                logger.info(
                    '[brandguide] S3 cleanup: %s objetos removidos do prefix %s',
                    s3_deleted, s3_prefix
                )
            except Exception:
                # Log mas nao impede delete do DB - usuario quer se livrar do registro.
                logger.exception(
                    '[brandguide] Falha ao limpar S3 prefix %s (prosseguindo com delete DB)',
                    s3_prefix
                )

        brandguide.delete()

        return JsonResponse({
            'success': True,
            'data': {
                'deletedId': brandguide_id,
                's3ObjectsDeleted': s3_deleted,
            }
        })

    except Exception:
        logger.exception('Erro ao deletar brandguide id=%s', brandguide_id)
        return JsonResponse({
            'success': False,
            'error': 'Erro ao deletar brandguide'
        }, status=500)


# ============================================================
# FASE 4 - UPLOAD DE TEMPLATES VISUAIS
# ============================================================

@login_required
@ratelimit(key='user', rate='10/m', method='POST', block=True)
@require_http_methods(["POST"])
def generate_template_upload_url(request):
    """Gera presigned URL para upload de template visual (PNG/JPG/WebP, max 10MB)."""
    try:
        organization = request.organization
        file_name = request.POST.get('fileName')
        file_type = request.POST.get('fileType')
        file_size = request.POST.get('fileSize')

        if not all([file_name, file_type, file_size]):
            return JsonResponse({'success': False, 'error': 'Parametros obrigatorios: fileName, fileType, fileSize'}, status=400)

        is_valid, error_msg = FileUploadValidator.validate_image(
            file_name=file_name, file_type=file_type, file_size=int(file_size)
        )
        if not is_valid:
            return JsonResponse({'success': False, 'error': error_msg}, status=400)

        result = S3Service.generate_presigned_upload_url(
            file_name=file_name, file_type=file_type, file_size=int(file_size),
            category='templates', organization_id=organization.id,
        )
        result['organization_id'] = organization.id
        return JsonResponse({'success': True, 'data': result})
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except Exception:
        logger.exception('Erro ao gerar URL de upload de template')
        return JsonResponse({'success': False, 'error': 'Erro ao gerar URL de upload'}, status=500)


@login_required
@require_http_methods(["POST"])
def create_visual_template(request):
    """Registra um VisualTemplate apos upload no S3."""
    try:
        organization = request.organization
        kb, _ = KnowledgeBase.objects.get_or_create(
            organization=organization, defaults={'nome_empresa': organization.name}
        )

        s3_key = request.POST.get('s3Key')
        name = request.POST.get('name', 'Template')
        template_type = request.POST.get('templateType', 'outro')
        social_network = request.POST.get('socialNetwork', 'universal')
        description = request.POST.get('description', '')

        if not s3_key:
            return JsonResponse({'success': False, 'error': 's3Key obrigatorio'}, status=400)

        S3Service.validate_organization_access(s3_key, organization.id)
        s3_url = S3Service.get_public_url(s3_key)

        template = VisualTemplate.objects.create(
            knowledge_base=kb,
            name=name,
            template_type=template_type,
            social_network=social_network,
            s3_key=s3_key,
            s3_url=s3_url,
            source='manual_upload',
            description=description,
            approved_by_user=True,
            uploaded_by=request.user,
        )

        preview_url = S3Service.generate_presigned_download_url(s3_key)
        return JsonResponse({
            'success': True,
            'data': {'templateId': template.id, 'previewUrl': preview_url}
        })
    except Exception:
        logger.exception('Erro ao criar template visual')
        return JsonResponse({'success': False, 'error': 'Erro ao criar template'}, status=500)


@login_required
@require_http_methods(["POST", "DELETE"])
def delete_visual_template(request, template_id):
    """Deleta um VisualTemplate + arquivo no S3."""
    try:
        organization = request.organization
        template = get_object_or_404(
            VisualTemplate, id=template_id,
            knowledge_base__organization=organization,
        )
        S3Service.delete_file(template.s3_key)
        template.delete()
        return JsonResponse({'success': True, 'data': {'deletedId': template_id}})
    except Exception:
        logger.exception('Erro ao deletar template id=%s', template_id)
        return JsonResponse({'success': False, 'error': 'Erro ao deletar template'}, status=500)


# ============================================================
# FASE 4 - UPLOAD DE ASSETS (GRAFISMOS)
# ============================================================

@login_required
@ratelimit(key='user', rate='10/m', method='POST', block=True)
@require_http_methods(["POST"])
def generate_asset_upload_url(request):
    """Gera presigned URL para upload de asset/grafismo (PNG/SVG, max 5MB)."""
    try:
        organization = request.organization
        file_name = request.POST.get('fileName')
        file_type = request.POST.get('fileType')
        file_size = request.POST.get('fileSize')

        if not all([file_name, file_type, file_size]):
            return JsonResponse({'success': False, 'error': 'Parametros obrigatorios: fileName, fileType, fileSize'}, status=400)

        result = S3Service.generate_presigned_upload_url(
            file_name=file_name, file_type=file_type, file_size=int(file_size),
            category='assets', organization_id=organization.id,
        )
        result['organization_id'] = organization.id
        return JsonResponse({'success': True, 'data': result})
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except Exception:
        logger.exception('Erro ao gerar URL de upload de asset')
        return JsonResponse({'success': False, 'error': 'Erro ao gerar URL de upload'}, status=500)


@login_required
@require_http_methods(["POST"])
def create_brandgrafic_module(request):
    """Registra um BrandgraficModule (upload manual) apos upload no S3."""
    try:
        organization = request.organization
        kb, _ = KnowledgeBase.objects.get_or_create(
            organization=organization, defaults={'nome_empresa': organization.name}
        )

        s3_key = request.POST.get('s3Key')
        name = request.POST.get('name', 'Asset')
        orientation = request.POST.get('orientation', 'both')
        usage_hint = request.POST.get('usageHint', '')
        file_format = 'svg' if s3_key and s3_key.endswith('.svg') else 'png'

        if not s3_key:
            return JsonResponse({'success': False, 'error': 's3Key obrigatorio'}, status=400)

        S3Service.validate_organization_access(s3_key, organization.id)
        s3_url = S3Service.get_public_url(s3_key)

        asset = BrandgraficModule.objects.create(
            knowledge_base=kb,
            name=name,
            extraction_type='manual_upload',
            s3_key=s3_key,
            s3_url=s3_url,
            file_format=file_format,
            has_transparency=(file_format == 'png'),
            orientation=orientation,
            usage_hint=usage_hint,
            approved_by_user=True,
            is_active=True,
        )

        preview_url = S3Service.generate_presigned_download_url(s3_key)
        return JsonResponse({
            'success': True,
            'data': {'assetId': asset.id, 'previewUrl': preview_url}
        })
    except Exception:
        logger.exception('Erro ao criar asset')
        return JsonResponse({'success': False, 'error': 'Erro ao criar asset'}, status=500)


@login_required
@require_http_methods(["POST", "DELETE"])
def delete_brandgrafic_module(request, asset_id):
    """Deleta um BrandgraficModule + arquivo no S3."""
    try:
        organization = request.organization
        asset = get_object_or_404(
            BrandgraficModule, id=asset_id,
            knowledge_base__organization=organization,
        )
        S3Service.delete_file(asset.s3_key)
        asset.delete()
        return JsonResponse({'success': True, 'data': {'deletedId': asset_id}})
    except Exception:
        logger.exception('Erro ao deletar asset id=%s', asset_id)
        return JsonResponse({'success': False, 'error': 'Erro ao deletar asset'}, status=500)


def _s3_prefix_from_pdf_key(pdf_key: str, organization_id: int) -> str:
    """
    Deriva o prefixo do S3 a partir do s3_key do PDF original.

    Exemplo:
        'org-23/brandguides/1776292563/original.pdf'
        -> 'org-23/brandguides/1776292563/'

    Valida que comeca com 'org-{organization_id}/' para evitar delete em
    outra organizacao (seguranca multi-tenant).
    """
    if not pdf_key:
        return ''

    directory = pdf_key.rsplit('/', 1)[0] + '/'
    expected_prefix = f'org-{organization_id}/brandguides/'
    if not directory.startswith(expected_prefix):
        logger.warning(
            '[brandguide] Prefix S3 fora do escopo da organizacao: %s (esperado %s)',
            directory, expected_prefix
        )
        return ''
    return directory


# ============================================================
# FASE 3 - WEBHOOK CALLBACK DO N8N (analise IA)
# ============================================================

@csrf_exempt
@require_POST
def brandguide_analysis_callback(request):
    """
    Webhook que recebe o resultado da analise IA do N8N.

    Payload esperado:
        {
            "brandguide_id": int,
            "knowledge_base_id": int,
            "status": "completed" | "error",
            "page_classifications": [
                {"page_number": int, "category": str, "relevance": str}
            ],
            "suggested_kb_fields": {...},     # campos sugeridos para KB
            "brand_visual_spec": {...},        # spec visual estruturado
            "error_message": str (opcional quando status=error)
        }

    Seguranca:
        - Token X-INTERNAL-TOKEN obrigatorio
        - Validacao de IP (N8N_ALLOWED_IPS)
        - Rate limit por IP
    """
    # CAMADA 1: Token interno
    internal_token = request.headers.get('X-INTERNAL-TOKEN')
    if internal_token != settings.N8N_WEBHOOK_SECRET:
        logger.warning(
            '[brandguide_cb] Token invalido de IP %s',
            request.META.get('REMOTE_ADDR')
        )
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=401)

    # CAMADA 2: IP permitido
    client_ip = (
        request.META.get('HTTP_CF_CONNECTING_IP')
        or request.META.get('REMOTE_ADDR')
    )
    allowed_ips = [ip.strip() for ip in settings.N8N_ALLOWED_IPS.split(',') if ip.strip()]
    if allowed_ips and client_ip not in allowed_ips:
        logger.warning('[brandguide_cb] IP nao autorizado: %s', client_ip)
        return JsonResponse({'success': False, 'error': 'Unauthorized IP'}, status=401)

    # CAMADA 3: Rate limit por IP
    cache_key = f'brandguide_cb_rate_limit_{client_ip}'
    current = cache.get(cache_key, 0)
    max_per_min = int(settings.N8N_RATE_LIMIT_PER_IP.split('/')[0])
    if current >= max_per_min:
        logger.warning('[brandguide_cb] Rate limit excedido IP=%s', client_ip)
        return JsonResponse({'success': False, 'error': 'Rate limit exceeded'}, status=429)
    cache.set(cache_key, current + 1, 60)

    # Parse do payload
    try:
        data = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning('[brandguide_cb] Payload invalido: %s', exc)
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    brandguide_id = data.get('brandguide_id')
    if not brandguide_id:
        return JsonResponse({'success': False, 'error': 'brandguide_id obrigatorio'}, status=400)

    try:
        brandguide = BrandguideUpload.objects.select_related(
            'knowledge_base'
        ).get(id=brandguide_id)
    except BrandguideUpload.DoesNotExist:
        logger.warning('[brandguide_cb] BrandguideUpload %s nao existe', brandguide_id)
        return JsonResponse({'success': False, 'error': 'brandguide nao encontrado'}, status=404)

    status_recebido = (data.get('status') or 'completed').lower()

    # Guard: nao sobrescrever 'completed' com 'error' (protege contra
    # callbacks duplicados do Error Trigger de execucoes anteriores do N8N)
    if brandguide.processing_status == 'completed' and status_recebido == 'error':
        logger.warning(
            '[brandguide_cb] Ignorando callback de erro para brandguide ja completed id=%s',
            brandguide_id
        )
        return JsonResponse({'success': True, 'message': 'ignorado (ja completed)'})

    # Caso de erro reportado pelo N8N
    if status_recebido == 'error':
        error_msg = data.get('error_message') or 'Erro na analise (sem detalhes)'
        brandguide.processing_status = 'error'
        brandguide.error_message = error_msg[:5000]
        brandguide.save(update_fields=['processing_status', 'error_message'])
        logger.error(
            '[brandguide_cb] N8N reportou erro brandguide_id=%s: %s',
            brandguide_id, error_msg
        )
        return JsonResponse({'success': True, 'message': 'erro registrado'})

    # Salvar dados de consumo de tokens (se enviados pelo N8N)
    ai_usage = data.get('ai_usage')
    if ai_usage:
        brandguide.ai_usage = ai_usage
        brandguide.save(update_fields=['ai_usage'])

    # Caso de sucesso: aplicar resultados
    try:
        _apply_analysis_result(brandguide, data)
    except Exception:
        logger.exception('[brandguide_cb] Falha ao aplicar resultado brandguide_id=%s', brandguide_id)
        brandguide.processing_status = 'error'
        brandguide.error_message = 'Falha ao processar resultado do N8N'
        brandguide.save(update_fields=['processing_status', 'error_message'])
        return JsonResponse({'success': False, 'error': 'internal_error'}, status=500)

    brandguide.processing_status = 'completed'
    brandguide.completed_at = timezone.now()
    brandguide.save(update_fields=['processing_status', 'completed_at'])

    logger.info(
        '[brandguide_cb] Analise aplicada brandguide_id=%s',
        brandguide_id
    )

    return JsonResponse({'success': True, 'brandguide_id': brandguide_id})


def _apply_analysis_result(brandguide: BrandguideUpload, data: dict) -> None:
    """
    Aplica o resultado da analise vindo do N8N no banco.

    - Atualiza classificacoes das BrandguidePage
    - Salva suggested_kb_fields como sugestao pendente (kb.n8n_analysis)
    - Salva brand_visual_spec na KB (com source=brandguide_pdf, confidence=high)
    """
    kb = brandguide.knowledge_base

    # 1. Atualizar classificacoes das paginas
    page_classifications = data.get('page_classifications') or []
    for pc in page_classifications:
        page_num = pc.get('page_number')
        if not page_num:
            continue
        updates = {}
        if pc.get('category'):
            updates['category'] = pc['category'][:30]
        if pc.get('relevance') in ('high', 'medium', 'low'):
            updates['relevance'] = pc['relevance']
        if updates:
            BrandguidePage.objects.filter(
                brandguide=brandguide,
                page_number=page_num,
            ).update(**updates)

    # 2. Salvar campos sugeridos (usuario aprova depois via perfil_view)
    suggested_fields = data.get('suggested_kb_fields') or {}
    if suggested_fields:
        current_analysis = kb.n8n_analysis or {}
        # Agrupar em sub-chave para nao conflitar com analise de fundamentos
        current_analysis['brandguide'] = {
            'brandguide_id': brandguide.id,
            'received_at': timezone.now().isoformat(),
            'suggested_fields': suggested_fields,
        }
        kb.n8n_analysis = current_analysis

    # 3. Salvar Brand Visual Spec com metadados de origem
    brand_visual_spec = data.get('brand_visual_spec')
    if brand_visual_spec:
        kb.brand_visual_spec = brand_visual_spec
        kb.brand_visual_spec_source = 'brandguide_pdf'
        kb.brand_visual_spec_confidence = 'high'
        # Requer aprovacao do usuario no perfil antes de ser usado em prod
        kb.brand_visual_spec_validated = False

    kb.save()
