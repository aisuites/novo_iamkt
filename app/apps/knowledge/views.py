from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.cache import never_cache
from django.db import transaction
from django.utils import timezone
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
from .kb_services import KnowledgeBaseService
from .services.n8n_service import N8NService
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
    
    # Modal welcome - aparece se onboarding não foi concluído (FLUXO 1)
    show_welcome_modal = False
    if kb and not kb.onboarding_completed:
        show_welcome_modal = True
    
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
        'show_welcome_modal': show_welcome_modal,
        'user_name': request.user.first_name or request.user.username,
        'kb_exists': kb is not None,
        'kb_completude': kb.completude_percentual if kb else 0,
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
                
                # Processar campo site_institucional_domain (Bloco 6)
                if block_number == 6:
                    site_domain = request.POST.get('site_institucional_domain', '').strip()
                    if site_domain:
                        # Adicionar https:// se não estiver presente
                        if not site_domain.startswith(('http://', 'https://')):
                            kb.site_institucional = f'https://{site_domain}'
                        else:
                            kb.site_institucional = site_domain
                    else:
                        kb.site_institucional = ''
                    
                    # Processar campos de redes sociais (social_*_domain)
                    social_fields = {
                        'social_instagram_domain': 'instagram',
                        'social_facebook_domain': 'facebook',
                        'social_linkedin_domain': 'linkedin',
                        'social_youtube_domain': 'youtube'
                    }
                    
                    for field_name, network_type in social_fields.items():
                        domain = request.POST.get(field_name, '').strip()
                        if domain:
                            # Adicionar https:// se não estiver presente
                            if not domain.startswith(('http://', 'https://')):
                                url = f'https://{domain}'
                            else:
                                url = domain
                            
                            # Atualizar ou criar SocialNetwork
                            from apps.knowledge.models import SocialNetwork
                            SocialNetwork.objects.update_or_create(
                                knowledge_base=kb,
                                network_type=network_type,
                                defaults={
                                    'name': network_type.capitalize(),
                                    'url': url,
                                    'is_active': True
                                }
                            )
                
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
        # ENVIAR PARA N8N: Análise de Fundamentos
        # ========================================
        print("=" * 80, flush=True)
        print("📤 [N8N] INICIANDO ENVIO DE DADOS", flush=True)
        print(f"📤 [N8N] KB ID: {kb.id}", flush=True)
        print(f"📤 [N8N] Organização: {kb.organization.name} (ID: {kb.organization_id})", flush=True)
        print(f"📤 [N8N] Onboarding completo: {kb.onboarding_completed}", flush=True)
        print(f"📤 [N8N] Status atual: {kb.analysis_status}", flush=True)
        
        try:
            n8n_result = N8NService.send_fundamentos(kb)
            print(f"📤 [N8N] Resultado: {n8n_result}", flush=True)
            
            if n8n_result.get('success'):
                print(f"✅ [N8N] SUCESSO! Revision ID: {n8n_result.get('revision_id')}", flush=True)
            else:
                print(f"⚠️ [N8N] FALHA! Erro: {n8n_result.get('error')}", flush=True)
        except Exception as e:
            print(f"❌ [N8N] EXCEÇÃO: {str(e)}", flush=True)
            import traceback
            print(traceback.format_exc(), flush=True)
        
        print("=" * 80, flush=True)
        # Não bloquear o fluxo se N8N falhar
        
        # ========================================
        # ONBOARDING: Marcar como concluído
        # ========================================
        if not kb.onboarding_completed:
            from django.utils import timezone
            
            kb.onboarding_completed = True
            kb.onboarding_completed_at = timezone.now()
            kb.onboarding_completed_by = request.user
            kb.save(update_fields=['onboarding_completed', 'onboarding_completed_at', 'onboarding_completed_by'])
            print(f"🔄 [REDIRECT] Primeira vez - redirecionando para perfil_view", flush=True)
            messages.success(request, '🎉 Base de Conhecimento salva com sucesso! Redirecionando para análise...')
        else:
            print(f"🔄 [REDIRECT] Atualização - redirecionando para perfil_view", flush=True)
            messages.success(request, '✅ Base de Conhecimento atualizada com sucesso! Redirecionando para análise...')
        
        # Redirecionar SEMPRE para Perfil da Empresa após salvar
        print(f"🔄 [REDIRECT] Executando redirect('knowledge:perfil_view')", flush=True)
        return redirect('knowledge:perfil_view')
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
                'message': 'Fonte enviada com sucesso'
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


@never_cache
@login_required
def perfil_view(request):
    """
    Página "Perfil da Empresa" - Exibe análise N8N e permite aceitar/rejeitar sugestões
    Estados: pending, processing, completed, compiling, compiled, error
    """
    print(f"🔍 [PERFIL_VIEW] Iniciando view", flush=True)
    
    # Buscar KnowledgeBase da organization
    try:
        kb = KnowledgeBase.objects.for_request(request).first()
        print(f"🔍 [PERFIL_VIEW] KB encontrado: {kb is not None}", flush=True)
    except Exception as e:
        print(f"❌ [PERFIL_VIEW] Erro ao buscar KB: {e}", flush=True)
        kb = None
    
    if not kb:
        messages.error(request, 'Base de Conhecimento não encontrada.')
        return redirect('knowledge:view')
    
    print(f"🔍 [PERFIL_VIEW] Onboarding completo: {kb.onboarding_completed}", flush=True)
    
    # Determinar estado atual
    analysis_status = kb.analysis_status
    print(f"🔍 [PERFIL_VIEW] Status da análise: {analysis_status}", flush=True)
    
    # ESTADO 4: Modo Edição (Análise Completa)
    if analysis_status == 'completed' and kb.n8n_analysis:
        print(f"🔍 [PERFIL_VIEW] Entrando no processamento de análise completa", flush=True)
        # Processar dados da análise N8N
        payload = kb.n8n_analysis.get('payload', [])
        print(f"🔍 [PERFIL_VIEW] Payload type: {type(payload)}, length: {len(payload) if isinstance(payload, list) else 'N/A'}", flush=True)
        
        if not payload or len(payload) == 0:
            print(f"❌ [PERFIL_VIEW] Payload vazio ou inválido", flush=True)
            messages.error(request, 'Dados de análise inválidos.')
            return redirect('knowledge:view')
        
        # Extrair campos analisados (payload[0] contém todos os campos)
        campos_raw = payload[0] if isinstance(payload, list) else {}
        print(f"🔍 [PERFIL_VIEW] campos_raw keys: {list(campos_raw.keys())[:5] if campos_raw else 'vazio'}...", flush=True)
        
        # Mapeamento: nome em português do payload N8N → nome em inglês (usado no frontend)
        # IMPORTANTE: Payload N8N usa nomes em português com underscore
        field_n8n_to_english = {
            'missao': 'mission',
            'visao': 'vision',
            'valores': 'values',
            'descricao_do_produto': 'description',
            'publico_alvo': 'target_audience',
            'publico_interno': 'internal_audience',
            'posicionamento': 'positioning',
            'proposta_de_valor': 'value_proposition',
            'diferenciais': 'differentials',
            'tom_de_voz': 'tone_of_voice',
            'tom_de_voz_interno': 'internal_tone_of_voice',
            'palavras_recomendadas': 'recommended_words',
            'palavras_a_evitar': 'words_to_avoid',
            'paleta_de_cores': 'palette_colors',
            'fontes': 'fonts',
            'logotipo': 'logo_files',
            'imagens_de_referencia': 'reference_images',
            'website': 'website_url',
            'redes_sociais': 'social_networks',
            'concorrencia': 'competitors',
            'frase_em_10_palavras': 'phrase_in_10_words',
            'sugestoes_estrategicas_de_ativacao_de_marca': 'strategic_suggestions_for_brand_activation'
        }
        
        # Mapear nomes técnicos para labels amigáveis
        field_labels = {
            'mission': 'Missão',
            'vision': 'Visão',
            'values': 'Valores & princípios',
            'description': 'Descrição do Produto/Serviço',
            'target_audience': 'Público externo',
            'internal_audience': 'Público interno',
            'internal_segments': 'Segmentos internos',
            'positioning': 'Posicionamento de mercado',
            'value_proposition': 'Proposta de valor',
            'differentials': 'Diferenciais competitivos',
            'tone_of_voice': 'Tom de voz externo',
            'internal_tone_of_voice': 'Tom de voz interno',
            'recommended_words': 'Palavras recomendadas',
            'words_to_avoid': 'Palavras a evitar',
            'palette_colors': 'Cores da identidade visual',
            'fonts': 'Tipografia da marca',
            'logo_files': 'Logotipos',
            'reference_images': 'Imagens de referência',
            'website_url': 'Site institucional',
            'social_networks': 'Redes sociais',
            'competitors': 'Concorrentes',
            'phrase_in_10_words': 'Frase em 10 Palavras',
            'strategic_suggestions_for_brand_activation': 'Sugestões Estratégicas'
        }
        
        # Ordem dos campos por bloco (nomes em português do payload N8N)
        blocos_estrutura = [
            {
                'numero': 1,
                'titulo': 'Identidade institucional',
                'campos': ['missao', 'visao', 'valores', 'descricao_do_produto']
            },
            {
                'numero': 2,
                'titulo': 'Públicos & segmentos',
                'campos': ['publico_alvo', 'publico_interno']
            },
            {
                'numero': 3,
                'titulo': 'Posicionamento & diferenciais',
                'campos': ['posicionamento', 'proposta_de_valor', 'diferenciais']
            },
            {
                'numero': 4,
                'titulo': 'Tom de voz & linguagem',
                'campos': ['tom_de_voz', 'tom_de_voz_interno', 'palavras_recomendadas', 'palavras_a_evitar']
            },
            {
                'numero': 5,
                'titulo': 'Identidade visual',
                'campos': ['paleta_de_cores', 'fontes', 'logotipo', 'imagens_de_referencia']
            },
            {
                'numero': 6,
                'titulo': 'Sites e redes sociais',
                'campos': ['website', 'redes_sociais', 'concorrencia']
            }
        ]
        
        # Definir estrutura de campos da Base de Conhecimento
        # IMPORTANTE: Exibir TODOS os campos, independente do payload N8N
        campos_kb_estrutura = [
            {
                'numero': 1,
                'titulo': 'Identidade institucional',
                'campos': [
                    {'nome': 'mission', 'label': 'Missão', 'campo_modelo': 'missao'},
                    {'nome': 'vision', 'label': 'Visão', 'campo_modelo': 'visao'},
                    {'nome': 'values', 'label': 'Valores & princípios', 'campo_modelo': 'valores'},
                    {'nome': 'description', 'label': 'Descrição do Produto/Serviço', 'campo_modelo': 'descricao_produto'},
                ]
            },
            {
                'numero': 2,
                'titulo': 'Públicos & segmentos',
                'campos': [
                    {'nome': 'target_audience', 'label': 'Público externo', 'campo_modelo': 'publico_externo'},
                    {'nome': 'internal_audience', 'label': 'Público interno', 'campo_modelo': 'publico_interno'},
                ]
            },
            {
                'numero': 3,
                'titulo': 'Posicionamento & diferenciais',
                'campos': [
                    {'nome': 'positioning', 'label': 'Posicionamento de mercado', 'campo_modelo': 'posicionamento'},
                    {'nome': 'value_proposition', 'label': 'Proposta de valor', 'campo_modelo': 'proposta_valor'},
                    {'nome': 'differentials', 'label': 'Diferenciais competitivos', 'campo_modelo': 'diferenciais'},
                ]
            },
            {
                'numero': 4,
                'titulo': 'Tom de voz & linguagem',
                'campos': [
                    {'nome': 'tone_of_voice', 'label': 'Tom de voz externo', 'campo_modelo': 'tom_voz_externo'},
                    {'nome': 'internal_tone_of_voice', 'label': 'Tom de voz interno', 'campo_modelo': 'tom_voz_interno'},
                    {'nome': 'recommended_words', 'label': 'Palavras recomendadas', 'campo_modelo': 'palavras_recomendadas'},
                    {'nome': 'words_to_avoid', 'label': 'Palavras a evitar', 'campo_modelo': 'palavras_evitar'},
                ]
            },
            {
                'numero': 5,
                'titulo': 'Identidade visual',
                'campos': [
                    {'nome': 'palette_colors', 'label': 'Cores da marca', 'campo_modelo': 'colors', 'readonly': True, 'type': 'colors'},
                    {'nome': 'fonts', 'label': 'Tipografia', 'campo_modelo': 'typography_settings', 'readonly': True, 'type': 'fonts'},
                    {'nome': 'logo_files', 'label': 'Logotipos', 'campo_modelo': 'logos', 'readonly': True, 'type': 'logos'},
                    {'nome': 'reference_images', 'label': 'Imagens de referência', 'campo_modelo': 'reference_images', 'readonly': True, 'type': 'references'},
                ]
            },
            {
                'numero': 6,
                'titulo': 'Sites e redes sociais',
                'campos': [
                    {'nome': 'website_url', 'label': 'Site institucional', 'campo_modelo': 'site_institucional', 'type': 'website', 'readonly': False, 'no_suggestions': True},
                    {'nome': 'social_networks', 'label': 'Redes sociais', 'campo_modelo': 'social_networks', 'type': 'social_networks', 'readonly': False, 'no_suggestions': True},
                    {'nome': 'competitors', 'label': 'Concorrentes', 'campo_modelo': 'concorrentes', 'type': 'competitors', 'readonly': False, 'no_suggestions': True},
                ]
            }
        ]
        
        # Processar campos agrupados por bloco
        blocos_analise = []
        stats = {'fraco': 0, 'medio': 0, 'bom': 0}
        
        for bloco in campos_kb_estrutura:
            campos_bloco = []
            
            for campo_def in bloco['campos']:
                campo_nome = campo_def['nome']
                campo_modelo = campo_def['campo_modelo']
                
                # 1. BUSCAR VALOR INFORMADO PELO USUÁRIO (do banco de dados)
                informado = ''
                colors_data = None  # Para campos de cores
                fonts_data = None  # Para campos de fontes
                logos_data = None  # Para campos de logos
                references_data = None  # Para imagens de referência
                social_networks_data = None  # Para redes sociais
                competitors_data = None  # Para concorrentes
                
                # Tratamento especial para campo colors (relacionamento)
                if campo_modelo == 'colors':
                    colors_queryset = kb.colors.all().order_by('order')
                    if colors_queryset.exists():
                        colors_data = list(colors_queryset.values('id', 'name', 'hex_code', 'color_type'))
                        informado = f"{colors_queryset.count()} cor(es) cadastrada(s)"
                
                # Tratamento especial para campo typography_settings (relacionamento)
                elif campo_modelo == 'typography_settings':
                    fonts_data = []
                    
                    # 1. Buscar Typography (configurações de tipografia)
                    fonts_queryset = kb.typography_settings.all().order_by('order')
                    for font in fonts_queryset:
                        font_dict = {
                            'id': font.id,
                            'usage': font.usage,
                            'font_source': font.font_source,
                        }
                        if font.font_source == 'google':
                            font_dict['font_name'] = font.google_font_name
                            font_dict['font_weight'] = font.google_font_weight
                        else:  # upload
                            if font.custom_font:
                                font_dict['font_name'] = font.custom_font.name
                                font_dict['custom_font_id'] = font.custom_font.id
                        fonts_data.append(font_dict)
                    
                    # 2. Buscar CustomFont (fontes customizadas independentes)
                    custom_fonts_queryset = kb.custom_fonts.all().order_by('-created_at')
                    for custom_font in custom_fonts_queryset:
                        # Verificar se já não está em Typography
                        already_in_typography = any(
                            f.get('custom_font_id') == custom_font.id 
                            for f in fonts_data
                        )
                        if not already_in_typography:
                            fonts_data.append({
                                'id': f'custom_{custom_font.id}',
                                'font_name': custom_font.name,
                                'usage': custom_font.font_type.upper(),
                                'font_source': 'upload',
                                'custom_font_id': custom_font.id,
                            })
                    
                    if fonts_data:
                        informado = f"{len(fonts_data)} fonte(s) cadastrada(s)"
                
                # Tratamento especial para campo logos (relacionamento)
                elif campo_modelo == 'logos':
                    from apps.knowledge.models import Logo
                    logos_queryset = kb.logos.all().order_by('-is_primary', 'logo_type')
                    if logos_queryset.exists():
                        logos_data = list(logos_queryset.values('id', 'name', 's3_key', 's3_url', 'logo_type', 'is_primary'))
                        informado = f"{logos_queryset.count()} logo(s) cadastrado(s)"
                
                # Tratamento especial para campo reference_images (relacionamento)
                elif campo_modelo == 'reference_images':
                    from apps.knowledge.models import ReferenceImage
                    references_queryset = kb.reference_images.all().order_by('-created_at')
                    if references_queryset.exists():
                        references_data = list(references_queryset.values('id', 'title', 's3_key', 's3_url'))
                        informado = f"{references_queryset.count()} imagem(ns) de referência"
                
                # Tratamento especial para campo social_networks (relacionamento)
                elif campo_modelo == 'social_networks':
                    from apps.knowledge.models import SocialNetwork
                    socials_queryset = kb.social_networks.filter(is_active=True).order_by('order')
                    social_networks_data = {}
                    if socials_queryset.exists():
                        for social in socials_queryset:
                            social_networks_data[social.network_type] = social.url
                        informado = f"{socials_queryset.count()} rede(s) social(is) cadastrada(s)"
                
                # Tratamento especial para campo concorrentes (JSONField)
                elif campo_modelo == 'concorrentes':
                    competitors_data = kb.concorrentes if kb.concorrentes else []
                    if competitors_data and isinstance(competitors_data, list):
                        informado = f"{len(competitors_data)} concorrente(s) cadastrado(s)"
                
                elif hasattr(kb, campo_modelo):
                    valor_banco = getattr(kb, campo_modelo, '')
                    if valor_banco:
                        if isinstance(valor_banco, list):
                            informado = ', '.join(str(i) for i in valor_banco)
                        elif isinstance(valor_banco, dict):
                            informado = json.dumps(valor_banco, ensure_ascii=False, indent=2)
                        else:
                            informado = str(valor_banco)
                
                # 2. BUSCAR DADOS DO PAYLOAD N8N (se existir)
                status = ''
                avaliacao = ''
                sugestao = ''
                
                # Tentar encontrar no payload (pode estar em PT ou EN)
                campo_data = None
                for possivel_nome in [campo_nome, campo_modelo, campo_def.get('nome_pt', '')]:
                    if possivel_nome and possivel_nome in campos_raw:
                        campo_data = campos_raw[possivel_nome]
                        break
                
                if campo_data and isinstance(campo_data, dict):
                    # Buscar 'classificacao' (após merge seletivo) ou 'status' (primeira análise)
                    status = campo_data.get('classificacao', campo_data.get('status', ''))
                    avaliacao = campo_data.get('avaliacao', '')
                    
                    # Contar estatísticas
                    if status == 'fraco':
                        stats['fraco'] += 1
                    elif status == 'médio':
                        stats['medio'] += 1
                    elif status == 'bom':
                        stats['bom'] += 1
                    
                    # Buscar 'sugestao' (após merge seletivo) ou 'sugestao_do_agente_iamkt' (primeira análise)
                    sugestao_raw = campo_data.get('sugestao', campo_data.get('sugestao_do_agente_iamkt', ''))
                    if isinstance(sugestao_raw, list):
                        # Verificar se é lista de strings ou lista de objetos
                        if sugestao_raw and isinstance(sugestao_raw[0], dict):
                            # Lista de objetos (ex: fontes)
                            sugestao_parts = []
                            for item in sugestao_raw:
                                # Para fontes, exibir apenas o nome de forma amigável
                                if 'name' in item:
                                    sugestao_parts.append(f"• {item['name']}")
                                else:
                                    # Fallback: exibir todos os campos
                                    item_str = ', '.join(f"{k}: {v}" for k, v in item.items())
                                    sugestao_parts.append(f"• {item_str}")
                            sugestao = '\n'.join(sugestao_parts)
                        else:
                            # Lista de strings simples
                            sugestao = '\n'.join(f"• {s}" for s in sugestao_raw)
                    elif isinstance(sugestao_raw, dict):
                        # Formatar dict de forma mais legível
                        sugestao_parts = []
                        for key, value in sugestao_raw.items():
                            if isinstance(value, list):
                                sugestao_parts.append(f"**{key}:**")
                                for item in value:
                                    if isinstance(item, dict):
                                        # Para objetos aninhados (ex: fontes)
                                        item_str = ', '.join(f"{k}: {v}" for k, v in item.items())
                                        sugestao_parts.append(f"  • {item_str}")
                                    else:
                                        sugestao_parts.append(f"  • {item}")
                            else:
                                sugestao_parts.append(f"**{key}:** {value}")
                        sugestao = '\n'.join(sugestao_parts) if sugestao_parts else json.dumps(sugestao_raw, ensure_ascii=False, indent=2)
                    else:
                        sugestao = str(sugestao_raw) if sugestao_raw else ''
                
                # 3. ADICIONAR CAMPO AO BLOCO (sempre, mesmo sem dados N8N)
                campo_data_dict = {
                    'nome': campo_nome,
                    'label': campo_def['label'],
                    'status': status,
                    'informado': informado or 'Não informado',
                    'avaliacao': avaliacao,
                    'sugestao': sugestao,
                    'readonly': campo_def.get('readonly', False),  # Campos readonly não têm aceitar/rejeitar
                    'no_suggestions': campo_def.get('no_suggestions', False),  # Campos sem botões de sugestão
                    'type': campo_def.get('type', 'text')  # Tipo de campo (text, colors, etc)
                }
                
                # Adicionar dados especiais para campos de cores
                if colors_data is not None:
                    campo_data_dict['colors'] = colors_data
                
                # Adicionar dados especiais para campos de fontes
                if fonts_data is not None:
                    campo_data_dict['fonts'] = fonts_data
                
                # Adicionar dados especiais para campos de logos
                if logos_data is not None:
                    campo_data_dict['logos'] = logos_data
                
                # Adicionar dados especiais para imagens de referência
                if references_data is not None:
                    campo_data_dict['references'] = references_data
                
                # Adicionar dados especiais para redes sociais
                if 'social_networks_data' in locals() and social_networks_data:
                    campo_data_dict['social_networks_data'] = social_networks_data
                
                # Adicionar dados especiais para concorrentes
                if 'competitors_data' in locals() and competitors_data:
                    campo_data_dict['competitors_data'] = competitors_data
                
                campos_bloco.append(campo_data_dict)
            
            # Adicionar bloco (sempre, mesmo sem campos com sugestão)
            blocos_analise.append({
                'numero': bloco['numero'],
                'titulo': bloco['titulo'],
                'campos': campos_bloco
            })
        
        print(f"🔍 [PERFIL_VIEW] Total de blocos processados: {len(blocos_analise)}", flush=True)
        print(f"🔍 [PERFIL_VIEW] Stats: {stats}", flush=True)
        
        from apps.knowledge.models import Logo
        primary_logo = Logo.objects.filter(
            knowledge_base=kb,
            is_primary=True
        ).first()
        
        context = {
            'kb': kb,
            'analysis_status': analysis_status,
            'compilation_status': kb.compilation_status,
            'blocos_analise': blocos_analise,
            'stats': stats,
            'kb_onboarding_completed': kb.onboarding_completed if kb else False,
            'kb_suggestions_reviewed': kb.suggestions_reviewed if kb else False,
            'primary_logo': primary_logo,
        }
        
        print(f" [PERFIL_VIEW] Contexto criado - onboarding: {context['kb_onboarding_completed']}, suggestions: {context['kb_suggestions_reviewed']}", flush=True)
        
        return render(request, 'knowledge/perfil.html', context)
    
    # Outros estados: apenas passar status
    context = {
        'kb': kb,
        'analysis_status': analysis_status,
        'kb_onboarding_completed': kb.onboarding_completed if kb else False,
        'kb_suggestions_reviewed': kb.suggestions_reviewed if kb else False
    }
    
    print(f"✅ [PERFIL_VIEW] Contexto criado (outros estados) - onboarding: {context['kb_onboarding_completed']}, suggestions: {context['kb_suggestions_reviewed']}", flush=True)
    
    return render(request, 'knowledge/perfil.html', context)


@never_cache
@login_required
def perfil_visualizacao_view(request):
    """
    Página de Visualização do Perfil da Empresa (Modo Leitura)
    Exibe dados compilados retornados pelo N8N
    """
    # Buscar KnowledgeBase
    try:
        kb = KnowledgeBase.objects.for_request(request).first()
    except Exception:
        kb = None
    
    if not kb:
        messages.error(request, 'Base de Conhecimento não encontrada.')
        return redirect('knowledge:view')
    
    # Verificar se onboarding foi concluído
    if not kb.onboarding_completed:
        messages.warning(request, 'Complete o onboarding primeiro.')
        return redirect('knowledge:view')
    
    # Verificar se sugestões foram revisadas
    if not kb.suggestions_reviewed:
        messages.warning(request, 'Revise as sugestões primeiro.')
        return redirect('knowledge:perfil_view')
    
    # Buscar logo primário
    primary_logo = Logo.objects.filter(
        knowledge_base=kb,
        is_primary=True
    ).first()
    
    # Determinar estado da compilação
    compilation_status = kb.compilation_status
    
    # Transformar dados do N8N para formato do template
    compilation_data = {}
    if kb.n8n_compilation:
        n8n_data = kb.n8n_compilation
        
        # Mapear estrutura do N8N para estrutura do template
        compilation_data = {
            # Base consolidada - mapear de 'areas.base'
            'base_consolidada': n8n_data.get('areas', {}).get('base', {}),
            
            # Presença digital - mapear de 'areas.digital_presence'
            'presenca_digital': n8n_data.get('areas', {}).get('digital_presence', {}),
            
            # Identidade visual - mapear de 'areas.visual_identity'
            'identidade_visual': n8n_data.get('areas', {}).get('visual_identity', {}),
            
            # Avaliação - mapear de 'evaluation', 'scores', 'assessment_summary'
            'avaliacao': {
                'evaluation': n8n_data.get('evaluation'),
                'scores': n8n_data.get('scores', {}),
                'summary': n8n_data.get('assessment_summary', {})
            },
            
            # Melhorias - mapear de 'improvements_summary'
            'melhorias_summary': n8n_data.get('improvements_summary', {}),
            
            # Plano de marketing - mapear de 'marketing_plan_4w'
            'plano_marketing': n8n_data.get('marketing_plan_4w', []),
            
            # Lacunas - mapear de 'gaps'
            'lacunas': n8n_data.get('gaps', []),
            
            # Links verificados - mapear de 'link_checks'
            'links_verificados': n8n_data.get('link_checks', []),
        }
    
    # Preparar contexto
    context = {
        'kb': kb,
        'compilation_status': compilation_status,
        'primary_logo': primary_logo,
        'compilation_data': compilation_data,
    }
    
    return render(request, 'knowledge/perfil_visualizacao.html', context)
