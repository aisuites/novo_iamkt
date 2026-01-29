from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from django.db import transaction
import json

from .models import (
    KnowledgeBase, InternalSegment, ColorPalette, SocialNetwork, 
    ReferenceImage, Logo, CustomFont, KnowledgeChangeLog, Typography
)
from .forms import (
    KnowledgeBaseBlock1Form, KnowledgeBaseBlock2Form,
    KnowledgeBaseBlock3Form, KnowledgeBaseBlock4Form,
    KnowledgeBaseBlock5Form, KnowledgeBaseBlock6Form,
    KnowledgeBaseBlock7Form, ColorPaletteForm,
    SocialNetworkForm, ReferenceImageUploadForm,
    LogoUploadForm, CustomFontUploadForm
)
from . import services as services_module
KnowledgeBaseService = services_module.KnowledgeBaseService
from apps.utils.s3 import upload_to_s3, get_signed_url
from apps.utils.image_hash import (
    calculate_perceptual_hash, 
    find_similar_images_in_queryset,
    get_image_dimensions,
    validate_image_file
)


@never_cache
@login_required
def knowledge_view(request):
    """
    Visualizar e Editar Base de Conhecimento
    Interface accordion com edição inline por campo
    """
    # Buscar KnowledgeBase da organization do usuário
    try:
        kb = KnowledgeBase.objects.for_request(request).first()
    except Exception:
        kb = None
    
    # Se não existir, criar uma nova
    if not kb and hasattr(request, 'organization') and request.organization:
        kb = KnowledgeBase.objects.create(
            organization=request.organization,
            nome_empresa=request.organization.name
        )
    
    # Se kb ainda for None (usuário sem organization), criar vazia
    if not kb:
        kb = None
    
    # Recuperar erros de validação da sessão (se houver)
    validation_errors = request.session.pop('validation_errors', None)
    
    # Inicializar forms para cada bloco
    forms = {
        'block1': KnowledgeBaseBlock1Form(instance=kb),
        'block2': KnowledgeBaseBlock2Form(instance=kb),
        'block3': KnowledgeBaseBlock3Form(instance=kb),
        'block4': KnowledgeBaseBlock4Form(instance=kb),
        'block5': KnowledgeBaseBlock5Form(instance=kb),
        'block6': KnowledgeBaseBlock6Form(instance=kb),
        'block7': KnowledgeBaseBlock7Form(instance=kb),
    }
    
    # Buscar dados relacionados apenas se kb existir e tiver pk
    if kb and kb.pk:
        # TODOS os segmentos (ativos e inativos)
        # Otimizado com select_related para evitar N+1 queries
        internal_segments = InternalSegment.objects.filter(
            knowledge_base=kb
        ).select_related('parent', 'updated_by').order_by('is_active', 'order', 'name')
        
        colors = ColorPalette.objects.filter(knowledge_base=kb).order_by('order')
        social_networks = SocialNetwork.objects.filter(knowledge_base=kb).order_by('order')
        
        reference_images = ReferenceImage.objects.filter(
            knowledge_base=kb
        ).select_related('uploaded_by', 'knowledge_base').order_by('-created_at')[:20]
        
        logos = Logo.objects.filter(
            knowledge_base=kb
        ).select_related('uploaded_by', 'knowledge_base').order_by('-is_primary', 'logo_type')
        
        fonts = kb.typography_settings.select_related('updated_by', 'custom_font').order_by('order', 'usage')
        
        custom_fonts = CustomFont.objects.filter(
            knowledge_base=kb
        ).select_related('uploaded_by', 'knowledge_base').order_by('-created_at')
    else:
        # KB não existe ou não tem pk, inicializar vazios
        internal_segments = []
        colors = []
        social_networks = []
        reference_images = []
        logos = []
        fonts = []
        custom_fonts = []
    
    # Calcular completude proporcional por bloco (% de campos preenchidos)
    def calc_bloco_percent(fields_filled, total_fields):
        """Calcula percentual de campos preenchidos"""
        return int((fields_filled / total_fields) * 100) if total_fields > 0 else 0
    
    # BLOCO 1: Identidade (5 campos)
    bloco1_fields = [kb.nome_empresa, kb.missao, kb.visao, kb.valores, kb.descricao_produto]
    bloco1_filled = sum(1 for f in bloco1_fields if f)
    
    # BLOCO 2: Público (2 campos)
    bloco2_fields = [kb.publico_externo, kb.publico_interno]
    bloco2_filled = sum(1 for f in bloco2_fields if f)
    
    # BLOCO 3: Posicionamento (2 campos)
    bloco3_fields = [kb.posicionamento, kb.diferenciais]
    bloco3_filled = sum(1 for f in bloco3_fields if f)
    
    # BLOCO 4: Tom de Voz (4 campos)
    bloco4_fields = [
        kb.tom_voz_externo,
        kb.tom_voz_interno,
        len(kb.palavras_recomendadas or []) > 0,
        len(kb.palavras_evitar or []) > 0
    ]
    bloco4_filled = sum(1 for f in bloco4_fields if f)
    
    # BLOCO 5: Identidade Visual (2 campos principais)
    bloco5_fields = [
        colors.exists(),
        fonts.exists()
    ]
    bloco5_filled = sum(1 for f in bloco5_fields if f)
    
    # BLOCO 6: Sites e Redes (2 campos)
    bloco6_fields = [
        bool(kb.site_institucional),
        social_networks.exists()
    ]
    bloco6_filled = sum(1 for f in bloco6_fields if f)
    
    # BLOCO 7: Dados (3 campos)
    bloco7_fields = [
        len(kb.fontes_confiaveis or []) > 0,
        len(kb.canais_trends or []) > 0,
        len(kb.palavras_chave_trends or []) > 0
    ]
    bloco7_filled = sum(1 for f in bloco7_fields if f)
    
    completude_blocos = {
        'bloco1': calc_bloco_percent(bloco1_filled, len(bloco1_fields)),
        'bloco2': calc_bloco_percent(bloco2_filled, len(bloco2_fields)),
        'bloco3': calc_bloco_percent(bloco3_filled, len(bloco3_fields)),
        'bloco4': calc_bloco_percent(bloco4_filled, len(bloco4_fields)),
        'bloco5': calc_bloco_percent(bloco5_filled, len(bloco5_fields)),
        'bloco6': calc_bloco_percent(bloco6_filled, len(bloco6_fields)),
        'bloco7': calc_bloco_percent(bloco7_filled, len(bloco7_fields)),
    }
    
    context = {
        'kb': kb,
        'forms': forms,
        'internal_segments': internal_segments,
        'colors': colors,
        'social_networks': social_networks,
        'reference_images': reference_images,
        'logos': logos,
        'fonts': fonts,
        'custom_fonts': custom_fonts,
        'completude_blocos': completude_blocos,
        'completude_total': kb.completude_percentual,
        'validation_errors': validation_errors,
    }
    
    return render(request, 'knowledge/view.html', context)




@login_required
@require_http_methods(["POST"])
def knowledge_save_block(request, block_number):
    """
    Salvar bloco individual via AJAX
    
    Args:
        block_number: Número do bloco (1-7)
    
    Returns:
        JSON: {success: bool, message: str, completude: int}
    """
    # Buscar KnowledgeBase da organization
    kb = KnowledgeBase.objects.for_request(request).first()
    if not kb:
        return JsonResponse({'success': False, 'message': 'Base de conhecimento não encontrada'}, status=404)
    
    # Mapear número do bloco para form
    form_classes = {
        1: KnowledgeBaseBlock1Form,
        2: KnowledgeBaseBlock2Form,
        3: KnowledgeBaseBlock3Form,
        4: KnowledgeBaseBlock4Form,
        5: KnowledgeBaseBlock5Form,
        6: KnowledgeBaseBlock6Form,
        7: KnowledgeBaseBlock7Form,
    }
    
    form_class = form_classes.get(block_number)
    if not form_class:
        return JsonResponse({
            'success': False,
            'message': 'Bloco inválido'
        }, status=400)
    
    # Processar form
    form = form_class(request.POST, instance=kb)
    
    if form.is_valid():
        try:
            with transaction.atomic():
                # Salvar
                kb = form.save(commit=False)
                kb.last_updated_by = request.user
                kb.save()
                
                # Registrar no histórico (simplificado)
                # TODO: Implementar log detalhado de mudanças
                
                # Processar concorrentes do Bloco 6
                concorrentes_raw = request.POST.get('concorrentes', '[]')
                logger.debug(f"🔍 DEBUG Concorrentes - Raw POST data: {concorrentes_raw}")
                logger.debug(f"🔍 DEBUG Concorrentes - POST keys: {list(request.POST.keys())}")
                
                try:
                    concorrentes_list = json.loads(concorrentes_raw) if concorrentes_raw else []
                    logger.debug(f"🔍 DEBUG Concorrentes - Parsed JSON: {concorrentes_list}")
                    logger.debug(f"🔍 DEBUG Concorrentes - Type: {type(concorrentes_list)}, Length: {len(concorrentes_list)}")
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Erro ao parsear concorrentes JSON: {e}")
                    concorrentes_list = []
                
                # Validar estrutura
                if not isinstance(concorrentes_list, list):
                    logger.warning(f"⚠️  Concorrentes não é uma lista: {type(concorrentes_list)}")
                    concorrentes_list = []
                
                logger.debug(f"✅ DEBUG Concorrentes - Validados: {concorrentes_list}")
                
                # Verificar valor ANTES de salvar
                logger.debug(f"🔍 DEBUG KB ANTES - concorrentes: {kb.concorrentes}")
                
                kb.concorrentes = concorrentes_list
                kb.save()
                
                # Verificar valor DEPOIS de salvar
                kb.refresh_from_db()
                logger.debug(f"💾 DEBUG KB DEPOIS - concorrentes: {kb.concorrentes}")
                logger.debug(f"💾 DEBUG Concorrentes - Salvos no KB (id={kb.id})")
                
                return JsonResponse({
                    'success': True,
                    'message': f'Bloco {block_number} salvo com sucesso!',
                    'completude': kb.completude_percentual,
                    'is_complete': kb.is_complete
                })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Erro ao salvar: {str(e)}'
            }, status=500)
    else:
        # Retornar erros de validação
        errors = []
        for field, error_list in form.errors.items():
            for error in error_list:
                errors.append(f"{field}: {error}")
        
        return JsonResponse({
            'success': False,
            'message': 'Erros de validação',
            'errors': errors
        }, status=400)


@login_required
@require_http_methods(["POST"])
def knowledge_save_all(request):
    """
    Salvar todos os blocos de uma vez
    Usa Service Layer para processamento
    """
    # Buscar KnowledgeBase da organization
    kb = KnowledgeBase.objects.for_request(request).first()
    if not kb:
        messages.error(request, 'Base de conhecimento não encontrada')
        return redirect('knowledge:view')
    
    # Processar todos os forms (sem prefix pois o template não usa)
    forms = {
        'block1': KnowledgeBaseBlock1Form(request.POST, instance=kb),
        'block2': KnowledgeBaseBlock2Form(request.POST, instance=kb),
        'block3': KnowledgeBaseBlock3Form(request.POST, instance=kb),
        'block4': KnowledgeBaseBlock4Form(request.POST, instance=kb),
        'block5': KnowledgeBaseBlock5Form(request.POST, instance=kb),
        'block6': KnowledgeBaseBlock6Form(request.POST, instance=kb),
        'block7': KnowledgeBaseBlock7Form(request.POST, instance=kb),
    }
    
    # Validar todos os forms primeiro
    all_valid = True
    validation_errors = []
    
    for block_name, form in forms.items():
        if not form.is_valid():
            all_valid = False
            block_number = block_name.replace('block', '')
            block_titles = {
                '1': 'Identidade institucional',
                '2': 'Públicos & segmentos',
                '3': 'Posicionamento & diferenciais',
                '4': 'Tom de voz',
                '5': 'Identidade visual',
                '6': 'Sites e redes sociais',
                '7': 'Dados & insights'
            }
            block_title = block_titles.get(block_number, f'Bloco {block_number}')
            
            for field, errors in form.errors.items():
                if field != '__all__':
                    field_label = form.fields[field].label or field
                    validation_errors.append({
                        'block': block_number,
                        'block_title': block_title,
                        'field': field,
                        'field_label': field_label,
                        'errors': errors
                    })
    
    if not all_valid:
        # Mensagem principal
        messages.error(request, f'❌ Existem {len(validation_errors)} campo(s) obrigatório(s) não preenchido(s). Verifique os blocos destacados abaixo.')
        
        # Mensagens específicas por campo
        for error_info in validation_errors:
            messages.error(
                request, 
                f"Bloco {error_info['block']} ({error_info['block_title']}): {error_info['field_label']} - {', '.join(error_info['errors'])}"
            )
        
        # Adicionar lista de blocos com erro na sessão para destacar no frontend
        request.session['validation_errors'] = {
            'blocks': list(set([e['block'] for e in validation_errors])),
            'fields': [{'block': e['block'], 'field': e['field']} for e in validation_errors]
        }
        
        return redirect('knowledge:view')
    
    # Campo concorrentes agora é processado pelo KnowledgeBaseBlock6Form
    # Não precisa mais de processamento manual aqui
    
    # Se validação passou, usar Service Layer para salvar
    print("🔄 Chamando KnowledgeBaseService.save_all_blocks...", flush=True)
    success, errors = KnowledgeBaseService.save_all_blocks(request, kb, forms)
    print(f"🔄 save_all_blocks retornou: success={success}, errors={errors}", flush=True)
    
    if success:
        # ========================================
        # ONBOARDING: Marcar como concluído
        # ========================================
        if not kb.onboarding_completed:
            from django.utils import timezone
            
            kb.onboarding_completed = True
            kb.onboarding_completed_at = timezone.now()
            kb.onboarding_completed_by = request.user
            kb.save(update_fields=['onboarding_completed', 'onboarding_completed_at', 'onboarding_completed_by'])
            
            # TODO: Integração N8N (implementar após definir payload e retorno)
            # ========================================
            # PLACEHOLDER: Envio de dados para N8N
            # ========================================
            # try:
            #     n8n_payload = prepare_n8n_payload(kb)
            #     n8n_response = send_to_n8n(n8n_payload, timeout=30)
            #     process_company_profile(n8n_response, kb.organization)
            # except N8NTimeoutError:
            #     # Retry em background (Celery task)
            #     retry_n8n_send.delay(kb.id)
            # except Exception as e:
            #     logger.error(f'Erro ao enviar para N8N: {e}')
            # ========================================
            
            messages.success(request, '🎉 Base de Conhecimento salva com sucesso! Bem-vindo ao IAMKT!')
            return redirect('core:dashboard')
        
        messages.success(request, '✅ Base de Conhecimento atualizada com sucesso!')
        return redirect('knowledge:view')
    else:
        # Mostrar erros críticos
        print(f"❌ Salvamento falhou, adicionando mensagens de erro", flush=True)
        for error in errors:
            messages.error(request, error)
    
    print("🔄 Redirecionando para knowledge:view", flush=True)
    return redirect('knowledge:view')


@login_required
@require_http_methods(["POST"])
def knowledge_upload_image(request):
    """
    Upload de imagem de referência para S3
    Com verificação de similaridade (hash perceptual)
    """
    form = ReferenceImageUploadForm(request.POST, request.FILES)
    
    if form.is_valid():
        try:
            image_file = request.FILES['image_file']
            kb = KnowledgeBase.objects.for_request(request).first()
            if not kb:
                return JsonResponse({'success': False, 'message': 'Base de conhecimento não encontrada'}, status=404)
            
            # Validar imagem
            is_valid, error_msg = validate_image_file(image_file, max_size_mb=10)
            if not is_valid:
                return JsonResponse({
                    'success': False,
                    'message': error_msg
                }, status=400)
            
            # Verificar similaridade
            is_similar, similar_img, diff = find_similar_images_in_queryset(
                image_file,
                ReferenceImage.objects.filter(knowledge_base=kb),
                threshold=10
            )
            
            if is_similar:
                return JsonResponse({
                    'success': False,
                    'message': f'Imagem similar já existe: {similar_img.title}',
                    'similar_image': {
                        'id': similar_img.id,
                        'title': similar_img.title,
                        'url': get_signed_url(similar_img.s3_key),
                        'difference': diff
                    }
                }, status=400)
            
            # Calcular hash e dimensões
            perceptual_hash = calculate_perceptual_hash(image_file)
            width, height = get_image_dimensions(image_file)
            
            # Upload para S3
            s3_key = f'knowledge/reference_images/{kb.id}/{image_file.name}'
            result = upload_to_s3(
                image_file,
                s3_key,
                content_type=image_file.content_type
            )
            
            if not result['success']:
                return JsonResponse({
                    'success': False,
                    'message': f'Erro no upload: {result["error"]}'
                }, status=500)
            
            # Salvar no banco
            ref_image = form.save(commit=False)
            ref_image.knowledge_base = kb
            ref_image.s3_key = s3_key
            ref_image.s3_url = result['url']
            ref_image.perceptual_hash = perceptual_hash
            ref_image.file_size = image_file.size
            ref_image.width = width
            ref_image.height = height
            ref_image.uploaded_by = request.user
            ref_image.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Imagem enviada com sucesso!',
                'image': {
                    'id': ref_image.id,
                    'title': ref_image.title,
                    'url': get_signed_url(s3_key),
                    'width': width,
                    'height': height
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Erro ao processar imagem: {str(e)}'
            }, status=500)
    else:
        return JsonResponse({
            'success': False,
            'message': 'Formulário inválido',
            'errors': form.errors
        }, status=400)


@login_required
@require_http_methods(["POST"])
def knowledge_upload_logo(request):
    """Upload de logo para S3"""
    form = LogoUploadForm(request.POST, request.FILES)
    
    if form.is_valid():
        try:
            logo_file = request.FILES['logo_file']
            kb = KnowledgeBase.objects.for_request(request).first()
            if not kb:
                return JsonResponse({'success': False, 'message': 'Base de conhecimento não encontrada'}, status=404)
            
            # Upload para S3
            s3_key = f'knowledge/logos/{kb.id}/{logo_file.name}'
            result = upload_to_s3(logo_file, s3_key, content_type=logo_file.content_type)
            
            if not result['success']:
                return JsonResponse({
                    'success': False,
                    'message': f'Erro no upload: {result["error"]}'
                }, status=500)
            
            # Salvar no banco
            logo = form.save(commit=False)
            logo.knowledge_base = kb
            logo.s3_key = s3_key
            logo.s3_url = result['url']
            logo.file_format = logo_file.name.split('.')[-1].lower()
            logo.uploaded_by = request.user
            logo.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Logo enviado com sucesso!',
                'logo': {
                    'id': logo.id,
                    'name': logo.name,
                    'url': get_signed_url(s3_key)
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Erro: {str(e)}'
            }, status=500)
    else:
        return JsonResponse({
            'success': False,
            'errors': form.errors
        }, status=400)


@login_required
@require_http_methods(["POST"])
def knowledge_upload_font(request):
    """Upload de fonte customizada para S3"""
    form = CustomFontUploadForm(request.POST, request.FILES)
    
    if form.is_valid():
        try:
            font_file = request.FILES['font_file']
            kb = KnowledgeBase.objects.for_request(request).first()
            if not kb:
                return JsonResponse({'success': False, 'message': 'Base de conhecimento não encontrada'}, status=404)
            
            # Upload para S3
            s3_key = f'knowledge/fonts/{kb.id}/{font_file.name}'
            result = upload_to_s3(font_file, s3_key)
            
            if not result['success']:
                return JsonResponse({
                    'success': False,
                    'message': f'Erro no upload: {result["error"]}'
                }, status=500)
            
            # Salvar no banco
            font = form.save(commit=False)
            font.knowledge_base = kb
            font.s3_key = s3_key
            font.s3_url = result['url']
            font.uploaded_by = request.user
            font.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Fonte enviada com sucesso!',
                'font': {
                    'id': font.id,
                    'name': font.name,
                    'url': get_signed_url(s3_key)
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Erro: {str(e)}'
            }, status=500)
    else:
        return JsonResponse({
            'success': False,
            'errors': form.errors
        }, status=400)
