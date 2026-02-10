from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
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
            # Buscar imagens do post (enviar s3_keys para usar com lazyload)
            post_images = post.images.all().order_by('order')
            imagens_keys = [img.s3_key for img in post_images if img.s3_key]
            
            # Calcular imageStatus baseado no status do post e se tem imagens
            if post.status == 'image_generating':
                image_status = 'generating'
            elif post.status == 'image_ready' or (imagens_keys and post.status in ['approved', 'pending']):
                image_status = 'ready'
            else:
                image_status = 'none'
            
            # Contar alterações de imagem
            image_changes = post.change_requests.filter(
                change_type='image',
                is_initial=False
            ).count()
            
            posts_json.append({
                'id': post.id,
                'title': post.title or '',
                'subtitle': post.subtitle or '',
                'caption': post.caption or '',
                'hashtags': list(post.hashtags) if post.hashtags else [],
                'cta': post.cta or '',
                'image_prompt': post.image_prompt or '',
                'status': post.status,
                'social_network': post.social_network,
                'rede': post.social_network,
                'formats': list(post.formats) if post.formats else [],
                'carrossel': bool(post.is_carousel),
                'qtdImagens': int(post.image_count) if post.is_carousel else 1,
                'created_at': post.created_at.isoformat() if post.created_at else '',
                'has_image': bool(post.has_image),
                'imagens': imagens_keys,
                'imageStatus': image_status,
                'imageChanges': image_changes,
                'revisoesRestantes': 3,
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
        'posts_webhook_url': '',  # TODO: Configurar webhook URL
    }
    
    return render(request, 'posts/posts_list.html', context)
