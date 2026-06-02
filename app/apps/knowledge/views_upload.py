"""
Views para upload de arquivos usando S3 Presigned URLs
Versão 2.0 - Seguindo guia Django S3 completo
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django_ratelimit.decorators import ratelimit
from apps.core.services import S3Service
from apps.core.utils.image_validators import ImageValidator
from apps.core.utils.upload_validators import FileUploadValidator
from apps.knowledge.models import Logo, ReferenceImage, CustomFont
import json


# ============================================
# VIEW GENÉRICA DE PREVIEW (Seguindo Guia)
# ============================================

@login_required
@require_http_methods(["GET"])
def get_preview_url(request):
    """
    View genérica para obter Presigned URL de preview
    Funciona para qualquer tipo de arquivo (logos, references, etc)
    
    GET params:
        - s3_key: Chave do arquivo no S3
    
    Returns:
        {
            'success': bool,
            'data': {
                'previewUrl': str,
                'expiresIn': int
            }
        }
    """
    try:
        s3_key = request.GET.get('s3_key')
        
        if not s3_key:
            return JsonResponse({
                'success': False,
                'error': 'Parâmetro s3_key obrigatório'
            }, status=400)
        
        # Validar que arquivo pertence à organização do usuário
        organization = request.organization
        S3Service.validate_organization_access(s3_key, organization.id)
        
        # Gerar Presigned URL
        preview_url = S3Service.generate_presigned_download_url(s3_key)
        
        return JsonResponse({
            'success': True,
            'data': {
                'previewUrl': preview_url,
                'expiresIn': S3Service.DOWNLOAD_URL_EXPIRATION
            }
        })
        
    except ValueError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=403)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'Erro ao gerar URL de preview'
        }, status=500)


# ============================================
# UPLOAD DE LOGOS
# ============================================

@login_required
@ratelimit(key='user', rate='10/m', method='POST', block=True)
@require_http_methods(["POST"])
def generate_logo_upload_url(request):
    """
    Gera Presigned URL para upload de logo
    
    POST params:
        - fileName: Nome do arquivo
        - fileType: MIME type
        - fileSize: Tamanho em bytes
        - logoType: Tipo do logo (principal, horizontal, etc)
    
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
        organization = request.organization
        
        file_name = request.POST.get('fileName')
        file_type = request.POST.get('fileType')
        file_size = request.POST.get('fileSize')
        logo_type = request.POST.get('logoType', 'principal')
        
        if not all([file_name, file_type, file_size]):
            return JsonResponse({
                'success': False,
                'error': 'Parâmetros obrigatórios: fileName, fileType, fileSize'
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
        
        # Gerar Presigned URL usando novo S3Service
        result = S3Service.generate_presigned_upload_url(
            file_name=file_name,
            file_type=file_type,
            file_size=int(file_size),
            category='logos',
            organization_id=organization.id,
            custom_data={'logo_type': logo_type}
        )
        
        # Adicionar organization_id para o JavaScript usar nos headers
        result['organization_id'] = organization.id
        
        return JsonResponse({
            'success': True,
            'data': result
        })
        
    except ValueError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'Erro ao gerar URL de upload'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def create_logo(request):
    """
    Cria registro de Logo após upload bem-sucedido no S3
    
    POST params:
        - name: Nome do logo
        - logoType: Tipo do logo
        - s3Key: Chave do arquivo no S3
        - fileFormat: Formato do arquivo (png, svg, jpg)
        - isPrimary: Se é logo principal (opcional)
    
    Returns:
        {
            'success': bool,
            'data': {
                'logoId': int,
                'previewUrl': str
            }
        }
    """
    try:
        organization = request.organization
        
        # Obter ou criar knowledge_base (usando get_or_create para evitar duplicatas)
        from apps.knowledge.models import KnowledgeBase
        knowledge_base, created = KnowledgeBase.objects.get_or_create(
            organization=organization,
            defaults={'nome_empresa': organization.name}
        )
        
        name = request.POST.get('name')
        logo_type = request.POST.get('logoType')
        s3_key = request.POST.get('s3Key')
        file_format = request.POST.get('fileFormat')
        is_primary = request.POST.get('isPrimary', 'false').lower() == 'true'
        
        if not all([name, logo_type, s3_key, file_format]):
            return JsonResponse({
                'success': False,
                'error': 'Parâmetros obrigatórios: name, logoType, s3Key, fileFormat'
            }, status=400)
        
        # Validar que s3_key pertence à organização
        S3Service.validate_organization_access(s3_key, organization.id)
        
        # Validar dimensões da imagem (se não for SVG)
        if file_format != 'svg':
            # TODO: Baixar imagem do S3 e validar dimensões
            pass
        
        # Gerar URL pública
        s3_url = S3Service.get_public_url(s3_key)
        
        # Se não há nenhum logo ainda, este será o principal automaticamente
        if not is_primary and not knowledge_base.logos.exists():
            is_primary = True
        
        # Criar registro no banco
        logo = Logo.objects.create(
            knowledge_base=knowledge_base,
            name=name,
            logo_type=logo_type,
            file_format=file_format,
            s3_key=s3_key,
            s3_url=s3_url,
            is_primary=is_primary,
            uploaded_by=request.user
        )
        
        # Gerar URL de preview
        preview_url = S3Service.generate_presigned_download_url(s3_key)
        
        return JsonResponse({
            'success': True,
            'data': {
                'logoId': logo.id,
                'name': logo.name,
                'previewUrl': preview_url
            }
        })
        
    except ValueError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=403)
    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Erro ao criar logo: {str(e)}")
        logger.error(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': f'Erro ao criar logo: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["DELETE"])
def delete_logo(request, logo_id):
    """
    Deleta logo do banco e do S3
    
    URL params:
        - logo_id: ID do logo
    
    Returns:
        {'success': bool}
    """
    try:
        organization = request.organization
        
        logo = Logo.objects.get(
            id=logo_id,
            knowledge_base__organization=organization
        )
        
        # Deletar do S3
        if logo.s3_key:
            S3Service.delete_file(logo.s3_key)
        
        # Deletar do banco
        logo.delete()
        
        return JsonResponse({'success': True})
        
    except Logo.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Logo não encontrado'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'Erro ao deletar logo'
        }, status=500)


# ============================================
# UPLOAD DE IMAGENS DE REFERÊNCIA
# ============================================

@login_required
@ratelimit(key='user', rate='20/m', method='POST', block=True)
@require_http_methods(["POST"])
def generate_reference_upload_url(request):
    """
    Gera Presigned URL para upload de imagem de referência
    
    POST params:
        - fileName: Nome do arquivo
        - fileType: MIME type
        - fileSize: Tamanho em bytes
        - category: Categoria (opcional)
    
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
        organization = request.organization
        
        file_name = request.POST.get('fileName')
        file_type = request.POST.get('fileType')
        file_size = request.POST.get('fileSize')
        category = request.POST.get('category', 'geral')
        
        if not all([file_name, file_type, file_size]):
            return JsonResponse({
                'success': False,
                'error': 'Parâmetros obrigatórios: fileName, fileType, fileSize'
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
            category='references',
            organization_id=organization.id,
            custom_data={'reference_category': category}
        )
        
        # Adicionar organization_id para o JavaScript usar nos headers
        result['organization_id'] = organization.id
        
        return JsonResponse({
            'success': True,
            'data': result
        })
        
    except ValueError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'Erro ao gerar URL de upload'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def create_reference_image(request):
    """
    Cria registro de ReferenceImage após upload bem-sucedido no S3
    
    POST params:
        - name: Nome da imagem
        - s3Key: Chave do arquivo no S3
        - category: Categoria (opcional)
        - description: Descrição (opcional)
    
    Returns:
        {
            'success': bool,
            'data': {
                'referenceId': int,
                'previewUrl': str
            }
        }
    """
    try:
        organization = request.organization
        
        # Obter ou criar knowledge_base (usando get_or_create para evitar duplicatas)
        from apps.knowledge.models import KnowledgeBase
        knowledge_base, created = KnowledgeBase.objects.get_or_create(
            organization=organization,
            defaults={'nome_empresa': organization.name}
        )
        
        name = request.POST.get('name')
        s3_key = request.POST.get('s3Key')
        category = request.POST.get('category', 'geral')
        description = request.POST.get('description', '')
        
        if not all([name, s3_key]):
            return JsonResponse({
                'success': False,
                'error': 'Parâmetros obrigatórios: name, s3Key'
            }, status=400)
        
        # Validar que s3_key pertence à organização
        S3Service.validate_organization_access(s3_key, organization.id)
        
        # Gerar URL pública
        s3_url = S3Service.get_public_url(s3_key)
        
        # Criar registro no banco
        # Usar valores padrão seguros para campos que serão calculados posteriormente
        reference = ReferenceImage.objects.create(
            knowledge_base=knowledge_base,
            title=name,  # ReferenceImage usa 'title' não 'name'
            description=description,
            s3_key=s3_key,
            s3_url=s3_url,
            perceptual_hash='pending',  # Placeholder - será calculado em background
            file_size=1,  # Placeholder - será atualizado
            width=1,  # Placeholder - será atualizado
            height=1,  # Placeholder - será atualizado
            uploaded_by=request.user
        )
        
        # Gatilho 1 — analise visual em background. countdown absorve o caso
        # "subiu errado e deleta rapido" sem gastar IA; a guarda na task torna
        # a corrida um no-op se a imagem ja tiver sido removida.
        try:
            from apps.knowledge.tasks import analyze_reference_image_task
            analyze_reference_image_task.apply_async((reference.id,), countdown=15)
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                'Falha ao enfileirar analise visual da ReferenceImage %s', reference.id
            )

        # Gerar URL de preview
        preview_url = S3Service.generate_presigned_download_url(s3_key)

        return JsonResponse({
            'success': True,
            'data': {
                'referenceId': reference.id,
                'name': reference.title,
                'previewUrl': preview_url
            }
        })
        
    except ValueError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=403)
    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Erro ao criar imagem de referência: {str(e)}")
        logger.error(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': f'Erro ao criar imagem de referência: {str(e)}'
        }, status=500)


@login_required
@ratelimit(key='user', rate='5/m', method='POST', block=True)
@require_http_methods(["POST"])
def generate_font_upload_url(request):
    """
    Gera Presigned URL para upload de fonte customizada
    
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
        organization = request.organization
        
        file_name = request.POST.get('fileName')
        file_type = request.POST.get('fileType')
        file_size = request.POST.get('fileSize')
        
        if not all([file_name, file_type, file_size]):
            return JsonResponse({
                'success': False,
                'error': 'Parâmetros obrigatórios: fileName, fileType, fileSize'
            }, status=400)
        
        # VALIDAÇÃO DE SEGURANÇA
        is_valid, error_msg = FileUploadValidator.validate_font(
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
            category='fonts',
            organization_id=organization.id
        )
        
        # Adicionar organization_id para o JavaScript usar nos headers
        result['organization_id'] = organization.id
        
        return JsonResponse({
            'success': True,
            'data': result
        })
        
    except ValueError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'Erro ao gerar URL de upload'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def create_custom_font(request):
    """
    Cria registro de CustomFont após upload bem-sucedido no S3
    
    POST params:
        - name: Nome da fonte
        - s3Key: Chave do arquivo no S3
        - fileFormat: Formato do arquivo (ttf, otf, woff, woff2)
    
    Returns:
        {
            'success': bool,
            'data': {
                'fontId': int,
                'name': str,
                'previewUrl': str
            }
        }
    """
    try:
        organization = request.organization
        
        # Obter ou criar knowledge_base (usando get_or_create para evitar duplicatas)
        from apps.knowledge.models import KnowledgeBase
        knowledge_base, created = KnowledgeBase.objects.get_or_create(
            organization=organization,
            defaults={'nome_empresa': organization.name}
        )
        
        name = request.POST.get('name')
        s3_key = request.POST.get('s3Key')
        file_format = request.POST.get('fileFormat')
        
        if not all([name, s3_key, file_format]):
            return JsonResponse({
                'success': False,
                'error': 'Parâmetros obrigatórios: name, s3Key, fileFormat'
            }, status=400)
        
        # Validar que s3_key pertence à organização
        S3Service.validate_organization_access(s3_key, organization.id)
        
        # Gerar URL pública
        s3_url = S3Service.get_public_url(s3_key)
        
        # Criar registro no banco
        custom_font = CustomFont.objects.create(
            knowledge_base=knowledge_base,
            name=name,
            font_type='corpo',  # Padrão, pode ser alterado depois
            s3_key=s3_key,
            s3_url=s3_url,
            file_format=file_format,
            uploaded_by=request.user
        )
        
        # Gerar URL de preview
        preview_url = S3Service.generate_presigned_download_url(s3_key)
        
        return JsonResponse({
            'success': True,
            'data': {
                'fontId': custom_font.id,
                'name': custom_font.name,
                'previewUrl': preview_url
            }
        })
        
    except ValueError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=403)
    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Erro ao criar fonte: {str(e)}")
        logger.error(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': 'Erro ao criar fonte customizada'
        }, status=500)


@login_required
@require_http_methods(["DELETE"])
def delete_custom_font(request, font_id):
    """
    Deleta fonte customizada do banco e do S3
    
    URL params:
        - font_id: ID da fonte
    
    Returns:
        {'success': bool}
    """
    try:
        organization = request.organization
        
        font = CustomFont.objects.get(
            id=font_id,
            knowledge_base__organization=organization
        )
        
        # Deletar do S3
        if font.s3_key:
            S3Service.delete_file(font.s3_key)
        
        # Deletar do banco
        font.delete()
        
        return JsonResponse({'success': True})
        
    except CustomFont.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Fonte não encontrada'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'Erro ao deletar fonte'
        }, status=500)


@login_required
@require_http_methods(["DELETE"])
def delete_reference_image(request, reference_id):
    """
    Deleta imagem de referência do banco e do S3
    
    URL params:
        - reference_id: ID da imagem
    
    Returns:
        {'success': bool}
    """
    try:
        organization = request.organization
        
        reference = ReferenceImage.objects.get(
            id=reference_id,
            knowledge_base__organization=organization
        )
        
        # Deletar do S3
        if reference.s3_key:
            S3Service.delete_file(reference.s3_key)
        
        # Deletar do banco
        reference.delete()
        
        return JsonResponse({'success': True})
        
    except ReferenceImage.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Imagem não encontrada'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'Erro ao deletar imagem'
        }, status=500)
