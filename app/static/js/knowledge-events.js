/**
 * Knowledge Base - Event Listeners
 * Remove inline JavaScript (onclick, onchange) seguindo padrões do projeto
 */

document.addEventListener('DOMContentLoaded', () => {
    initSegmentEvents();
    initColorEvents();
    initFontEvents();
    initUploadEvents();
    initModalEvents();
    initTemplateEvents();
});

/**
 * SEGMENTOS INTERNOS
 */
function initSegmentEvents() {
    // Botão novo segmento
    const newSegmentBtn = document.querySelector('[data-action="new-segment"]');
    if (newSegmentBtn) {
        newSegmentBtn.addEventListener('click', () => {
            if (typeof openSegmentModal === 'function') {
                openSegmentModal();
            }
        });
    }

    // Toggle segments (checkbox)
    document.querySelectorAll('[data-action="toggle-segment"]').forEach(toggle => {
        toggle.addEventListener('change', (e) => {
            const segmentId = parseInt(e.target.dataset.segmentId);
            const isActive = e.target.checked;
            if (typeof toggleSegment === 'function') {
                toggleSegment(segmentId, isActive);
            }
        });
    });

    // Editar segmento
    document.querySelectorAll('[data-action="edit-segment"]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const segmentId = parseInt(e.currentTarget.dataset.segmentId);
            if (typeof editSegment === 'function') {
                editSegment(segmentId);
            }
        });
    });
}

/**
 * CORES
 */
function initColorEvents() {
    // Botão adicionar cor
    const addColorBtn = document.querySelector('[data-action="add-color"]');
    if (addColorBtn) {
        addColorBtn.addEventListener('click', () => {
            if (typeof addColor === 'function') {
                addColor();
            }
        });
    }

    // Remover cor (delegação de eventos)
    document.addEventListener('click', (e) => {
        if (e.target.closest('[data-action="remove-color"]')) {
            const btn = e.target.closest('[data-action="remove-color"]');
            if (typeof removeColor === 'function') {
                removeColor(btn);
            }
        }
    });
}

/**
 * FONTES
 */
function initFontEvents() {
    // Botão adicionar fonte
    const addFonteBtn = document.querySelector('[data-action="add-fonte"]');
    if (addFonteBtn) {
        addFonteBtn.addEventListener('click', () => {
            if (typeof addFonte === 'function') {
                addFonte();
            }
        });
    }

    // Remover fonte (delegação de eventos)
    document.addEventListener('click', (e) => {
        if (e.target.closest('[data-action="remove-fonte"]')) {
            const btn = e.target.closest('[data-action="remove-fonte"]');
            if (typeof removeFonte === 'function') {
                removeFonte(btn);
            }
        }
    });
}

/**
 * UPLOADS
 */
function initUploadEvents() {
    // Logo upload
    const logoInput = document.getElementById('logo-upload-input');
    const logoBtn = document.querySelector('[data-action="trigger-logo-upload"]');
    
    if (logoInput && logoBtn) {
        logoBtn.addEventListener('click', () => {
            logoInput.click();
        });
        
        logoInput.addEventListener('change', (e) => {
            if (typeof handleLogoUpload === 'function') {
                handleLogoUpload(e);
            }
        });
    }

    // Reference upload
    const refInput = document.getElementById('reference-upload-input');
    const refBtn = document.querySelector('[data-action="trigger-reference-upload"]');
    
    if (refInput && refBtn) {
        refBtn.addEventListener('click', () => {
            refInput.click();
        });
        
        refInput.addEventListener('change', (e) => {
            if (typeof handleReferenceUpload === 'function') {
                handleReferenceUpload(e);
            }
        });
    }

    // Remover logo (delegação de eventos)
    document.addEventListener('click', (e) => {
        if (e.target.closest('[data-action="remove-logo"]')) {
            const btn = e.target.closest('[data-action="remove-logo"]');
            const logoId = parseInt(btn.dataset.logoId);
            if (typeof removeLogo === 'function') {
                removeLogo(logoId);
            }
        }
    });

    // Remover referência (delegação de eventos)
    document.addEventListener('click', (e) => {
        if (e.target.closest('[data-action="remove-reference"]')) {
            const btn = e.target.closest('[data-action="remove-reference"]');
            const refId = parseInt(btn.dataset.refId);
            if (typeof removeReference === 'function') {
                removeReference(refId);
            }
        }
    });
}

/**
 * MODAL
 */
function initModalEvents() {
    // Fechar modal (overlay)
    const modalOverlay = document.querySelector('.modal-overlay');
    if (modalOverlay) {
        modalOverlay.addEventListener('click', () => {
            if (typeof closeSegmentModal === 'function') {
                closeSegmentModal();
            }
        });
    }

    // Fechar modal (botão X)
    const modalCloseBtn = document.querySelector('.modal-close');
    if (modalCloseBtn) {
        modalCloseBtn.addEventListener('click', () => {
            if (typeof closeSegmentModal === 'function') {
                closeSegmentModal();
            }
        });
    }
    
    // Botão cancelar no modal
    const cancelBtn = document.querySelector('[data-action="cancel-segment"]');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', () => {
            if (typeof closeSegmentModal === 'function') {
                closeSegmentModal();
            }
        });
    }
    
    // Botão salvar no modal
    const saveBtn = document.querySelector('[data-action="save-segment"]');
    if (saveBtn) {
        saveBtn.addEventListener('click', () => {
            if (typeof saveSegment === 'function') {
                saveSegment();
            }
        });
    }
}

/**
 * TEMPLATES
 */
function initTemplateEvents() {
    // Link templates (em desenvolvimento)
    const templateLink = document.querySelector('[data-action="open-templates"]');
    if (templateLink) {
        templateLink.addEventListener('click', (e) => {
            e.preventDefault();
            if (window.toaster) {
                toaster.info('Página de templates em desenvolvimento');
            }
        });
    }
}

/**
 * Função helper para mostrar notificações
 */
function showNotification(message, type = 'info') {
    if (window.toaster) {
        toaster[type](message);
    } else {
        console[type === 'error' ? 'error' : 'log'](message);
    }
}

// Exportar para uso global se necessário
window.showNotification = showNotification;
