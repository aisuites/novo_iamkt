"""
Views para gerenciamento de fontes no Perfil da Empresa
"""
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.db import transaction
from django.db import models
import json

from apps.knowledge.models import KnowledgeBase, Typography, CustomFont


@never_cache
@login_required
@require_POST
@csrf_exempt  # TODO: Remover após debug
def perfil_add_font(request):
    """
    Adicionar fonte à tipografia no Perfil
    """
    try:
        data = json.loads(request.body)
        print(f"🔍 [PERFIL_ADD_FONT] Payload recebido: {data}", flush=True)
        
        font_source = data.get('font_source', 'google')
        usage = data.get('usage', '').strip()
        
        print(f"🔍 [PERFIL_ADD_FONT] font_source={font_source}, usage={usage}", flush=True)
        
        if not usage:
            return JsonResponse({
                'success': False,
                'error': 'Uso da fonte é obrigatório'
            }, status=400)
        
        kb = KnowledgeBase.objects.for_request(request).first()
        if not kb:
            return JsonResponse({
                'success': False,
                'error': 'Base de conhecimento não encontrada'
            }, status=404)
        
        # Criar fonte
        with transaction.atomic():
            # Obter próxima ordem
            max_order = kb.typography_settings.aggregate(models.Max('order'))['order__max'] or 0
            
            if font_source == 'google':
                google_font_name = data.get('google_font_name', '').strip()
                google_font_weight = data.get('google_font_weight', '400')
                
                if not google_font_name:
                    return JsonResponse({
                        'success': False,
                        'error': 'Nome da fonte é obrigatório'
                    }, status=400)
                
                font = Typography.objects.create(
                    knowledge_base=kb,
                    usage=usage,
                    font_source='google',
                    google_font_name=google_font_name,
                    google_font_weight=google_font_weight,
                    google_font_url=f'https://fonts.googleapis.com/css2?family={google_font_name.replace(" ", "+")}:wght@{google_font_weight}&display=swap',
                    order=max_order + 1,
                    updated_by=request.user
                )
                
                print(f"✅ [PERFIL_ADD_FONT] Fonte Google adicionada: {google_font_name} (ID: {font.id})", flush=True)
                
            else:  # upload
                custom_font_id = data.get('custom_font_id')
                
                if not custom_font_id:
                    return JsonResponse({
                        'success': False,
                        'error': 'ID da fonte customizada é obrigatório'
                    }, status=400)
                
                # Buscar CustomFont
                try:
                    from apps.knowledge.models import CustomFont
                    custom_font = CustomFont.objects.get(id=custom_font_id, knowledge_base=kb)
                except CustomFont.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'error': 'Fonte customizada não encontrada'
                    }, status=404)
                
                font = Typography.objects.create(
                    knowledge_base=kb,
                    usage=usage,
                    font_source='upload',
                    custom_font=custom_font,
                    order=max_order + 1,
                    updated_by=request.user
                )
                
                print(f"✅ [PERFIL_ADD_FONT] Fonte Upload adicionada: {custom_font.name} (ID: {font.id})", flush=True)
            
            return JsonResponse({
                'success': True,
                'font_id': font.id,
                'message': 'Fonte adicionada com sucesso!'
            })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Dados inválidos'
        }, status=400)
    except Exception as e:
        print(f"❌ [PERFIL_ADD_FONT] Erro: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }, status=500)


@never_cache
@login_required
@require_POST
@csrf_exempt  # TODO: Remover após debug
def perfil_remove_font(request):
    """
    Remover fonte da tipografia no Perfil
    Se for fonte de upload, remove também o CustomFont e arquivo do S3
    """
    try:
        data = json.loads(request.body)
        font_id = data.get('font_id')
        
        if not font_id:
            return JsonResponse({
                'success': False,
                'error': 'ID da fonte não fornecido'
            }, status=400)
        
        kb = KnowledgeBase.objects.for_request(request).first()
        if not kb:
            return JsonResponse({
                'success': False,
                'error': 'Base de conhecimento não encontrada'
            }, status=404)
        
        # Buscar e remover fonte (suporta Typography ID numerico OU CustomFont 'custom_XX')
        font_id_str = str(font_id)

        # CustomFont standalone (ID como 'custom_83')
        if font_id_str.startswith('custom_'):
            try:
                custom_id = int(font_id_str.replace('custom_', ''))
                custom_font = kb.custom_fonts.get(id=custom_id)
                s3_key = custom_font.s3_key
                print(f"🗑️ [PERFIL_REMOVE_FONT] Deletando CustomFont standalone: {custom_font.name} (ID: {custom_id})", flush=True)
                try:
                    from apps.core.services.s3_service import S3Service
                    S3Service.delete_file(s3_key)
                except Exception as s3_error:
                    print(f"⚠️ [PERFIL_REMOVE_FONT] Erro S3: {s3_error}", flush=True)
                custom_font.delete()
                return JsonResponse({'success': True, 'message': 'Fonte removida com sucesso!'})
            except CustomFont.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Fonte não encontrada'}, status=404)
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)}, status=500)

        # Typography (ID numerico)
        try:
            font = kb.typography_settings.get(id=font_id)
            usage = font.usage
            font_source = font.font_source
            
            # Se for fonte de upload, deletar também o CustomFont e arquivo S3
            if font_source == 'upload' and font.custom_font:
                custom_font = font.custom_font
                s3_key = custom_font.s3_key
                custom_font_name = custom_font.name
                
                print(f"🗑️ [PERFIL_REMOVE_FONT] Deletando CustomFont: {custom_font_name} (ID: {custom_font.id})", flush=True)
                
                # Deletar arquivo do S3
                try:
                    from apps.core.services.s3_service import S3Service
                    S3Service.delete_file(s3_key)
                    print(f"✅ [PERFIL_REMOVE_FONT] Arquivo S3 deletado: {s3_key}", flush=True)
                except Exception as s3_error:
                    print(f"⚠️ [PERFIL_REMOVE_FONT] Erro ao deletar S3: {s3_error}", flush=True)
                
                # Deletar CustomFont
                custom_font.delete()
                print(f"✅ [PERFIL_REMOVE_FONT] CustomFont deletado: {custom_font_name}", flush=True)
            
            # Deletar Typography
            font.delete()
            
            print(f"✅ [PERFIL_REMOVE_FONT] Typography removido: {usage} (ID: {font_id})", flush=True)
            
            return JsonResponse({
                'success': True,
                'message': 'Fonte removida com sucesso!'
            })
        
        except Typography.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Fonte não encontrada'
            }, status=404)
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Dados inválidos'
        }, status=400)
    except Exception as e:
        print(f"❌ [PERFIL_REMOVE_FONT] Erro: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': f'Erro interno: {str(e)}'
        }, status=500)
