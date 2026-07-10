from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.conf import settings
from django.http import JsonResponse
from .models import Post


def _post_payload(post):
    """Dict de um post para o front (mesmo formato do INITIAL_POSTS embutido).
    Usado pela listagem e pelo endpoint post_json (vigia do botao Edicao
    Avancada: o transcritor grava _layout_elements DEPOIS do image_ready)."""
    # Buscar imagens do post (id + s3_key para lazyload + delete + edit-flag).
    # is_editable=True para a PostImage que e a "versao atual" composta
    # (s3_key == post.image_s3_key). So nessa o botao "Edicao Avancada"
    # aparece no front — abre o modal que sempre carrega a versao atual.
    current_main_key = (post.image_s3_key or '').strip()
    # Sem _layout_elements o editor NAO ABRE (overlay_not_ready) — o
    # botao so aparece quando ha elementos (posts simple ganham via
    # transcritor; arquetipos/local ja nascem com eles). Espelha o
    # _get_elements do overlay: designer_payload OU copy_payload.
    has_elements = bool(
        (post.designer_payload or {}).get('_layout_elements')
        or (post.copy_payload or {}).get('_layout_elements')
    )
    post_images = post.images.all().order_by('order')
    imagens_data = [
        {
            'id': img.id,
            's3_key': img.s3_key,
            'is_editable': (bool(current_main_key)
                            and img.s3_key == current_main_key
                            and has_elements),
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
    # Posts de TEMPLATE (arquetipos): portao com revisao por IA propria
    # (C1.4) — limites independentes por kind, contados no ctx.
    is_template = post.pipeline_used in ('todxs', 'vb', 'samsung')
    tpl_rev = {}
    if is_template:
        from apps.posts.tasks_archetype import TEMPLATE_REVISION_LIMIT
        _rev = (post.local_pipeline_context or {}).get('template_revisions') or {}
        tpl_rev = {
            'text': max(0, TEMPLATE_REVISION_LIMIT - int(_rev.get('text') or 0)),
            'image': max(0, TEMPLATE_REVISION_LIMIT - int(_rev.get('image') or 0)),
        }

    if post.pipeline_used == 'simple' or is_template:
        # template: image_prompt e a descricao REAL do fundo (vazio =
        # foto do usuario ou arquetipo solido -> sem IA de imagem)
        image_description_ptbr = (post.image_prompt or '').strip()
    else:
        image_description_ptbr = (post.visual_brief or '').strip()
        if not image_description_ptbr:
            sp = (post.copy_payload or {}).get('_strategic_payload') or {}
            image_description_ptbr = (
                (sp.get('visual_direction') or {}).get('image_style') or ''
            ).strip()

    return {
        'id': post.id,
        'title': post.title or '',
        'subtitle': post.subtitle or '',
        'caption': post.caption or '',
        'hashtags': list(post.hashtags) if post.hashtags else [],
        'cta': post.cta or '',
        'image_prompt': post.image_prompt or '',
        'image_description_ptbr': image_description_ptbr,
        'status': post.status,
        'lastError': (post.local_pipeline_context or {}).get('last_error', '') or '',
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
        # Portao de TEMPLATE (C1.4)
        'isTemplate': is_template,
        'aiImage': bool((post.image_prompt or '').strip()) if is_template else False,
        'tplRev': tpl_rev,
    }


@login_required
def post_json(request, post_id):
    """Snapshot JSON de UM post (mesmo shape da listagem). Usado pelo front
    para observar o is_editable virar apos o transcritor terminar."""
    post = get_object_or_404(
        Post, id=post_id, organization=request.user.organization)
    return JsonResponse({'success': True, 'post': _post_payload(post)})


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
            posts_json.append(_post_payload(post))
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
        # "Edição Avançada" é liberada POR ORG (flag no admin); a equipe
        # interna sempre vê. Não confundir com is_admin (pipeline/debug).
        'advanced_editor': bool(
            request.user.is_superuser
            or request.user.is_staff
            or getattr(request.organization, 'advanced_editor_enabled', False)
        ),
    }

    return render(request, 'posts/posts_list.html', context)
