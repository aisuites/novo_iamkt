from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.conf import settings
from .models import Post


@login_required
def posts_list(request):
    """
    Lista de posts com filtros e paginação
    """
    # Filtrar posts da organização do usuário
    posts = Post.objects.filter(organization=request.user.organization)
    
    # Aplicar filtros
    filtros = {}
    
    # Filtro por data
    data = request.GET.get('data')
    if data:
        posts = posts.filter(created_at__date=data)
        filtros['data'] = data
    
    # Filtro por status
    status = request.GET.get('status')
    if status and status != 'all':
        posts = posts.filter(status=status)
        filtros['status'] = status
    
    # Filtro por busca (título)
    search = request.GET.get('search')
    if search:
        posts = posts.filter(title__icontains=search)
        filtros['search'] = search
    
    # Paginação - 1 post por vez (como no resumo.html)
    paginator = Paginator(posts, 1)  # 1 post por página
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Verificar se tem knowledge base
    knowledge_base = hasattr(request.user.organization, 'knowledge_base')
    
    # Preparar dados para JavaScript - ENVIAR TODOS OS POSTS (como no resumo.html)
    # O JavaScript faz a paginação no frontend
    import json
    
    posts_json = []
    for post in posts.prefetch_related('images', 'change_requests').order_by('-created_at'):
        try:
            # Buscar imagens do post (id + s3_key para lazyload + delete + edit-flag).
            # is_editable=True para a PostImage que e a "versao atual" composta
            # (s3_key == post.image_s3_key). So nessa o botao "Edicao Avancada"
            # aparece no front — abre o modal que sempre carrega a versao atual.
            current_main_key = (post.image_s3_key or '').strip()
            post_images = post.images.all().order_by('order')
            imagens_data = [
                {
                    'id': img.id,
                    's3_key': img.s3_key,
                    'is_editable': bool(current_main_key) and img.s3_key == current_main_key,
                }
                for img in post_images if img.s3_key
            ]

            # Calcular imageStatus baseado no status do post e se tem imagens
            if post.status == 'image_generating':
                image_status = 'generating'
            elif post.status == 'image_ready' or (imagens_data and post.status in ['approved', 'pending']):
                image_status = 'ready'
            else:
                image_status = 'none'
            
            # Contar alterações de imagem
            image_changes = post.change_requests.filter(
                change_type='image',
                is_initial=False
            ).count()

            # Obter limite de alterações da organização
            max_image_revisions = post.organization.max_image_revisions if post.organization else 1

            # Alterações de CENA ("Alterar Cena - IA") restantes (limite local)
            from apps.posts.tasks_simple import MAX_TEXT_REVISIONS
            text_changes = post.change_requests.filter(
                change_type='text', is_initial=False
            ).count()
            revisoes_texto_restantes = max(0, MAX_TEXT_REVISIONS - text_changes)

            # Descricao da imagem mostrada/aprovada no front.
            # Pipeline SIMPLES (novo): image_prompt e a CENA PT-BR aprovada pelo user.
            # Pipelines antigos (local/n8n): image_prompt pode ser prompt EN do Gemini
            # — nao deve ir pro user; mantemos visual_brief (PT-BR) como antes.
            if post.pipeline_used == 'simple':
                image_description_ptbr = (post.image_prompt or '').strip()
            else:
                image_description_ptbr = (post.visual_brief or '').strip()
                if not image_description_ptbr:
                    sp = (post.copy_payload or {}).get('_strategic_payload') or {}
                    image_description_ptbr = (
                        (sp.get('visual_direction') or {}).get('image_style') or ''
                    ).strip()

            posts_json.append({
                'id': post.id,
                'title': post.title or '',
                'subtitle': post.subtitle or '',
                'caption': post.caption or '',
                'hashtags': list(post.hashtags) if post.hashtags else [],
                'cta': post.cta or '',
                'image_prompt': post.image_prompt or '',
                'image_description_ptbr': image_description_ptbr,
                'status': post.status,
                'social_network': post.social_network,
                'rede': post.social_network,
                'formats': list(post.formats) if post.formats else [],
                'carrossel': bool(post.is_carousel),
                'qtdImagens': int(post.image_count) if post.is_carousel else 1,
                'created_at': post.created_at.isoformat() if post.created_at else '',
                'has_image': bool(post.has_image),
                'imagens': imagens_data,
                'imageStatus': image_status,
                'imageChanges': image_changes,
                'maxImageRevisions': max_image_revisions,
                'revisoesRestantes': 3,
                'revisoesTextoRestantes': revisoes_texto_restantes,
            })
        except Exception:
            continue
    
    # Converter para JSON string para passar ao template
    posts_json = json.dumps(posts_json)
    
    context = {
        'page_obj': page_obj,
        'filtros': filtros,
        'knowledge_base': knowledge_base,
        'posts_json': posts_json,
        'posts_webhook_url': settings.N8N_WEBHOOK_GERAR_POST,
        'enable_local_pipeline': settings.ENABLE_LOCAL_PIPELINE,
        # Equipe INTERNA = superuser ou staff. Controla o seletor de pipeline,
        # o botao "Edicao Avancada" (Pillow) e a area de Debug. NAO usar
        # profile=='admin': esse e o admin da empresa-CLIENTE (nao a equipe).
        'is_admin': bool(
            request.user.is_superuser
            or request.user.is_staff
        ),
    }

    return render(request, 'posts/posts_list.html', context)
