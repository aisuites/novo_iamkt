"""
Views para upload de imagens de referência para Posts usando S3 Presigned URLs
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django_ratelimit.decorators import ratelimit
from apps.core.services import S3Service
from apps.core.utils.upload_validators import FileUploadValidator
import json


@login_required
@ratelimit(key='user', rate='20/m', method='POST', block=True)
@require_http_methods(["POST"])
def generate_reference_upload_url(request):
    """
    Gera Presigned URL para upload de imagem de referência para Posts
    
    POST params:
        - fileName: Nome do arquivo
        - fileType: MIME type
        - fileSize: Tamanho em bytes
    
    Returns:
        {
            'success': bool,
            'data': {
                'upload_url': str,
                's3_key': str,
                'expires_in': int
            }
        }
    """
    try:
        import logging
        logger = logging.getLogger(__name__)
        
        # Verificar se organization existe
        if not hasattr(request, 'organization') or not request.organization:
            logger.error("request.organization não encontrado")
            return JsonResponse({
                'success': False,
                'error': 'Organização não encontrada'
            }, status=400)
        
        organization = request.organization
        
        # Debug: ver o que está chegando
        logger.info(f"Content-Type: {request.content_type}")
        logger.info(f"Recebendo requisição de upload de imagem")
        
        file_name = request.POST.get('fileName')
        file_type = request.POST.get('fileType')
        file_size = request.POST.get('fileSize')
        
        logger.info(f"Parsed - fileName: {file_name}, fileType: {file_type}, fileSize: {file_size}")
        
        if not all([file_name, file_type, file_size]):
            return JsonResponse({
                'success': False,
                'error': f'Parâmetros obrigatórios faltando. Recebido: fileName={file_name}, fileType={file_type}, fileSize={file_size}'
            }, status=400)
        
        # VALIDAÇÃO DE SEGURANÇA
        is_valid, error_msg = FileUploadValidator.validate_image(
            file_name=file_name,
            file_type=file_type,
            file_size=int(file_size)
        )
        
        if not is_valid:
            return JsonResponse({
                'success': False,
                'error': error_msg
            }, status=400)
        
        # Gerar Presigned URL
        result = S3Service.generate_presigned_upload_url(
            file_name=file_name,
            file_type=file_type,
            file_size=int(file_size),
            category='posts',
            organization_id=organization.id,
            custom_data={'type': 'post_reference'}
        )
        
        # Adicionar organization_id para o JavaScript usar nos headers
        result['organization_id'] = organization.id
        
        return JsonResponse({
            'success': True,
            'data': result
        })
        
    except ValueError as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"ValueError em generate_reference_upload_url: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Exception em generate_reference_upload_url: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Erro ao gerar URL de upload: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def create_reference_image(request):
    """
    Retorna dados da imagem de referência após upload bem-sucedido no S3
    (Não cria registro no banco - apenas valida e retorna URL)
    
    POST params:
        - name: Nome da imagem
        - s3Key: Chave do arquivo no S3
    
    Returns:
        {
            'success': bool,
            'data': {
                'name': str,
                's3_key': str,
                's3_url': str,
                'previewUrl': str
            }
        }
    """
    try:
        organization = request.organization
        
        data = json.loads(request.body)
        name = data.get('name')
        s3_key = data.get('s3Key')
        
        if not all([name, s3_key]):
            return JsonResponse({
                'success': False,
                'error': 'Parâmetros obrigatórios: name, s3Key'
            }, status=400)
        
        # Validar que s3_key pertence à organização
        S3Service.validate_organization_access(s3_key, organization.id)
        
        # Gerar URL pública
        s3_url = S3Service.get_public_url(s3_key)
        
        # Gerar URL de preview
        preview_url = S3Service.generate_presigned_download_url(s3_key)
        
        return JsonResponse({
            'success': True,
            'data': {
                'name': name,
                's3_key': s3_key,
                's3_url': s3_url,
                'previewUrl': preview_url
            }
        })
        
    except ValueError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=403)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Erro ao processar imagem de referência: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Erro ao processar imagem: {str(e)}'
        }, status=500)
