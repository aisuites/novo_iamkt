"""
Views do pipeline de Brandguide (Fase 2).

Upload de PDF, consulta de status e delecao de brandguides.
A analise por IA e feita em fases posteriores (Fase 3+).
"""

import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from apps.core.services import S3Service
from apps.knowledge.models import BrandguideUpload, KnowledgeBase

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
