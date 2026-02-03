/**
 * Posts Detail - Lógicas de Renderização e Interação
 * Adaptado de resumo.html - v2026.02.02
 */

(function() {
    'use strict';

    // Estado Global
    const postsState = {
        items: [],
        filtered: [],
        page: 1,
        perPage: 1, // 1 post por página
        selectedId: null,
        filters: {
            date: '',
            status: 'all',
            search: ''
        },
        restoredFromStorage: false
    };

    // Mapeamento de Status
    const statusInfo = {
        pending: { label: 'Pendente de Aprovação', className: 'is-pending' },
        generating: { label: 'Agente Gerando Conteúdo', className: 'is-generating' },
        approved: { label: 'Aprovado', className: 'is-approved' },
        image_generating: { label: 'Agente Gerando Imagem', className: 'is-image_generating' },
        delivered: { label: 'Entregue', className: 'is-delivered' },
        rejected: { label: 'Rejeitado', className: 'is-rejected' },
        agent: { label: 'Agente Alterando', className: 'is-agent' }
    };

    // DOM Elements
    const dom = {
        postsPane: document.getElementById('postsMain'),
        postsEmpty: document.getElementById('postsEmpty'),
        postsMain: document.getElementById('postsMain'),
        postDetails: document.getElementById('postDetails'),
        postVisual: document.getElementById('postVisual'),
        postStatus: document.getElementById('postStatus'),
        postTags: document.getElementById('postTags'),
        postTitulo: document.getElementById('postTitulo'),
        postSubtitulo: document.getElementById('postSubtitulo'),
        postLegenda: document.getElementById('postLegenda'),
        postHashtags: document.getElementById('postHashtags'),
        postCTA: document.getElementById('postCTA'),
        postDescricaoImagem: document.getElementById('postDescricaoImagem'),
        postRevisoes: document.getElementById('postRevisoes'),
        postDataCriacao: document.getElementById('postDataCriacao'),
        postActions: document.getElementById('postActions'),
        postImageFrame: document.getElementById('postImageFrame'),
        postGallery: document.getElementById('postGallery'),
        postImageActions: document.getElementById('postImageActions'),
        textRequestBox: document.getElementById('textRequestBox'),
        textRequestInput: document.getElementById('textRequestInput'),
        imageRequestBox: document.getElementById('imageRequestBox'),
        imageRequestInput: document.getElementById('imageRequestInput'),
        postPagerInfo: document.getElementById('postPagerInfo'),
        pagerButtons: document.getElementById('pagerButtons')
    };

    // CSRF Token
    const CSRF_TOKEN = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

    /**
     * Inicialização
     */
    function init() {
        console.log('🚀 Posts Detail JS inicializado');
        
        // Carregar posts iniciais do Django
        loadInitialPosts();
        
        // Event listeners para ações
        setupEventListeners();
        
        // Renderizar primeira vez
        if (postsState.items.length > 0) {
            renderPosts();
        }
    }

    /**
     * Carregar posts iniciais passados pelo Django
     */
    function loadInitialPosts() {
        // Posts são passados via template Django
        // Por enquanto, vamos trabalhar com o post atual da página
        const postElement = document.querySelector('[data-post-id]');
        if (postElement) {
            const postId = parseInt(postElement.dataset.postId);
            // Aqui você pode fazer fetch para carregar todos os posts
            // Por enquanto, trabalharemos com paginação do Django
        }
    }

    /**
     * Setup de Event Listeners
     */
    function setupEventListeners() {
        // Botões de ação de texto
        document.addEventListener('click', (e) => {
            const action = e.target.dataset.action;
            if (!action) return;

            switch(action) {
                case 'cancel-text-request':
                    cancelTextRequest();
                    break;
                case 'submit-text-request':
                    submitTextRequest();
                    break;
                case 'cancel-image-request':
                    cancelImageRequest();
                    break;
                case 'submit-image-request':
                    submitImageRequest();
                    break;
            }
        });
    }

    /**
     * Renderizar Posts
     */
    function renderPosts(scrollIntoView = false) {
        const post = getCurrentPost();
        
        if (!post) {
            if (dom.postsEmpty) dom.postsEmpty.style.display = '';
            if (dom.postsMain) dom.postsMain.style.display = 'none';
            return;
        }

        if (dom.postsEmpty) dom.postsEmpty.style.display = 'none';
        if (dom.postsMain) dom.postsMain.style.display = '';

        updatePostDetails(post);
        updatePostVisual(post);
        buildPostActions(post);
    }

    /**
     * Obter post atual
     */
    function getCurrentPost() {
        // Por enquanto, retorna null pois estamos usando paginação Django
        // Futuramente, implementar lógica de estado local
        return null;
    }

    /**
     * Atualizar detalhes do post (coluna esquerda)
     */
    function updatePostDetails(post) {
        if (!post) return;

        // Atualizar status pill
        if (dom.postStatus) {
            const info = statusInfo[post.status] || statusInfo.pending;
            dom.postStatus.textContent = post.statusLabel || info.label;
            dom.postStatus.className = `status-pill ${info.className}`;
        }

        // Banner de geração de texto
        updateTextGenerationBanner(post);

        // Atualizar tags
        if (dom.postTags) {
            dom.postTags.innerHTML = '';
            const tags = buildPostTags(post);
            tags.forEach(text => {
                const span = document.createElement('span');
                span.className = 'post-tag';
                span.textContent = text;
                dom.postTags.appendChild(span);
            });
        }

        // Atualizar campos de texto
        if (dom.postTitulo) dom.postTitulo.textContent = post.titulo || '—';
        if (dom.postSubtitulo) dom.postSubtitulo.textContent = post.subtitulo || '—';
        if (dom.postLegenda) dom.postLegenda.textContent = post.legenda || '—';
        if (dom.postHashtags) dom.postHashtags.textContent = (post.hashtags && post.hashtags.length) ? post.hashtags.join(' ') : '—';
        if (dom.postCTA) dom.postCTA.textContent = post.cta || '—';

        // Descrição da imagem com scroll para carrossel
        if (dom.postDescricaoImagem) {
            dom.postDescricaoImagem.textContent = post.descricaoImagem || post.descricao || '—';
            
            if (post.carrossel && post.qtdImagens > 1) {
                if (!dom.postDescricaoImagem.classList.contains('post-image-prompt')) {
                    dom.postDescricaoImagem.classList.add('post-image-prompt');
                }
            } else {
                dom.postDescricaoImagem.classList.remove('post-image-prompt');
            }
        }

        // Footer
        if (dom.postRevisoes) dom.postRevisoes.textContent = `Revisões restantes: ${Math.max(0, post.revisoesRestantes ?? 0)}`;
        if (dom.postDataCriacao) dom.postDataCriacao.textContent = `Data da criação: ${formatDateDisplay(post.createdAt)}`;

        // Caixa de solicitação de texto
        if (dom.textRequestBox) dom.textRequestBox.hidden = !post.textRequestOpen;
        if (dom.textRequestInput) {
            dom.textRequestInput.classList.remove('invalid');
            dom.textRequestInput.value = post.textRequestOpen ? (post.pendingTextRequest || '') : '';
        }
    }

    /**
     * Construir tags do post
     */
    function buildPostTags(post) {
        const tags = [];
        
        if (post.formats && post.formats.length) {
            post.formats.forEach(format => {
                tags.push(`${post.rede || 'Canal'} - ${format.toUpperCase()}`);
            });
        } else if (post.rede) {
            tags.push(post.rede);
        }
        
        if (post.carrossel) {
            const amount = Math.min(5, Math.max(2, Number(post.qtdImagens) || 2));
            tags.push(`CARROSSEL - ${amount} IMAGENS`);
        }
        
        return tags;
    }

    /**
     * Atualizar banner de geração de texto
     */
    function updateTextGenerationBanner(post) {
        const bannerContainer = dom.postStatus?.parentElement?.parentElement;
        const existingBanner = bannerContainer?.querySelector('.post-text-status-banner');
        
        if (existingBanner) {
            existingBanner.remove();
        }

        if (dom.postStatus && post.status === 'generating' && bannerContainer) {
            const banner = document.createElement('div');
            banner.className = 'post-text-status-banner';
            banner.innerHTML = `
                <span class="status-icon">🔄</span>
                <span class="status-text">Seu conteúdo será gerado em até 3 minutos.</span>
                <button type="button" class="btn btn-sm" onclick="window.location.reload()">Atualizar Status</button>
            `;
            bannerContainer.insertBefore(banner, dom.postStatus.parentElement);
        }
    }

    /**
     * Atualizar visual do post (coluna direita)
     */
    function updatePostVisual(post) {
        if (!post || !dom.postImageFrame) return;

        // Limpar frame
        dom.postImageFrame.innerHTML = '';
        if (dom.postGallery) {
            dom.postGallery.innerHTML = '';
            dom.postGallery.hidden = true;
        }
        if (dom.postImageActions) dom.postImageActions.innerHTML = '';

        // Banner de geração de imagem
        updateImageGenerationBanner(post);

        // Caixa de solicitação de imagem
        if (dom.imageRequestBox) dom.imageRequestBox.hidden = !post.imageRequestOpen;
        if (dom.imageRequestInput) {
            dom.imageRequestInput.classList.remove('invalid');
            dom.imageRequestInput.value = post.imageRequestOpen ? (post.pendingImageRequest || '') : '';
        }

        // Status: agent
        if (post.status === 'agent') {
            const span = document.createElement('span');
            span.className = 'placeholder';
            span.textContent = 'Agente alterando — aguarde';
            dom.postImageFrame.appendChild(span);
            return;
        }

        // Imagem pronta
        if (post.imageStatus === 'ready' && post.imagens && post.imagens.length) {
            const index = Math.max(0, Math.min(post.imagens.length - 1, post.activeImageIndex || 0));
            post.activeImageIndex = index;
            
            const img = document.createElement('img');
            img.src = post.imagens[index];
            img.alt = `Pré-visualização da imagem ${index + 1}`;
            dom.postImageFrame.appendChild(img);

            // Galeria para carrossel
            if (post.imagens.length > 1 && dom.postGallery) {
                dom.postGallery.hidden = false;
                post.imagens.forEach((url, idx) => {
                    const btn = document.createElement('button');
                    btn.type = 'button';
                    if (idx === index) btn.classList.add('active');
                    
                    const thumb = document.createElement('img');
                    thumb.src = url;
                    thumb.alt = `Miniatura ${idx + 1}`;
                    btn.appendChild(thumb);
                    
                    btn.addEventListener('click', () => {
                        post.activeImageIndex = idx;
                        updatePostVisual(post);
                    });
                    
                    dom.postGallery.appendChild(btn);
                });
            }

            // Ações de imagem
            buildImageActions(post);
            return;
        }

        // Gerando imagem
        if (post.imageStatus === 'generating') {
            const span = document.createElement('span');
            span.className = 'placeholder';
            span.textContent = 'Gerando imagem...';
            dom.postImageFrame.appendChild(span);
            return;
        }

        // Sem imagem
        const placeholder = document.createElement('span');
        placeholder.className = 'placeholder';
        placeholder.textContent = 'SEM IMAGEM GERADA';
        dom.postImageFrame.appendChild(placeholder);
    }

    /**
     * Atualizar banner de geração de imagem
     */
    function updateImageGenerationBanner(post) {
        const existingBanner = dom.postImageFrame.parentElement?.querySelector('.post-image-status-banner');
        if (existingBanner) {
            existingBanner.remove();
        }

        if (shouldShowImageGenerationBanner(post)) {
            const banner = document.createElement('div');
            banner.className = 'post-image-status-banner';
            
            const deadline = calculateImageDeadline(post.createdAt);
            const deadlineText = formatDeadline(deadline);
            
            banner.innerHTML = `
                <span class="status-icon">🔄</span>
                <span class="status-text">Sua imagem será gerada até ${deadlineText}</span>
                <button type="button" class="btn btn-sm" onclick="window.location.reload()">Atualizar Status</button>
            `;
            dom.postImageFrame.parentElement.insertBefore(banner, dom.postImageFrame);
        }
    }

    /**
     * Verificar se deve mostrar banner de geração de imagem
     */
    function shouldShowImageGenerationBanner(post) {
        return post.status === 'image_generating' || post.imageStatus === 'generating';
    }

    /**
     * Construir ações de imagem
     */
    function buildImageActions(post) {
        if (!dom.postImageActions || post.imageRequestOpen) return;

        if (post.imageChanges >= 1) {
            const badge = document.createElement('span');
            badge.className = 'badge-muted';
            badge.textContent = 'Limite de alterações de imagem atingido';
            dom.postImageActions.appendChild(badge);
        } else {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'btn';
            btn.textContent = 'Solicitar Alteração de imagem';
            btn.addEventListener('click', () => {
                post.imageRequestOpen = true;
                post.pendingImageRequest = '';
                updatePostVisual(post);
                requestAnimationFrame(() => dom.imageRequestInput?.focus());
            });
            dom.postImageActions.appendChild(btn);
        }
    }

    /**
     * Construir ações do post (botões dinâmicos)
     */
    function buildPostActions(post) {
        if (!dom.postActions) return;
        dom.postActions.innerHTML = '';
        if (!post) return;

        // Status: agent
        if (post.status === 'agent') {
            const badge = document.createElement('span');
            badge.className = 'badge-muted';
            badge.textContent = 'Agente alterando — aguarde';
            dom.postActions.appendChild(badge);
            return;
        }

        // Status: image_generating
        if (post.status === 'image_generating') {
            const badge = document.createElement('span');
            badge.className = 'badge-muted';
            badge.textContent = 'Gerando imagem — aguarde';
            dom.postActions.appendChild(badge);
            return;
        }

        // Status: rejected
        if (post.status === 'rejected') {
            const badge = document.createElement('span');
            badge.className = 'badge-muted';
            badge.textContent = 'Post rejeitado';
            dom.postActions.appendChild(badge);
            return;
        }

        // Status: pending
        if (post.status === 'pending') {
            if (!post.textRequestOpen) {
                const btnReject = createActionButton('Rejeitar', 'btn ghost danger', () => rejectPost(post));
                
                const btnRequest = createActionButton('Solicitar Alteração', 'btn ghost', () => {
                    if ((post.revisoesRestantes ?? 1) <= 0) return;
                    post.textRequestOpen = true;
                    post.pendingTextRequest = '';
                    renderPosts();
                    requestAnimationFrame(() => dom.textRequestInput?.focus());
                });
                
                if ((post.revisoesRestantes ?? 0) <= 0) {
                    btnRequest.disabled = true;
                    btnRequest.title = 'Limite de revisões atingido';
                }

                const btnEdit = createActionButton('Editar', 'btn ghost', () => openEditPostModal(post));
                const btnApprove = createActionButton('Gerar Imagem', 'btn', () => startImageGeneration(post));

                dom.postActions.append(btnReject, btnRequest, btnEdit, btnApprove);
                dom.textRequestBox.hidden = true;
                dom.imageRequestBox.hidden = true;
            }
            return;
        }

        // Status: approved + sem imagem
        if (post.status === 'approved' && post.imageStatus === 'none') {
            const btnGenerate = createActionButton('Gerar Imagem', 'btn', () => startImageGeneration(post));
            dom.postActions.appendChild(btnGenerate);
        }
    }

    /**
     * Criar botão de ação
     */
    function createActionButton(label, className, handler) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = className;
        btn.textContent = label;
        btn.addEventListener('click', handler);
        return btn;
    }

    /**
     * Cancelar solicitação de alteração de texto
     */
    function cancelTextRequest() {
        if (dom.textRequestBox) dom.textRequestBox.hidden = true;
        if (dom.textRequestInput) dom.textRequestInput.value = '';
    }

    /**
     * Enviar solicitação de alteração de texto
     */
    async function submitTextRequest() {
        const text = dom.textRequestInput?.value.trim();
        if (!text) {
            dom.textRequestInput?.classList.add('invalid');
            return;
        }

        const postId = dom.postStatus?.dataset.postId;
        if (!postId) {
            window.toaster?.error('Post não identificado');
            return;
        }

        try {
            const response = await fetch(`/posts/${postId}/request-text-change/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CSRF_TOKEN
                },
                body: JSON.stringify({ mensagem: text })
            });

            const data = await response.json();
            
            if (response.ok && data.success) {
                window.toaster?.success('Solicitação enviada! O agente irá processar em breve.');
                cancelTextRequest();
                setTimeout(() => window.location.reload(), 1500);
            } else {
                window.toaster?.error(data.error || 'Erro ao enviar solicitação');
            }
        } catch (error) {
            console.error('Erro:', error);
            window.toaster?.error('Erro ao enviar solicitação');
        }
    }

    /**
     * Cancelar solicitação de alteração de imagem
     */
    function cancelImageRequest() {
        if (dom.imageRequestBox) dom.imageRequestBox.hidden = true;
        if (dom.imageRequestInput) dom.imageRequestInput.value = '';
    }

    /**
     * Enviar solicitação de alteração de imagem
     */
    async function submitImageRequest() {
        const text = dom.imageRequestInput?.value.trim();
        if (!text) {
            dom.imageRequestInput?.classList.add('invalid');
            return;
        }

        const postId = dom.postStatus?.dataset.postId;
        if (!postId) {
            window.toaster?.error('Post não identificado');
            return;
        }

        try {
            const response = await fetch(`/posts/${postId}/request-image-change/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CSRF_TOKEN
                },
                body: JSON.stringify({ mensagem: text })
            });

            const data = await response.json();
            
            if (response.ok && data.success) {
                window.toaster?.success('Solicitação enviada! A imagem será regerada em breve.');
                cancelImageRequest();
                setTimeout(() => window.location.reload(), 1500);
            } else {
                window.toaster?.error(data.error || 'Erro ao enviar solicitação');
            }
        } catch (error) {
            console.error('Erro:', error);
            window.toaster?.error('Erro ao enviar solicitação');
        }
    }

    /**
     * Rejeitar post
     */
    async function rejectPost(post) {
        if (!confirm('Tem certeza que deseja rejeitar este post?')) return;
        
        const postId = dom.postStatus?.dataset.postId;
        if (!postId) {
            window.toaster?.error('Post não identificado');
            return;
        }

        try {
            const response = await fetch(`/posts/${postId}/reject/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CSRF_TOKEN
                },
                body: JSON.stringify({})
            });

            const data = await response.json();
            
            if (response.ok && data.success) {
                window.toaster?.success('Post rejeitado com sucesso!');
                setTimeout(() => window.location.reload(), 1500);
            } else {
                window.toaster?.error(data.error || 'Erro ao rejeitar post');
            }
        } catch (error) {
            console.error('Erro:', error);
            window.toaster?.error('Erro ao rejeitar post');
        }
    }

    /**
     * Iniciar geração de imagem
     */
    async function startImageGeneration(post) {
        const postId = dom.postStatus?.dataset.postId;
        if (!postId) {
            window.toaster?.error('Post não identificado');
            return;
        }

        try {
            window.toaster?.info('Iniciando geração de imagem...');
            
            const response = await fetch(`/posts/${postId}/generate-image/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CSRF_TOKEN
                },
                body: JSON.stringify({ mensagem: '' })
            });

            const data = await response.json();
            
            if (response.ok && data.success) {
                window.toaster?.success('Geração de imagem iniciada! Aguarde...');
                setTimeout(() => window.location.reload(), 1500);
            } else {
                window.toaster?.error(data.error || 'Erro ao iniciar geração');
            }
        } catch (error) {
            console.error('Erro:', error);
            window.toaster?.error('Erro ao iniciar geração de imagem');
        }
    }

    /**
     * Abrir modal de edição
     */
    function openEditPostModal(post) {
        console.log('✏️ Abrindo modal de edição para post:', post.id);
        // TODO: Implementar modal de edição
        window.toaster?.info('Modal de edição em desenvolvimento');
    }

    /**
     * Calcular prazo de entrega da imagem
     */
    function calculateImageDeadline(createdAtStr) {
        const created = new Date(createdAtStr);
        
        function addBusinessDays(date, days) {
            const result = new Date(date);
            let added = 0;
            while (added < days) {
                result.setDate(result.getDate() + 1);
                const dayOfWeek = result.getDay();
                if (dayOfWeek !== 0 && dayOfWeek !== 6) {
                    added++;
                }
            }
            return result;
        }
        
        function nextBusinessDay09(date) {
            const result = new Date(date);
            result.setDate(result.getDate() + 1);
            result.setHours(9, 0, 0, 0);
            
            while (result.getDay() === 0 || result.getDay() === 6) {
                result.setDate(result.getDate() + 1);
            }
            return result;
        }
        
        let startTime = new Date(created);
        const dayOfWeek = startTime.getDay();
        const hour = startTime.getHours();
        
        if (dayOfWeek === 0 || dayOfWeek === 6) {
            const daysToAdd = dayOfWeek === 0 ? 1 : 2;
            startTime.setDate(startTime.getDate() + daysToAdd);
            startTime.setHours(9, 0, 0, 0);
        } else if (hour < 9) {
            startTime.setHours(9, 0, 0, 0);
        } else if (hour >= 17) {
            startTime = nextBusinessDay09(startTime);
        }
        
        const deadline = new Date(startTime);
        deadline.setHours(deadline.getHours() + 6);
        
        if (startTime.getHours() >= 16) {
            const nextDay = addBusinessDays(startTime, 1);
            nextDay.setHours(15, 0, 0, 0);
            return nextDay;
        }
        
        if (deadline.getHours() > 17) {
            return nextBusinessDay09(startTime);
        }
        
        return deadline;
    }

    /**
     * Formatar prazo
     */
    function formatDeadline(date) {
        const day = String(date.getDate()).padStart(2, '0');
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const year = String(date.getFullYear()).slice(-2);
        const hour = String(date.getHours()).padStart(2, '0');
        const minute = String(date.getMinutes()).padStart(2, '0');
        return `${day}/${month}/${year} às ${hour}:${minute}`;
    }

    /**
     * Formatar data para exibição
     */
    function formatDateDisplay(dateStr) {
        if (!dateStr) return '—';
    } else {
        window.toaster?.error(data.error || 'Erro ao enviar solicitação');
    }
} catch (error) {
    console.error('Erro:', error);
    window.toaster?.error('Erro ao enviar solicitação');
}
}

/**
 * Rejeitar post
 */
async function rejectPost(post) {
    if (!confirm('Tem certeza que deseja rejeitar este post?')) return;
    
    const postId = dom.postStatus?.dataset.postId;
    if (!postId) {
        window.toaster?.error('Post não identificado');
        return;
    }

    try {
        const response = await fetch(`/posts/${postId}/reject/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': CSRF_TOKEN
            },
            body: JSON.stringify({})
        });

        const data = await response.json();
        
        if (response.ok && data.success) {
            window.toaster?.success('Post rejeitado com sucesso!');
            setTimeout(() => window.location.reload(), 1500);
        } else {
            window.toaster?.error(data.error || 'Erro ao rejeitar post');
        }
    } catch (error) {
        console.error('Erro:', error);
        window.toaster?.error('Erro ao rejeitar post');
    }
}

/**
 * Iniciar geração de imagem
 */
async function startImageGeneration(post) {
    const postId = dom.postStatus?.dataset.postId;
    if (!postId) {
        window.toaster?.error('Post não identificado');
        return;
    }

    try {
        window.toaster?.info('Iniciando geração de imagem...');
        
        const response = await fetch(`/posts/${postId}/generate-image/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': CSRF_TOKEN
            },
            body: JSON.stringify({ mensagem: '' })
        });

        const data = await response.json();
        
        if (response.ok && data.success) {
            window.toaster?.success('Geração de imagem iniciada! Aguarde...');
            setTimeout(() => window.location.reload(), 1500);
        } else {
            window.toaster?.error(data.error || 'Erro ao iniciar geração');
        }
    } catch (error) {
        console.error('Erro:', error);
        window.toaster?.error('Erro ao iniciar geração de imagem');
    }
}

/**
 * Abrir modal de edição
 */
function openEditPostModal(post) {
    console.log('✏️ Abrindo modal de edição para post:', post.id);
    // TODO: Implementar modal de edição
    window.toaster?.info('Modal de edição em desenvolvimento');
}

/**
 * Calcular prazo de entrega da imagem
 */
function calculateImageDeadline(createdAtStr) {
    const created = new Date(createdAtStr);
    
    function addBusinessDays(date, days) {
        const result = new Date(date);
        let added = 0;
        while (added < days) {
            result.setDate(result.getDate() + 1);
            const dayOfWeek = result.getDay();
            if (dayOfWeek !== 0 && dayOfWeek !== 6) {
                added++;
            }
        }
        return result;
    }
    
    function nextBusinessDay09(date) {
        const result = new Date(date);
        result.setDate(result.getDate() + 1);
        result.setHours(9, 0, 0, 0);
        
        while (result.getDay() === 0 || result.getDay() === 6) {
            result.setDate(result.getDate() + 1);
        }
        return result;
    }
    
    let startTime = new Date(created);
    const dayOfWeek = startTime.getDay();
    const hour = startTime.getHours();
    
    if (dayOfWeek === 0 || dayOfWeek === 6) {
        const daysToAdd = dayOfWeek === 0 ? 1 : 2;
        startTime.setDate(startTime.getDate() + daysToAdd);
        startTime.setHours(9, 0, 0, 0);
    } else if (hour < 9) {
        startTime.setHours(9, 0, 0, 0);
    } else if (hour >= 17) {
        startTime = nextBusinessDay09(startTime);
    }
    
    const deadline = new Date(startTime);
    deadline.setHours(deadline.getHours() + 6);
    
    if (startTime.getHours() >= 16) {
        const nextDay = addBusinessDays(startTime, 1);
        nextDay.setHours(15, 0, 0, 0);
        return nextDay;
    }
    
    if (deadline.getHours() > 17) {
        return nextBusinessDay09(startTime);
    }
    
    return deadline;
}

/**
 * Formatar prazo
 */
function formatDeadline(date) {
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = String(date.getFullYear()).slice(-2);
    const hour = String(date.getHours()).padStart(2, '0');
    const minute = String(date.getMinutes()).padStart(2, '0');
    return `${day}/${month}/${year} às ${hour}:${minute}`;
}

/**
 * Formatar data para exibição
 */
function formatDateDisplay(dateStr) {
    if (!dateStr) return '—';
    const date = new Date(dateStr);
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    const hour = String(date.getHours()).padStart(2, '0');
    const minute = String(date.getMinutes()).padStart(2, '0');
    return `${day}/${month}/${year} ${hour}:${minute}`;
}

/**
 * Inicialização
 */
function init() {
    setupEventListeners();
    console.log('✅ Posts Detail JS inicializado');
}

// Executar quando DOM estiver pronto
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
})();

/**
 * Configurar galeria de miniaturas (GLOBAL)
 */
window.setupPostGallery = function() {
    const gallery = document.getElementById('postGallery');
    if (!gallery) {
        console.log('⚠️ Galeria não encontrada');
        return;
    }

    const thumbButtons = gallery.querySelectorAll('.gallery-thumb');
    const mainImage = document.querySelector('.post-main-image');
    
    console.log('🖼️ Configurando galeria:', {
        gallery: !!gallery,
        thumbButtons: thumbButtons.length,
        mainImage: !!mainImage
    });
    
    if (!mainImage || thumbButtons.length === 0) {
        console.log('⚠️ Imagem principal ou miniaturas não encontradas');
        return;
    }

    thumbButtons.forEach((btn, index) => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const s3Key = this.dataset.s3Key;
            
            console.log(`🖱️ Clique na miniatura ${index + 1}, s3Key:`, s3Key);
            
            // Atualizar imagem principal
            mainImage.setAttribute('data-lazy-load', s3Key);
            mainImage.src = '#';
            
            // Recarregar imagem com lazyload
            if (window.imagePreviewLoader) {
                console.log('🔄 Recarregando imagem com lazyload');
                window.imagePreviewLoader.observe(mainImage);
            } else {
                console.log('⚠️ imagePreviewLoader não disponível');
            }
            
            // Atualizar estado ativo dos botões
            thumbButtons.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
        });
    });
    
    console.log('✅ Galeria configurada com sucesso');
};
