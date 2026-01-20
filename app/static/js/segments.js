/**
 * SEGMENTS.JS - Gerenciamento de Segmentos Internos
 * CRUD completo via AJAX com modal
 */

// Abrir modal para criar novo segmento
function openSegmentModal() {
    document.getElementById('segmentModalTitle').textContent = 'Novo Segmento Interno';
    document.getElementById('segmentForm').reset();
    document.getElementById('segment_id').value = '';
    document.getElementById('segmentModal').classList.remove('modal-hidden');
}

// Fechar modal
function closeSegmentModal() {
    document.getElementById('segmentModal').classList.add('modal-hidden');
    document.getElementById('segmentForm').reset();
}

// Editar segmento existente
async function editSegment(segmentId) {
    try {
        const response = await fetch(`/knowledge/segment/${segmentId}/`);
        if (!response.ok) throw new Error('Erro ao carregar segmento');
        
        const data = await response.json();
        
        document.getElementById('segmentModalTitle').textContent = 'Editar Segmento Interno';
        document.getElementById('segment_id').value = data.id;
        document.getElementById('segment_name').value = data.name;
        document.getElementById('segment_description').value = data.description || '';
        document.getElementById('segment_parent').value = data.parent || '';
        document.getElementById('segment_order').value = data.order;
        
        document.getElementById('segmentModal').classList.remove('modal-hidden');
    } catch (error) {
        console.error('Erro ao editar segmento:', error);
        if (window.toaster) {
            toaster.error('Erro ao carregar dados do segmento');
        }
    }
}

// Salvar segmento (criar ou atualizar)
async function saveSegment() {
    const form = document.getElementById('segmentForm');
    const segmentId = document.getElementById('segment_id').value;
    
    const formData = {
        name: document.getElementById('segment_name').value,
        description: document.getElementById('segment_description').value,
        parent: document.getElementById('segment_parent').value || null,
        order: parseInt(document.getElementById('segment_order').value) || 0,
    };
    
    // Validação
    if (!formData.name.trim()) {
        if (window.toaster) {
            toaster.error('Nome é obrigatório');
        }
        return;
    }
    
    try {
        const url = segmentId 
            ? `/knowledge/segment/${segmentId}/update/`
            : '/knowledge/segment/create/';
        
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            },
            body: JSON.stringify(formData),
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || 'Erro ao salvar segmento');
        }
        
        const data = await response.json();
        
        // Fechar modal e recarregar página
        closeSegmentModal();
        location.reload();
        
    } catch (error) {
        console.error('Erro ao salvar segmento:', error);
        if (window.toaster) {
            toaster.error(error.message || 'Erro ao salvar segmento');
        }
    }
}

// Toggle ativar/desativar segmento
async function toggleSegment(segmentId, activate) {
    const action = activate ? 'ativar' : 'desativar';
    
    try {
        const url = activate 
            ? `/knowledge/segment/${segmentId}/restore/`
            : `/knowledge/segment/${segmentId}/delete/`;
        
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
            },
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || `Erro ao ${action} segmento`);
        }
        
        const data = await response.json();
        
        // Mostrar toaster de sucesso
        if (window.toaster) {
            toaster.success(data.message || `Segmento ${activate ? 'ativado' : 'desativado'} com sucesso`);
        }
        
        // Atualizar UI sem recarregar página
        const segmentItem = document.querySelector(`.segment-item[data-segment-id="${segmentId}"]`);
        if (segmentItem) {
            // Atualizar classe do item
            if (activate) {
                segmentItem.classList.remove('segment-inactive');
                segmentItem.dataset.isActive = 'true';
            } else {
                segmentItem.classList.add('segment-inactive');
                segmentItem.dataset.isActive = 'false';
            }
            
            // Atualizar texto de status
            const statusText = segmentItem.querySelector('.segment-status-text');
            if (statusText) {
                statusText.textContent = activate ? 'Ativo' : 'Inativo';
            }
        }
        
    } catch (error) {
        console.error(`Erro ao ${action} segmento:`, error);
        
        // Reverter checkbox em caso de erro
        const segmentItem = document.querySelector(`.segment-item[data-segment-id="${segmentId}"]`);
        if (segmentItem) {
            const checkbox = segmentItem.querySelector('.toggle-switch input');
            if (checkbox) {
                checkbox.checked = !activate;
            }
        }
        
        if (window.toaster) {
            toaster.error(error.message || `Erro ao ${action} segmento`);
        } else {
            alert(error.message || `Erro ao ${action} segmento`);
        }
    }
}

// Desativar segmento (mantido para compatibilidade)
async function deleteSegment(segmentId) {
    return toggleSegment(segmentId, false);
}

// Obter CSRF token
function getCsrfToken() {
    const name = 'csrftoken';
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Fechar modal ao pressionar ESC
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeSegmentModal();
    }
});
