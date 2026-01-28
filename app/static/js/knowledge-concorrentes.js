/**
 * CONCORRENTES.JS
 * Gerenciamento de concorrentes na Base de Conhecimento
 */

// Array para armazenar concorrentes
let concorrentes = [];

/**
 * Inicializa o gerenciador de concorrentes
 */
function initConcorrentes() {
  // Carregar concorrentes existentes do campo hidden
  const concorrentesData = document.getElementById('concorrentes_data');
  if (concorrentesData && concorrentesData.value) {
    try {
      const parsed = JSON.parse(concorrentesData.value);
      concorrentes = Array.isArray(parsed) ? parsed : [];
    } catch (e) {
      console.error('Erro ao parsear concorrentes:', e);
      concorrentes = [];
    }
  }
  
  // Renderizar lista inicial
  renderConcorrentes();
  
  // Adicionar listener para Enter nos inputs
  const nomeInput = document.getElementById('concorrente_nome');
  const urlInput = document.getElementById('concorrente_url');
  
  if (nomeInput) {
    nomeInput.addEventListener('keypress', function(e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        addConcorrente();
      }
    });
  }
  
  if (urlInput) {
    urlInput.addEventListener('keypress', function(e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        addConcorrente();
      }
    });
  }
}

/**
 * Adiciona um novo concorrente
 */
function addConcorrente() {
  const nomeInput = document.getElementById('concorrente_nome');
  const urlInput = document.getElementById('concorrente_url');
  
  if (!nomeInput) {
    console.error('Input de nome não encontrado');
    return;
  }
  
  const nome = nomeInput.value.trim();
  const url = urlInput ? urlInput.value.trim() : '';
  
  // Validação
  if (!nome) {
    alert('Por favor, informe o nome do concorrente');
    nomeInput.focus();
    return;
  }
  
  // Validar URL se fornecida
  if (url && !isValidUrl(url)) {
    alert('Por favor, informe uma URL válida (ex: https://exemplo.com)');
    if (urlInput) urlInput.focus();
    return;
  }
  
  // Verificar duplicatas (por nome)
  const existe = concorrentes.some(c => 
    c.nome.toLowerCase() === nome.toLowerCase()
  );
  
  if (existe) {
    alert('Este concorrente já foi adicionado');
    nomeInput.focus();
    return;
  }
  
  // Adicionar ao array
  concorrentes.push({
    nome: nome,
    url: url || ''
  });
  
  // Limpar inputs
  nomeInput.value = '';
  if (urlInput) urlInput.value = '';
  nomeInput.focus();
  
  // Atualizar UI e campo hidden
  renderConcorrentes();
  saveConcorrentes();
}

/**
 * Remove um concorrente pelo índice
 */
function removeConcorrente(index) {
  if (confirm('Deseja remover este concorrente?')) {
    concorrentes.splice(index, 1);
    renderConcorrentes();
    saveConcorrentes();
  }
}

/**
 * Renderiza a lista de concorrentes
 */
function renderConcorrentes() {
  const container = document.getElementById('concorrentes-list');
  if (!container) return;
  
  // Limpar container
  container.innerHTML = '';
  
  // Se não há concorrentes, mostrar mensagem
  if (concorrentes.length === 0) {
    container.innerHTML = `
      <div class="concorrentes-empty">
        Nenhum concorrente adicionado ainda
      </div>
    `;
    return;
  }
  
  // Renderizar cada concorrente
  concorrentes.forEach((concorrente, index) => {
    const item = document.createElement('div');
    item.className = 'concorrente-item';
    
    item.innerHTML = `
      <div class="concorrente-nome-display">${escapeHtml(concorrente.nome)}</div>
      <div class="concorrente-url-display">${escapeHtml(concorrente.url || 'Sem URL')}</div>
      <button 
        type="button" 
        class="btn-remove-item" 
        onclick="removeConcorrente(${index})"
        title="Remover concorrente"
      >
        Remover
      </button>
    `;
    
    container.appendChild(item);
  });
}

/**
 * Salva concorrentes no campo hidden
 */
function saveConcorrentes() {
  const hiddenField = document.getElementById('concorrentes_data');
  if (hiddenField) {
    hiddenField.value = JSON.stringify(concorrentes);
  }
}

/**
 * Valida URL
 */
function isValidUrl(string) {
  try {
    const url = new URL(string);
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch (_) {
    return false;
  }
}

/**
 * Escapa HTML para prevenir XSS
 */
function escapeHtml(text) {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  };
  return text.replace(/[&<>"']/g, m => map[m]);
}

// Logs de debug (apenas desenvolvimento)
if (window.location.hostname.includes('localhost') || window.location.hostname.includes('127.0.0.1')) {
  console.log('🔍 DEBUG knowledge-concorrentes.js carregado');
  console.log('- removeConcorrente:', typeof removeConcorrente !== 'undefined' ? '✅' : '❌');
  console.log('- addConcorrente:', typeof addConcorrente !== 'undefined' ? '✅' : '❌');
  console.log('- saveConcorrentes:', typeof saveConcorrentes !== 'undefined' ? '✅' : '❌');
  console.log('- renderConcorrentes:', typeof renderConcorrentes !== 'undefined' ? '✅' : '❌');
}

// Inicializar quando o DOM estiver pronto
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initConcorrentes);
} else {
  initConcorrentes();
}
