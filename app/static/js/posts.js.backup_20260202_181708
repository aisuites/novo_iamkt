/**
 * POSTS.JS - Página de Posts
 * Extraído de resumo.html e adaptado para padrão IAMKT
 * Data: 02/02/2026
 * 
 * ADAPTAÇÕES:
 * - Removido console.log → logger.debug()
 * - Removido confirm() → window.confirmModal
 * - Removido alert() → window.toaster
 * - Usando funções de utils.js (getCookie, etc)
 */

(function() {
  'use strict';

  // ============================================================================
  // CONFIGURAÇÃO E CONSTANTES
  // ============================================================================

  // URLs do backend (injetadas pelo Django template)
  const POSTS_WEBHOOK_URL = window.POSTS_WEBHOOK_URL || '';
  const CSRF_TOKEN = window.CSRF_TOKEN || '';

  // Dados iniciais (injetados pelo Django template)
  const INITIAL_POSTS = window.INITIAL_POSTS || [];
  const CURRENT_USER = window.CURRENT_USER || '';
  const ORGANIZATION_ID = window.ORGANIZATION_ID || 0;

  // Logging
  logger.debug('[POSTS] Inicializando página de posts');
  logger.debug('[POSTS] POSTS_WEBHOOK_URL:', POSTS_WEBHOOK_URL);
  logger.debug('[POSTS] CSRF_TOKEN:', CSRF_TOKEN ? 'Presente' : 'Ausente');

  // ============================================================================
  // UTILITÁRIOS
  // ============================================================================

  const $ = (selector, scope = document) => scope.querySelector(selector);
  const $$ = (selector, scope = document) => Array.from(scope.querySelectorAll(selector));
  const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

  /**
   * Faz requisição POST com JSON
   */
  async function postJSON(url, data) {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': CSRF_TOKEN,
        'Accept': 'application/json',
      },
      body: JSON.stringify(data)
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const errorMsg = errorData.error || 'HTTP ' + response.status;
      throw new Error(errorMsg);
    }

    return response.json();
  }

  /**
   * Gera ID único
   */
  function uid() {
    return 'p_' + Math.random().toString(36).slice(2, 10);
  }

  /**
   * Escapa HTML (já existe em utils.js, mas mantido para compatibilidade)
   */
  function escapeHtml(str) {
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
    return (str || '').replace(/[&<>"']/g, ch => map[ch]);
  }

  /**
   * Normaliza hashtags
   */
  function normalizeHashtags(value) {
    if (!value) return [];
    if (Array.isArray(value)) return value.filter(Boolean);
    return String(value)
      .split(/[,#\s]+/)
      .map(v => v.trim())
      .filter(Boolean)
      .map(v => (v.startsWith('#') ? v : '#' + v));
  }

  // ============================================================================
  // INFORMAÇÕES DE STATUS
  // ============================================================================

  const statusInfo = {
    pending: { label: 'Pendente de Aprovação', className: 'is-pending' },
    approved: { label: 'Aprovado', className: 'is-approved' },
    rejected: { label: 'Rejeitado', className: 'is-rejected' },
    agent: { label: 'Agente Alterando — Aguarde', className: 'is-agent' },
    generating: { label: 'Agente Gerando Conteúdo', className: 'is-agent' },
    image_generating: { label: 'Agente Gerando Imagem', className: 'is-agent' },
    image_ready: { label: 'Imagem Disponível', className: 'is-approved' }
  };

  // ============================================================================
  // ESTADO DA APLICAÇÃO
  // ============================================================================

  const postsState = {
    items: INITIAL_POSTS.slice(),
    filtered: [],
    page: 1,
    perPage: 1,
    filters: { date: '', status: 'all', search: '' },
    selectedId: null,
    restoredFromStorage: false
  };

  let editingPostRef = null;

  // Normalizar dados dos posts
  postsState.items.forEach(item => {
    if (!item) return;
    
    // Garantir serverId
    if (item.serverId === undefined || item.serverId === null) {
      if (typeof item.id === 'number' && Number.isFinite(item.id)) {
        item.serverId = item.id;
      } else if (typeof item.id === 'string' && /^\d+$/.test(item.id)) {
        item.serverId = Number(item.id);
      }
    }
    
    // Garantir imageChanges
    if (typeof item.imageChanges !== 'number') item.imageChanges = 0;
    
    // Garantir statusLabel
    if (!item.statusLabel && item.status) {
      item.statusLabel = (statusInfo[item.status]?.label) || '';
    }
  });

  // ============================================================================
  // REFERÊNCIAS DO DOM
  // ============================================================================

  const dom = {
    // Modais
    modals: $$('.posts-modal'),
    modalGerarPost: document.getElementById('modalGerarPost'),
    modalEditarPost: document.getElementById('modalEditarPost'),
    
    // Formulários
    formGerarPost: document.getElementById('formGerarPost'),
    formEditarPost: document.getElementById('formEditarPost'),
    
    // Campos do formulário Gerar Post
    redePost: document.getElementById('redePost'),
    temaPost: document.getElementById('temaPost'),
    temaContador: document.getElementById('temaContador'),
    formatOptions: document.getElementById('formatOptions'),
    carrosselToggle: document.getElementById('carrosselToggle'),
    carrosselQtyField: document.getElementById('carrosselQtyField'),
    carrosselQtyInput: document.getElementById('qtdImagens'),
    refImgs: document.getElementById('refImgs'),
    refImgsInfo: document.getElementById('refImgsInfo'),
    
    // Campos do formulário Editar Post
    editTitulo: document.getElementById('editTitulo'),
    editSubtitulo: document.getElementById('editSubtitulo'),
    editLegenda: document.getElementById('editLegenda'),
    editHashtags: document.getElementById('editHashtags'),
    editCTA: document.getElementById('editCTA'),
    editDescricaoImagem: document.getElementById('editDescricaoImagem'),
    
    // Filtros
    filtroStatus: document.getElementById('filtroStatus'),
    filtroData: document.getElementById('filtroData'),
    filtroBusca: document.getElementById('filtroBusca'),
    btnBuscar: document.getElementById('btnBuscarTitulo'),
    btnLimparFiltros: document.getElementById('btnLimparFiltros'),
    
    // Lista de posts
    postsPane: document.getElementById('tab-posts'),
    postsEmpty: document.getElementById('postsEmpty'),
    postsMain: document.getElementById('postsMain'),
    
    // Detalhes do post
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
    
    // Ações do post
    postActions: document.getElementById('postActions'),
    postImageActions: document.getElementById('postImageActions'),
    textRequestBox: document.getElementById('textRequestBox'),
    textRequestInput: document.getElementById('textRequestInput'),
    imageRequestBox: document.getElementById('imageRequestBox'),
    imageRequestInput: document.getElementById('imageRequestInput'),
    
    // Imagem do post
    postImageFrame: document.getElementById('postImageFrame'),
    postGallery: document.getElementById('postGallery'),
    
    // Paginação
    postPagerInfo: document.getElementById('postPagerInfo'),
    pagerButtons: document.getElementById('pagerButtons')
  };

  // ============================================================================
  // POPULAR DROPDOWN DE STATUS
  // ============================================================================

  if (dom.filtroStatus) {
    const statusOrder = ['pending', 'generating', 'image_generating', 'image_ready', 'approved', 'agent', 'rejected'];
    const options = ['<option value="all">Todos</option>'];
    
    statusOrder.forEach(code => {
      const info = statusInfo[code];
      if (info) {
        options.push(`<option value="${code}">${info.label}</option>`);
      }
    });
    
    dom.filtroStatus.innerHTML = options.join('');
  }

  // ============================================================================
  // GERENCIAMENTO DE MODAIS
  // ============================================================================

  /**
   * Abre modal
   */
  function openModal(id) {
    const modal = typeof id === 'string' ? document.getElementById(id) : id;
    if (modal) {
      modal.classList.add('open');
      modal.setAttribute('aria-hidden', 'false');
    }
  }

  /**
   * Fecha modal
   */
  function closeModal(target) {
    const modal = typeof target === 'string' ? document.getElementById(target) : target;
    if (modal) {
      modal.classList.remove('open');
      modal.setAttribute('aria-hidden', 'true');
    }
  }

  /**
   * Fecha modal de edição
   */
  function closeEditPostModal() {
    closeModal(dom.modalEditarPost);
    editingPostRef = null;
  }

  // Event listeners para abrir modais
  $$('[data-open]').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = btn.getAttribute('data-open');
      
      if (id === 'modalGerarPost') {
        resetGerarPostForm();
        updateTemaCounter();
      }
      
      openModal(id);
    });
  });

  // Event listeners para fechar modais
  $$('[data-close]').forEach(btn => {
    btn.addEventListener('click', () => closeModal(btn.closest('.posts-modal')));
  });

  // Fechar ao clicar fora do modal
  dom.modals.forEach(modal => {
    modal.addEventListener('click', event => {
      if (event.target === modal) closeModal(modal);
    });
  });

  // Event listeners específicos do modal de edição
  if (dom.modalEditarPost) {
    $$('[data-close]', dom.modalEditarPost).forEach(btn => {
      btn.addEventListener('click', () => closeEditPostModal());
    });
    
    dom.modalEditarPost.addEventListener('click', event => {
      if (event.target === dom.modalEditarPost) {
        closeEditPostModal();
      }
    });
  }

  // ============================================================================
  // FORMULÁRIO GERAR POST
  // ============================================================================

  /**
   * Atualiza contador de caracteres do tema
   */
  function updateTemaCounter() {
    if (!dom.temaPost || !dom.temaContador) return;
    const max = dom.temaPost.maxLength || 3000;
    dom.temaContador.textContent = `${dom.temaPost.value.length}/${max}`;
  }

  /**
   * Atualiza informação de arquivos de referência
   */
  function updateRefsInfo() {
    if (!dom.refImgs || !dom.refImgsInfo) return;
    const files = dom.refImgs.files ? Array.from(dom.refImgs.files) : [];
    const label = files.length
      ? `${files.length} ${files.length === 1 ? 'arquivo selecionado' : 'arquivos selecionados'}`
      : 'Nenhum arquivo selecionado';
    dom.refImgsInfo.textContent = `${label} — Máx. 5 imagens (.JPG ou .PNG)`;
  }

  /**
   * Define estado do carrossel
   */
  function setCarrossel(enabled) {
    if (!dom.carrosselToggle || !dom.carrosselQtyField) return;
    dom.carrosselToggle.classList.toggle('active', enabled);
    dom.carrosselToggle.setAttribute('aria-pressed', enabled ? 'true' : 'false');
    dom.carrosselQtyField.hidden = !enabled;
  }

  /**
   * Reseta formulário de gerar post
   */
  function resetGerarPostForm() {
    if (!dom.formGerarPost) return;
    
    dom.formGerarPost.reset();
    if (dom.refImgs) dom.refImgs.value = '';
    
    const feedRadio = dom.formatOptions?.querySelector('input[value="feed"]');
    if (feedRadio) feedRadio.checked = true;
    
    syncFormatUI();
    setCarrossel(false);
    
    if (dom.carrosselQtyInput) dom.carrosselQtyInput.value = '3';
    
    updateTemaCounter();
    updateRefsInfo();
  }

  /**
   * Preenche modal com dados de uma pauta
   */
  function prefillPostModal(data) {
    resetGerarPostForm();
    
    if (data?.rede && dom.redePost) dom.redePost.value = data.rede;
    
    if (data?.tema && dom.temaPost) {
      const max = dom.temaPost.maxLength || data.tema.length;
      dom.temaPost.value = data.tema.slice(0, max);
    }
    
    updateTemaCounter();

    const formatsPref = Array.isArray(data?.formatos) ? data.formatos.map(f => String(f).toLowerCase()) : [];
    const feedRadio = dom.formatOptions?.querySelector('input[value="feed"]');
    const storiesRadio = dom.formatOptions?.querySelector('input[value="stories"]');
    const bothRadio = dom.formatOptions?.querySelector('input[value="both"]');
    
    if (feedRadio && storiesRadio && bothRadio) {
      if (formatsPref.includes('feed') && formatsPref.includes('stories')) {
        bothRadio.checked = true;
      } else if (formatsPref.includes('stories')) {
        storiesRadio.checked = true;
      } else {
        feedRadio.checked = true;
      }
    }
    
    syncFormatUI();
  }

  // Event listener para contador de tema
  dom.temaPost?.addEventListener('input', () => {
    const max = dom.temaPost.maxLength || 3000;
    if (dom.temaPost.value.length > max) {
      dom.temaPost.value = dom.temaPost.value.slice(0, max);
    }
    updateTemaCounter();
  });

  // Sincronizar UI de formato
  const formatRadios = dom.formatOptions ? Array.from(dom.formatOptions.querySelectorAll('input[type="radio"]')) : [];
  
  function syncFormatUI() {
    const checked = dom.formatOptions?.querySelector('input[type="radio"]:checked');
    const bothSelected = checked?.value === 'both';
    
    if (dom.formatOptions) {
      dom.formatOptions.querySelectorAll('.chip-choice').forEach(label => {
        const input = label.querySelector('input[type="radio"]');
        const isActive = !!(input && input.checked);
        label.classList.toggle('active', isActive);
      });
    }
    
    if (dom.carrosselToggle) {
      if (bothSelected) {
        dom.carrosselToggle.classList.add('chip-disabled');
        dom.carrosselToggle.setAttribute('aria-disabled', 'true');
        dom.carrosselToggle.disabled = true;
        setCarrossel(false);
      } else {
        dom.carrosselToggle.classList.remove('chip-disabled');
        dom.carrosselToggle.removeAttribute('aria-disabled');
        dom.carrosselToggle.disabled = false;
      }
    }
  }

  formatRadios.forEach(radio => {
    radio.addEventListener('change', () => {
      syncFormatUI();
    });
  });
  
  syncFormatUI();

  // CTA Toggle behavior
  const ctaOptions = document.querySelectorAll('.cta-toggle-option');
  ctaOptions.forEach(option => {
    option.addEventListener('click', () => {
      ctaOptions.forEach(opt => opt.classList.remove('active'));
      option.classList.add('active');
      const radio = option.querySelector('input[type="radio"]');
      if (radio) radio.checked = true;
    });
  });

  // Carrossel toggle
  dom.carrosselToggle?.addEventListener('click', () => {
    if (dom.carrosselToggle.disabled) return;
    const enabled = !dom.carrosselToggle.classList.contains('active');
    setCarrossel(enabled);
  });

  // Quantidade de imagens do carrossel
  $$('#carrosselQtyField button[data-step]').forEach(btn => {
    btn.addEventListener('click', () => {
      if (!dom.carrosselQtyInput) return;
      const min = Number(dom.carrosselQtyInput.min) || 2;
      const max = Number(dom.carrosselQtyInput.max) || 5;
      const step = Number(btn.dataset.step) || 0;
      let value = Number(dom.carrosselQtyInput.value) || min;
      value = Math.max(min, Math.min(max, value + step));
      dom.carrosselQtyInput.value = String(value);
    });
  });

  // Limitar imagens de referência a 5
  dom.refImgs?.addEventListener('change', () => {
    if (!dom.refImgs) return;
    const files = Array.from(dom.refImgs.files || []);
    if (files.length > 5) {
      const dt = new DataTransfer();
      files.slice(0, 5).forEach(file => dt.items.add(file));
      dom.refImgs.files = dt.files;
    }
    updateRefsInfo();
  });

  /**
   * Retorna formatos selecionados
   */
  function selectedFormats() {
    if (!dom.formatOptions) return ['feed'];
    const checked = dom.formatOptions.querySelector('input[type=\'radio\']:checked');
    const value = checked?.value || 'feed';
    if (value === 'both') {
      return ['feed', 'stories'];
    }
    return [value];
  }

  /**
   * Envia requisição para gerar post
   */
  async function requestPostFromAgent(payload) {
    if (!POSTS_WEBHOOK_URL) {
      throw new Error('URL de webhook não configurada');
    }

    const formData = new FormData();
    formData.append('rede', payload.rede || 'Instagram');
    formData.append('tema', payload.tema || '');
    formData.append('usuario', payload.usuario || '');
    formData.append('formatos', JSON.stringify(payload.formatos || []));
    formData.append('carrossel', payload.carrossel ? '1' : '0');
    formData.append('qtdImagens', String(payload.qtdImagens || 1));
    formData.append('ctaRequested', payload.ctaRequested ? '1' : '0');
    
    if (Array.isArray(payload.files)) {
      payload.files.forEach(file => {
        if (file) formData.append('referencias', file);
      });
    }

    logger.debug('[POSTS] Enviando post para:', POSTS_WEBHOOK_URL);
    
    const response = await fetch(POSTS_WEBHOOK_URL, {
      method: 'POST',
      headers: { 'X-CSRFToken': CSRF_TOKEN },
      body: formData,
    });

    logger.debug('[POSTS] Response status:', response.status, response.ok);

    if (!response.ok) {
      const errorText = await response.text();
      logger.error('[POSTS] Response error:', errorText);
      
      let errorMessage = 'Não foi possível gerar o post agora. Tente novamente.';
      try {
        const errorData = JSON.parse(errorText);
        if (errorData.error) {
          errorMessage = errorData.error;
        }
      } catch (e) {
        // Ignorar erro de parse
      }
      
      throw new Error(errorMessage);
    }

    return response.json();
  }

  // Submit do formulário Gerar Post
  // NOTA: Event listener desabilitado - agora é tratado por posts-modal.js
  /*
  if (dom.formGerarPost) {
    dom.formGerarPost.addEventListener('submit', async (e) => {
      e.preventDefault();

      const rede = dom.redePost?.value || 'Instagram';
      const tema = dom.temaPost?.value.trim() || '';
      const formatos = selectedFormats();
      const carrossel = dom.carrosselToggle?.classList.contains('active') || false;
      const qtdImagens = carrossel ? (Number(dom.carrosselQtyInput?.value) || 3) : 1;
      const ctaRadio = document.querySelector('input[name="ctaOption"]:checked');
      const ctaRequested = ctaRadio?.value === 'sim';
      const files = dom.refImgs?.files ? Array.from(dom.refImgs.files) : [];

      const payload = {
        rede,
        tema,
        usuario: CURRENT_USER,
        formatos,
        carrossel,
        qtdImagens,
        ctaRequested,
        files
      };

      try {
        const result = await requestPostFromAgent(payload);
        
        logger.debug('[POSTS] Post gerado com sucesso:', result);
        
        // Usar toaster ao invés de alert
        if (window.toaster) {
          window.toaster.success('Post enviado ao agente! Aguarde o processamento.');
        }
        
        closeModal('modalGerarPost');
        resetGerarPostForm();
        
        // Recarregar página após 2 segundos
        setTimeout(() => {
          window.location.reload();
        }, 2000);
        
      } catch (error) {
        logger.error('[POSTS] Erro ao gerar post:', error);
        
        // Usar toaster ao invés de alert
        if (window.toaster) {
          window.toaster.error(error.message || 'Erro ao gerar post. Tente novamente.');
        }
      }
    });
  }
  */

  // ============================================================================
  // FILTROS E PAGINAÇÃO
  // ============================================================================

  /**
   * Aplica filtros aos posts
   */
  function applyPostFilters() {
    let filtered = [...postsState.items];

    // Filtro por data
    if (dom.filtroData && dom.filtroData.value) {
      const selectedDate = dom.filtroData.value;
      filtered = filtered.filter(p => {
        const postDate = new Date(p.created_at).toISOString().split('T')[0];
        return postDate === selectedDate;
      });
    }

    // Filtro por status
    if (dom.filtroStatus && dom.filtroStatus.value && dom.filtroStatus.value !== 'all') {
      filtered = filtered.filter(p => p.status === dom.filtroStatus.value);
    }

    // Busca por título
    if (dom.filtroBusca && dom.filtroBusca.value.trim()) {
      const query = dom.filtroBusca.value.toLowerCase();
      filtered = filtered.filter(p =>
        (p.titulo || '').toLowerCase().includes(query) ||
        String(p.id).includes(query)
      );
    }

    postsState.filtered = filtered;
    postsState.page = 1;
    renderPosts();
  }

  // Event listeners para filtros
  dom.filtroStatus?.addEventListener('change', applyPostFilters);
  dom.filtroData?.addEventListener('change', applyPostFilters);
  dom.btnBuscar?.addEventListener('click', applyPostFilters);
  dom.filtroBusca?.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      applyPostFilters();
    }
  });

  // Limpar filtros
  dom.btnLimparFiltros?.addEventListener('click', () => {
    if (dom.filtroStatus) dom.filtroStatus.value = 'all';
    if (dom.filtroData) dom.filtroData.value = '';
    if (dom.filtroBusca) dom.filtroBusca.value = '';
    
    postsState.filters.status = 'all';
    postsState.filters.date = '';
    postsState.filters.search = '';
    postsState.page = 1;
    
    renderPosts();
  });

  /**
   * Renderiza posts
   */
  function renderPosts() {
    // TODO: Implementar renderização de posts
    logger.debug('[POSTS] Renderizando posts...');
  }

  /**
   * Renderiza paginação
   */
  function renderPostPagination() {
    // TODO: Implementar paginação
    logger.debug('[POSTS] Renderizando paginação...');
  }

  // ============================================================================
  // INICIALIZAÇÃO
  // ============================================================================

  logger.debug('[POSTS] Página de posts inicializada com sucesso');
  logger.debug('[POSTS] Total de posts:', postsState.items.length);

  // Aplicar filtros iniciais
  applyPostFilters();

})();
