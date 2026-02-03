/**
 * POSTS.JS - Página de Posts
 * Extraído de resumo.html e adaptado para padrão IAMKT
 * Data: 02/02/2026
 * Versão: 2026-02-02-20:42 (REBUILD COMPLETO)
 * 
 * ADAPTAÇÕES:
 * - Removido console.log → logger.debug()
 * - Removido confirm() → window.confirmModal
 * - Removido alert() → window.toaster
 * - Usando funções de utils.js (getCookie, etc)
 */

(function() {
  'use strict';
  
  // Identificador de versão para debug
  window.POSTS_JS_VERSION = '2026-02-02-20:42-REBUILD';

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

  /**
   * Obtém ID do servidor do post
   */
  function getServerId(post) {
    if (!post) return null;
    
    if (typeof post.serverId === 'number' && Number.isFinite(post.serverId)) {
      return post.serverId;
    }
    
    if (typeof post.id === 'number' && Number.isFinite(post.id)) {
      return post.id;
    }
    
    if (typeof post.id === 'string' && /^\d+$/.test(post.id)) {
      return parseInt(post.id, 10);
    }
    
    return null;
  }

  /**
   * Formata data e hora para exibição (DD/MM/YYYY às HH:MM)
   */
  function formatDateTime(dateStr) {
    const date = new Date(dateStr);
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    const hour = String(date.getHours()).padStart(2, '0');
    const minute = String(date.getMinutes()).padStart(2, '0');
    return `${day}/${month}/${year} às ${hour}:${minute}`;
  }

  /**
   * Formata data para chave de filtro (YYYY-MM-DD)
   */
  function formatDateKey(dateStr) {
    const date = new Date(dateStr);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  /**
   * Calcula prazo de entrega da imagem (3 dias úteis)
   */
  function calculateImageDeadline(createdAtStr) {
    const created = new Date(createdAtStr);
    
    // Função auxiliar: adicionar dias úteis (pula fim de semana)
    function addBusinessDays(date, days) {
      let result = new Date(date);
      let addedDays = 0;
      
      while (addedDays < days) {
        result.setDate(result.getDate() + 1);
        const dayOfWeek = result.getDay();
        
        // Se não é sábado (6) nem domingo (0)
        if (dayOfWeek !== 0 && dayOfWeek !== 6) {
          addedDays++;
        }
      }
      
      return result;
    }
    
    return addBusinessDays(created, 3);
  }

  /**
   * Formata prazo para exibição (DD/MM/YYYY)
   */
  function formatDeadline(date) {
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    return `${day}/${month}/${year}`;
  }

  /**
   * Verifica se deve mostrar banner de geração de imagem
   */
  function shouldShowImageGenerationBanner(post) {
    // Mostra banner se:
    // 1. Status é 'image_generating' OU imageStatus é 'generating' E
    // 2. Ainda não tem imagens
    return (post.status === 'image_generating' || post.imageStatus === 'generating') 
           && (!post.imagens || post.imagens.length === 0);
  }

  /**
   * Verifica se deve mostrar banner de geração de texto
   */
  function shouldShowTextGenerationBanner(post) {
    // Mostra banner se status é 'generating'
    return post.status === 'generating';
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

  // Estado global
  const postsState = {
    items: INITIAL_POSTS.slice(),
    filtered: [],
    page: 1,
    perPage: 1,
    filters: { date: '', status: 'all', search: '' },
    selectedId: null,
    restoredFromStorage: false
  };

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
   * Aplica filtros aos posts (retorna items filtrados)
   */
  function applyFilters() {
    const { date, status, search } = postsState.filters;
    let items = postsState.items.slice();
    
    // Filtro por data
    if (date) {
      items = items.filter(post => {
        const postDate = new Date(post.created_at).toISOString().split('T')[0];
        return postDate === date;
      });
    }
    
    // Filtro por status
    if (status && status !== 'all') {
      items = items.filter(post => post.status === status);
    }
    
    // Busca por título
    if (search) {
      const q = search.toLowerCase();
      items = items.filter(post => 
        (post.title || '').toLowerCase().includes(q) ||
        String(post.id).includes(q)
      );
    }
    
    postsState.filtered = items;
    return items;
  }

  // Event listeners para filtros
  dom.filtroStatus?.addEventListener('change', () => {
    postsState.filters.status = dom.filtroStatus.value;
    postsState.page = 1;
    renderPosts(true);
  });
  
  dom.filtroData?.addEventListener('change', () => {
    postsState.filters.date = dom.filtroData.value;
    postsState.page = 1;
    renderPosts(true);
  });
  
  dom.btnBuscar?.addEventListener('click', () => {
    postsState.filters.search = dom.filtroBusca?.value.trim() || '';
    postsState.page = 1;
    renderPosts(true);
  });
  
  dom.filtroBusca?.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      postsState.filters.search = dom.filtroBusca.value.trim();
      postsState.page = 1;
      renderPosts(true);
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
    
    renderPosts(true);
  });

  /**
   * Obtém post atual baseado na página
   */
  function getCurrentPost() {
    if (!postsState.filtered.length) return null;
    const index = Math.min(postsState.filtered.length - 1, Math.max(0, postsState.page - 1));
    return postsState.filtered[index];
  }

  /**
   * Atualiza detalhes do post
   */
  function updatePostDetails(post) {
    if (!post) return;
    
    const dom = window.postsDOM || {};
    
    // Banner de status de geração de texto (coluna esquerda)
    const bannerContainer = dom.postStatus?.parentElement?.parentElement;
    const existingTextBanner = bannerContainer?.querySelector('.post-text-status-banner');
    if (existingTextBanner) {
      existingTextBanner.remove();
    }
    
    // Mostrar banner apenas se status === 'generating'
    if (dom.postStatus && post.status === 'generating' && bannerContainer) {
      const textBanner = document.createElement('div');
      textBanner.className = 'post-text-status-banner';
      textBanner.innerHTML = `
        <span class="status-icon">🔄</span>
        <span class="status-text">Seu conteúdo será gerado em até 3 minutos.</span>
        <button type="button" class="btn btn-sm" onclick="window.location.reload()">Atualizar Status</button>
      `;
      bannerContainer.insertBefore(textBanner, dom.postStatus.parentElement);
    }
    
    // Status
    if (dom.postStatus) {
      const info = statusInfo[post.status] || statusInfo.pending;
      dom.postStatus.textContent = post.statusLabel || info.label;
      dom.postStatus.className = `status-pill ${info.className}`;
    }
    
    // Campos de texto
    if (dom.postTitulo) dom.postTitulo.textContent = post.title || '—';
    if (dom.postSubtitulo) dom.postSubtitulo.textContent = post.subtitle || '—';
    if (dom.postLegenda) dom.postLegenda.textContent = post.caption || '—';
    if (dom.postHashtags) dom.postHashtags.textContent = Array.isArray(post.hashtags) ? post.hashtags.join(' ') : (post.hashtags || '—');
    if (dom.postCTA) dom.postCTA.textContent = post.cta || '—';
    if (dom.postDescricaoImagem) dom.postDescricaoImagem.textContent = post.image_prompt || '—';
    
    // Revisões e data
    if (dom.postRevisoes) {
      const rev = typeof post.imageChanges === 'number' ? post.imageChanges : 0;
      const max = 1;
      dom.postRevisoes.textContent = `${rev}/${max}`;
    }
    
    if (dom.postDataCriacao && post.created_at) {
      dom.postDataCriacao.textContent = formatDateTime(post.created_at);
    }
  }

  /**
   * Atualiza área visual do post (imagens, galeria, banners)
   */
  function updatePostVisual(post) {
    if (!post || !dom.postImageFrame || !dom.postGallery) {
      return;
    }
    
    // Limpar containers
    dom.postImageFrame.innerHTML = '';
    dom.postGallery.innerHTML = '';
    dom.postGallery.hidden = true;
    if (dom.postImageActions) dom.postImageActions.innerHTML = '';
    
    // Remover banner existente
    const existingBanner = dom.postImageFrame.parentElement?.querySelector('.post-image-status-banner');
    if (existingBanner) {
      existingBanner.remove();
    }
    
    // Mostrar banner de geração de imagem se necessário
    if (shouldShowImageGenerationBanner(post)) {
      const banner = document.createElement('div');
      banner.className = 'post-image-status-banner';
      
      // Calcular prazo de entrega
      const deadline = calculateImageDeadline(post.created_at);
      const deadlineText = formatDeadline(deadline);
      
      banner.innerHTML = `
        <span class="status-icon">🔄</span>
        <span class="status-text">Sua imagem será gerada até ${deadlineText}</span>
        <button type="button" class="btn btn-sm" onclick="window.location.reload()">Atualizar Status</button>
      `;
      dom.postImageFrame.parentElement.insertBefore(banner, dom.postImageFrame);
    }
    
    // Controlar caixa de solicitação de alteração de imagem
    if (dom.imageRequestBox) dom.imageRequestBox.hidden = !post.imageRequestOpen;
    if (dom.imageRequestInput) {
      dom.imageRequestInput.classList.remove('invalid');
      dom.imageRequestInput.value = post.imageRequestOpen ? (post.pendingImageRequest || '') : '';
    }
    
    // Status 'agent' - Agente alterando
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
      
      // Mostrar imagem principal
      const img = document.createElement('img');
      img.src = post.imagens[index];
      img.alt = `Pré-visualização da imagem ${index + 1}`;
      dom.postImageFrame.appendChild(img);
      
      // Galeria de miniaturas (se houver múltiplas imagens)
      if (post.imagens.length > 1 && dom.postGallery) {
        dom.postGallery.hidden = false;
        post.imagens.forEach((url, idx) => {
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.className = 'gallery-thumb';
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
      
      // Ações da imagem
      if (dom.postImageActions) {
        if (post.imageRequestOpen) return;
        
        // Se atingiu limite de alterações
        if (post.imageChanges >= 1) {
          const badge = document.createElement('span');
          badge.className = 'badge-muted';
          badge.textContent = 'Limite de alterações de imagem atingido';
          dom.postImageActions.appendChild(badge);
        } else {
          // Botão de solicitar alteração
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
      return;
    }
    
    // Imagem gerando
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
   * Constrói botões de ação
   */
  function buildPostActions(post) {
    const actionsContainer = document.getElementById('postActions');
    if (!actionsContainer) return;
    
    actionsContainer.innerHTML = '';
    if (!post) return;
    
    // Status: generating - Mostrar badge
    if (post.status === 'generating') {
      const badge = document.createElement('span');
      badge.className = 'badge-muted';
      badge.textContent = 'Agente gerando conteúdo — aguarde';
      actionsContainer.appendChild(badge);
      return;
    }
    
    // Status: agent - Mostrar badge
    if (post.status === 'agent') {
      const badge = document.createElement('span');
      badge.className = 'badge-muted';
      badge.textContent = 'Agente alterando — aguarde';
      actionsContainer.appendChild(badge);
      return;
    }
    
    // Status: approved - Mostrar badge
    if (post.status === 'approved') {
      const badge = document.createElement('span');
      badge.className = 'badge-success';
      badge.textContent = '✓ Post aprovado';
      actionsContainer.appendChild(badge);
      return;
    }
    
    // Status: rejected - Mostrar badge
    if (post.status === 'rejected') {
      const badge = document.createElement('span');
      badge.className = 'badge-danger';
      badge.textContent = '✗ Post rejeitado';
      actionsContainer.appendChild(badge);
      return;
    }
    
    // Status: pending, image_generating ou image_ready - Mostrar botões
    if (post.status === 'pending' || post.status === 'image_generating' || post.status === 'image_ready') {
      // Botão Rejeitar
      const btnReject = document.createElement('button');
      btnReject.type = 'button';
      btnReject.className = 'btn btn-outline-danger';
      btnReject.textContent = 'Rejeitar';
      btnReject.addEventListener('click', () => rejectPost(post));
      
      // Botão Solicitar Alteração
      const btnRequest = document.createElement('button');
      btnRequest.type = 'button';
      btnRequest.className = 'btn btn-outline-secondary';
      btnRequest.textContent = 'Solicitar Alteração';
      btnRequest.addEventListener('click', () => {
        post.textRequestOpen = true;
        post.pendingTextRequest = '';
        updatePostDetails(post);
        requestAnimationFrame(() => dom.textRequestInput?.focus());
      });
      
      // Botão Editar
      const btnEdit = document.createElement('button');
      btnEdit.type = 'button';
      btnEdit.className = 'btn btn-outline-primary';
      btnEdit.textContent = 'Editar';
      btnEdit.addEventListener('click', () => openEditPostModal(post));
      
      // Botão Gerar Imagem (apenas se não tem imagem)
      if (!post.images || post.images.length === 0) {
        const btnGenerate = document.createElement('button');
        btnGenerate.type = 'button';
        btnGenerate.className = 'btn btn-primary';
        btnGenerate.textContent = 'Gerar Imagem';
        btnGenerate.addEventListener('click', () => startImageGeneration(post));
        
        actionsContainer.append(btnReject, btnRequest, btnEdit, btnGenerate);
      } else {
        // Botão Aprovar (se tem imagem)
        const btnApprove = document.createElement('button');
        btnApprove.type = 'button';
        btnApprove.className = 'btn btn-success';
        btnApprove.textContent = 'Aprovar';
        btnApprove.addEventListener('click', () => approvePost(post));
        
        actionsContainer.append(btnReject, btnRequest, btnEdit, btnApprove);
      }
    }
  }

  /**
   * Renderiza posts
   */
  function renderPosts(scrollIntoView = false) {
    const filtered = applyFilters();
    const total = filtered.length;

    if (!dom.postsPane) return;

    if (total === 0) {
      if (dom.postsEmpty) dom.postsEmpty.style.display = '';
      if (dom.postsMain) dom.postsMain.hidden = true;
      if (dom.postPagerInfo) {
        const msg = postsState.items.length && (postsState.filters.date || postsState.filters.search || postsState.filters.status !== 'all')
          ? 'Nenhum post corresponde aos filtros aplicados'
          : '0 posts';
        dom.postPagerInfo.textContent = msg;
      }
      if (dom.pagerButtons) dom.pagerButtons.innerHTML = '';
      return;
    }

    if (dom.postsEmpty) dom.postsEmpty.style.display = 'none';
    if (dom.postsMain) dom.postsMain.hidden = false;

    const totalPages = Math.max(1, Math.ceil(total / postsState.perPage));

    // Restaurar post selecionado após reload (apenas na primeira renderização)
    if (!postsState.restoredFromStorage) {
      postsState.restoredFromStorage = true;
      try {
        const savedPostId = localStorage.getItem('selectedPostId');
        if (savedPostId) {
          const postId = parseInt(savedPostId, 10);
          if (!isNaN(postId) && filtered.some(p => p.id === postId)) {
            postsState.selectedId = postId;
          }
        }
      } catch (e) {
        // Ignorar erro
      }
    }

    if (postsState.selectedId) {
      const selectedIndex = filtered.findIndex(item => item.id === postsState.selectedId);
      if (selectedIndex !== -1) {
        postsState.page = Math.floor(selectedIndex / postsState.perPage) + 1;
      } else {
        postsState.selectedId = null;
      }
    }

    postsState.page = Math.min(totalPages, Math.max(1, postsState.page));
    const startIndex = (postsState.page - 1) * postsState.perPage;
    let current = filtered[startIndex] || null;
    if (!current && filtered.length) {
      current = filtered[0];
      postsState.page = 1;
    }
    postsState.selectedId = current?.id || postsState.selectedId || null;
    
    // Salvar post selecionado no localStorage
    if (postsState.selectedId) {
      try {
        localStorage.setItem('selectedPostId', postsState.selectedId.toString());
      } catch (e) {
        // Ignorar erro
      }
    }

    updatePostDetails(current);
    updatePostVisual(current);
    buildPostActions(current);
    buildPagination(total, totalPages);

    if (scrollIntoView) {
      const offset = (window.app && window.app.stickyOffset) ? window.app.stickyOffset : 80;
      requestAnimationFrame(() => {
        const top = dom.postsPane.getBoundingClientRect().top + window.pageYOffset - offset;
        window.scrollTo({ top, behavior: 'smooth' });
      });
    }
  }

  /**
   * Constrói botões de paginação
   */
  function buildPagination(totalItems, totalPages) {
    if (!dom.pagerButtons || !dom.postPagerInfo) return;
    dom.postPagerInfo.textContent = `${postsState.page} de ${totalItems} ${totalItems === 1 ? 'post' : 'posts'}`;
    dom.pagerButtons.innerHTML = '';

    const windowSize = 10;
    const currentPage = postsState.page;
    const maxStart = Math.max(1, totalPages - windowSize + 1);
    let startPage = Math.min(Math.max(1, currentPage), maxStart);
    let endPage = Math.min(totalPages, startPage + windowSize - 1);

    const addButton = (label, page, disabled = false, extraClass = '') => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = label;
      if (extraClass) btn.classList.add(extraClass);
      btn.disabled = disabled;
      if (!disabled) {
        btn.addEventListener('click', () => {
          if (postsState.page === page) return;
          postsState.page = page;
          postsState.selectedId = null; // CRÍTICO: Limpa selectedId para não sobrescrever navegação manual
          renderPosts(true);
        });
      }
      dom.pagerButtons.appendChild(btn);
    };

    addButton('«', 1, currentPage === 1, 'nav-first');
    addButton('‹', Math.max(1, currentPage - 1), currentPage === 1, 'nav-prev');

    for (let page = startPage; page <= endPage; page += 1) {
      addButton(page, page, false, page === currentPage ? 'active' : '');
    }

    addButton('›', Math.min(totalPages, currentPage + 1), currentPage >= totalPages, 'nav-next');
    addButton('»', totalPages, currentPage >= totalPages, 'nav-last');
  }

  // ============================================================================
  // MODAL DE EDIÇÃO
  // ============================================================================

  let editingPostRef = null;

  /**
   * Reseta formulário de edição
   */
  function resetEditPostForm() {
    if (dom.formEditarPost) dom.formEditarPost.reset();
  }

  /**
   * Fecha modal de edição
   */
  function closeEditPostModal() {
    resetEditPostForm();
    editingPostRef = null;
    closeModal(dom.modalEditarPost);
  }

  /**
   * Abre modal de edição e preenche campos
   */
  function openEditPostModal(post) {
    if (!post || !dom.modalEditarPost) return;
    
    editingPostRef = post;
    
    // Preencher campos
    if (dom.editTitulo) dom.editTitulo.value = post.title || '';
    if (dom.editSubtitulo) dom.editSubtitulo.value = post.subtitle || '';
    if (dom.editLegenda) dom.editLegenda.value = post.caption || '';
    if (dom.editHashtags) dom.editHashtags.value = Array.isArray(post.hashtags) ? post.hashtags.join(' ') : (post.hashtags || '');
    if (dom.editCTA) dom.editCTA.value = post.cta || '';
    if (dom.editDescricaoImagem) dom.editDescricaoImagem.value = post.image_prompt || '';
    
    openModal(dom.modalEditarPost);
    requestAnimationFrame(() => dom.editTitulo?.focus());
  }

  // Event listener para submit do formulário de edição
  if (dom.formEditarPost) {
    dom.formEditarPost.addEventListener('submit', async (e) => {
      e.preventDefault();
      
      if (!editingPostRef) return;
      
      const serverId = getServerId(editingPostRef);
      if (!serverId) {
        window.toaster?.error('Não foi possível identificar o post selecionado.');
        return;
      }
      
      const payload = {
        title: dom.editTitulo?.value.trim() || '',
        subtitle: dom.editSubtitulo?.value.trim() || '',
        caption: dom.editLegenda?.value.trim() || '',
        hashtags: dom.editHashtags?.value.trim() || '',
        cta: dom.editCTA?.value.trim() || '',
        image_prompt: dom.editDescricaoImagem?.value.trim() || ''
      };
      
      try {
        const response = await postJSON(`/posts/${serverId}/edit/`, payload);
        
        if (response.success) {
          // Atualizar post local
          Object.assign(editingPostRef, payload);
          window.toaster?.success('Post editado com sucesso!');
          closeEditPostModal();
          renderPosts();
        } else {
          window.toaster?.error(response.error || 'Erro ao editar post');
        }
      } catch (error) {
        logger.error('Erro ao editar post:', error);
        window.toaster?.error('Erro ao editar post. Tente novamente.');
      }
    });
  }

  // ============================================================================
  // AÇÕES DE POSTS
  // ============================================================================

  /**
   * Rejeita um post
   */
  async function rejectPost(post) {
    const serverId = getServerId(post);
    if (!serverId) {
      window.toaster?.error('Não foi possível identificar o post selecionado.');
      return;
    }
    
    const confirmed = confirm('Tem certeza que deseja rejeitar este post?');
    if (!confirmed) return;
    
    try {
      const response = await postJSON(`/posts/${serverId}/reject/`, {});
      
      if (response.success) {
        post.status = 'rejected';
        post.statusLabel = 'Rejeitado';
        window.toaster?.success('Post rejeitado com sucesso!');
        renderPosts();
      } else {
        window.toaster?.error(response.error || 'Erro ao rejeitar post');
      }
    } catch (error) {
      logger.error('Erro ao rejeitar post:', error);
      window.toaster?.error('Erro ao rejeitar post. Tente novamente.');
    }
  }

  /**
   * Aprova um post
   */
  async function approvePost(post) {
    const serverId = getServerId(post);
    if (!serverId) {
      window.toaster?.error('Não foi possível identificar o post selecionado.');
      return;
    }
    
    const confirmed = confirm('Tem certeza que deseja aprovar este post?');
    if (!confirmed) return;
    
    try {
      const response = await postJSON(`/posts/${serverId}/approve/`, {});
      
      if (response.success) {
        post.status = 'approved';
        post.statusLabel = 'Aprovado';
        window.toaster?.success('Post aprovado com sucesso!');
        renderPosts();
      } else {
        window.toaster?.error(response.error || 'Erro ao aprovar post');
      }
    } catch (error) {
      logger.error('Erro ao aprovar post:', error);
      window.toaster?.error('Erro ao aprovar post. Tente novamente.');
    }
  }

  /**
   * Inicia geração de imagem para o post
   */
  async function startImageGeneration(post) {
    const serverId = getServerId(post);
    if (!serverId) {
      window.toaster?.error('Não foi possível identificar o post selecionado.');
      return;
    }
    
    const confirmed = confirm('Deseja gerar a imagem para este post?');
    if (!confirmed) return;
    
    try {
      const response = await postJSON(`/posts/${serverId}/generate-image/`, {});
      
      if (response.success) {
        post.status = 'image_generating';
        post.imageStatus = 'generating';
        post.statusLabel = 'Agente Gerando Imagem';
        window.toaster?.success('Geração de imagem iniciada!');
        renderPosts();
      } else {
        window.toaster?.error(response.error || 'Erro ao iniciar geração de imagem');
      }
    } catch (error) {
      logger.error('Erro ao gerar imagem:', error);
      window.toaster?.error('Erro ao gerar imagem. Tente novamente.');
    }
  }

  // ============================================================================
  // SOLICITAÇÕES DE ALTERAÇÃO
  // ============================================================================

  /**
   * Envia solicitação de alteração de texto
   */
  async function submitTextRequest(post, text) {
    const serverId = getServerId(post);
    if (!serverId) {
      window.toaster?.error('Não foi possível identificar o post selecionado.');
      return;
    }
    
    if (!text || !text.trim()) {
      if (dom.textRequestInput) {
        dom.textRequestInput.classList.add('invalid');
      }
      return;
    }
    
    try {
      const response = await postJSON(`/posts/${serverId}/request-text-change/`, {
        request: text.trim()
      });
      
      if (response.success) {
        post.status = 'agent';
        post.statusLabel = 'Agente Alterando';
        post.textRequestOpen = false;
        post.pendingTextRequest = '';
        window.toaster?.success('Solicitação enviada com sucesso!');
        renderPosts();
      } else {
        window.toaster?.error(response.error || 'Erro ao enviar solicitação');
      }
    } catch (error) {
      logger.error('Erro ao enviar solicitação de texto:', error);
      window.toaster?.error('Erro ao enviar solicitação. Tente novamente.');
    }
  }

  /**
   * Envia solicitação de alteração de imagem
   */
  async function submitImageRequest(post, text) {
    if (post.imageChanges >= 1) {
      window.toaster?.warning('Limite de alterações de imagem atingido');
      return;
    }
    
    const serverId = getServerId(post);
    if (!serverId) {
      window.toaster?.error('Não foi possível identificar o post selecionado.');
      return;
    }
    
    if (!text || !text.trim()) {
      if (dom.imageRequestInput) {
        dom.imageRequestInput.classList.add('invalid');
      }
      return;
    }
    
    try {
      const response = await postJSON(`/posts/${serverId}/request-image-change/`, {
        request: text.trim()
      });
      
      if (response.success) {
        post.imageStatus = 'generating';
        post.imageChanges = (post.imageChanges || 0) + 1;
        post.imageRequestOpen = false;
        post.pendingImageRequest = '';
        window.toaster?.success('Solicitação enviada com sucesso!');
        renderPosts();
      } else {
        window.toaster?.error(response.error || 'Erro ao enviar solicitação');
      }
    } catch (error) {
      logger.error('Erro ao enviar solicitação de imagem:', error);
      window.toaster?.error('Erro ao enviar solicitação. Tente novamente.');
    }
  }

  // Event listeners para solicitações de alteração
  document.addEventListener('click', (e) => {
    // Cancelar solicitação de texto
    if (e.target.closest('#btnCancelTextRequest')) {
      const current = getCurrentPost();
      if (current) {
        current.textRequestOpen = false;
        current.pendingTextRequest = '';
        updatePostDetails(current);
      }
    }
    
    // Enviar solicitação de texto
    if (e.target.closest('#btnSendTextRequest')) {
      const current = getCurrentPost();
      if (current && dom.textRequestInput) {
        submitTextRequest(current, dom.textRequestInput.value);
      }
    }
    
    // Cancelar solicitação de imagem
    if (e.target.closest('#btnCancelImageRequest')) {
      const current = getCurrentPost();
      if (current) {
        current.imageRequestOpen = false;
        current.pendingImageRequest = '';
        updatePostVisual(current);
      }
    }
    
    // Enviar solicitação de imagem
    if (e.target.closest('#btnSendImageRequest')) {
      const current = getCurrentPost();
      if (current && dom.imageRequestInput) {
        submitImageRequest(current, dom.imageRequestInput.value);
      }
    }
  });

  // ============================================================================
  // INICIALIZAÇÃO
  // ============================================================================

  // Verificar se temos posts
  if (!window.INITIAL_POSTS) {
    window.INITIAL_POSTS = [];
  }

  // Renderizar posts iniciais
  renderPosts();

})();
