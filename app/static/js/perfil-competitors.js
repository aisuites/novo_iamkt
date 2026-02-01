/**
 * PERFIL-COMPETITORS.JS - Gerenciamento de Concorrentes no Perfil
 * Mesma lógica do knowledge-concorrentes.js adaptada para o Perfil
 */

let concorrenteIndexPerfil = 0;

/**
 * Adiciona uma nova linha de concorrente no Perfil
 */
function addConcorrenteLinePerfil(nome = '', url = '') {
    const container = document.getElementById('concorrentes-inputs-container-perfil');
    if (!container) return;
    
    // Remover https:// do URL para exibição (se presente)
    const urlDisplay = url ? url.replace(/^https?:\/\//, '') : '';
    
    const item = document.createElement('div');
    item.className = 'concorrente-item';
    item.dataset.index = concorrenteIndexPerfil;
    
    item.innerHTML = `
        <div class="concorrente-inputs-wrapper">
            <input type="text" 
                   class="concorrente-nome-input" 
                   data-index="${concorrenteIndexPerfil}"
                   value="${escapeHtmlPerfil(nome)}"
                   placeholder="Nome do concorrente"
                   required>
            <div class="website-field-wrapper">
                <span class="website-prefix">https://</span>
                <input type="text" 
                       class="concorrente-url-input" 
                       data-index="${concorrenteIndexPerfil}"
                       value="${escapeHtmlPerfil(urlDisplay)}"
                       placeholder="site-concorrente.com.br (opcional)">
            </div>
        </div>
        <button 
            type="button" 
            class="btn-remove-item" 
            onclick="removeConcorrenteLinePerfil(${concorrenteIndexPerfil})"
            title="Remover concorrente"
        >
            Remover
        </button>
    `;
    
    container.appendChild(item);
    
    // Adicionar listeners para marcar como editado
    const nomeInput = item.querySelector('.concorrente-nome-input');
    const urlInput = item.querySelector('.concorrente-url-input');
    
    if (nomeInput) {
        nomeInput.addEventListener('input', function() {
            syncConcorrentesPerfilToEditedFields();
        });
    }
    if (urlInput) {
        urlInput.addEventListener('input', function() {
            syncConcorrentesPerfilToEditedFields();
        });
    }
    
    concorrenteIndexPerfil++;
    syncConcorrentesPerfilToEditedFields();
}

/**
 * Remove uma linha de concorrente no Perfil
 */
async function removeConcorrenteLinePerfil(index) {
    const item = document.querySelector(`#concorrentes-inputs-container-perfil .concorrente-item[data-index="${index}"]`);
    if (!item) return;
    
    const nomeInput = item.querySelector('.concorrente-nome-input');
    const nome = nomeInput ? nomeInput.value.trim() : '';
    const mensagem = `Tem certeza que deseja remover ${nome ? `"${nome}"` : 'este concorrente'}?`;
    
    // Usar modal de confirmação
    if (window.confirmModal && typeof window.confirmModal.show === 'function') {
        const confirmed = await window.confirmModal.show(mensagem, 'Remover concorrente');
        if (confirmed) {
            item.classList.add('removing');
            setTimeout(() => {
                item.remove();
                syncConcorrentesPerfilToEditedFields();
            }, 200);
        }
    } else {
        // Fallback: confirmação nativa
        if (confirm(mensagem)) {
            item.classList.add('removing');
            setTimeout(() => {
                item.remove();
                syncConcorrentesPerfilToEditedFields();
            }, 200);
        }
    }
}

/**
 * Sincroniza concorrentes para editedFields (para salvamento no Perfil)
 */
function syncConcorrentesPerfilToEditedFields() {
    syncConcorrentesPerfil(true);
}

/**
 * Sincroniza array de concorrentes com o campo hidden e editedFields
 * @param {boolean} markAsEdited - Se true, marca como editado. Se false, apenas sincroniza.
 */
function syncConcorrentesPerfil(markAsEdited = true) {
    const container = document.getElementById('concorrentes-inputs-container-perfil');
    if (!container) return;
    
    const concorrentes = [];
    const items = container.querySelectorAll('.concorrente-item');
    
    items.forEach(item => {
        const nomeInput = item.querySelector('.concorrente-nome-input');
        const urlInput = item.querySelector('.concorrente-url-input');
        
        if (nomeInput && nomeInput.value.trim()) {
            let url = urlInput ? urlInput.value.trim() : '';
            
            // Adicionar https:// se houver URL e não começar com http
            if (url && !url.startsWith('http://') && !url.startsWith('https://')) {
                url = `https://${url}`;
            }
            
            concorrentes.push({
                nome: nomeInput.value.trim(),
                url: url || ''
            });
        }
    });
    
    // Atualizar campo hidden
    const hiddenField = document.getElementById('concorrentes_data_perfil');
    if (hiddenField) {
        hiddenField.value = JSON.stringify(concorrentes);
    }
    
    // Adicionar ao editedFields APENAS se markAsEdited for true
    if (markAsEdited && window.editedFields) {
        window.editedFields['competitors'] = JSON.stringify(concorrentes);
        
        // Atualizar contador
        if (window.updateCounter) {
            window.updateCounter();
        }
    }
    
    console.log(`✅ [PERFIL] Concorrentes sincronizados: ${concorrentes.length} item(ns)${markAsEdited ? ' (marcado como editado)' : ''}`);
}

/**
 * Inicializa concorrentes existentes no Perfil
 */
function initConcorrentesPerfil(competitorsData) {
    console.log('🔄 [PERFIL] initConcorrentesPerfil: Iniciando...', competitorsData);
    
    if (Array.isArray(competitorsData) && competitorsData.length > 0) {
        competitorsData.forEach((concorrente, index) => {
            console.log(`  [PERFIL] Carregando concorrente ${index + 1}: nome="${concorrente.nome}", url="${concorrente.url}"`);
            addConcorrenteLinePerfil(concorrente.nome || '', concorrente.url || '');
        });
        console.log(`✅ [PERFIL] ${competitorsData.length} concorrente(s) carregado(s)`);
        
        // Sincronizar campo hidden SEM marcar como editado (é apenas carregamento inicial)
        syncConcorrentesPerfil(false);
    } else {
        console.log('ℹ️ [PERFIL] Nenhum concorrente encontrado');
    }
}

/**
 * Escapa HTML para prevenir XSS
 */
function escapeHtmlPerfil(text) {
    if (!text) return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return String(text).replace(/[&<>"']/g, m => map[m]);
}

console.log('🔍 [PERFIL] perfil-competitors.js carregado');
