/**
 * TAGS.JS - Interface de Tags Editáveis
 * Para campos de lista (palavras recomendadas, palavras a evitar, etc)
 */

document.addEventListener('DOMContentLoaded', function() {
    // Inicializar todos os campos de tags
    initializeTagsFields();
});

function initializeTagsFields() {
    // Carregar tags dos data-attributes (sem textareas hidden)
    const tagsContainers = [
        { id: 'tags-recomendadas', field: 'palavras_recomendadas' },
        { id: 'tags-evitar', field: 'palavras_evitar' },
        { id: 'tags-fontes', field: 'fontes_confiaveis' },
        { id: 'tags-canais', field: 'canais_trends' },
        { id: 'tags-palavras-trends', field: 'palavras_chave_trends' }
    ];
    
    tagsContainers.forEach(({ id, field }) => {
        const container = document.getElementById(id);
        if (container) {
            const tagsData = container.dataset.tags;
            if (tagsData) {
                const tags = parseJSON(tagsData);
                // Para canais_trends, extrair apenas os nomes se for array de objetos
                if (field === 'canais_trends') {
                    const tagsSimples = tags.map(item => {
                        if (typeof item === 'object' && item.nome) {
                            return item.nome;
                        }
                        return item;
                    });
                    renderTags(id, tagsSimples, field);
                } else {
                    renderTags(id, tags, field);
                }
            }
        }
    });
    
    // Event listeners para inputs de tags
    document.querySelectorAll('.tag-input').forEach(input => {
        input.addEventListener('keydown', handleTagInput);
    });
}

function parseJSON(value) {
    if (!value || value.trim() === '') return [];
    try {
        const parsed = JSON.parse(value);
        return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
        console.warn('Erro ao parsear JSON:', e);
        return [];
    }
}

function renderTags(containerId, tags, fieldName) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    container.innerHTML = '';
    
    tags.forEach(tag => {
        const tagElement = createTagElement(tag, containerId, fieldName);
        container.appendChild(tagElement);
    });
}

function createTagElement(text, containerId, fieldName) {
    const tag = document.createElement('div');
    tag.className = 'tag-item';
    tag.innerHTML = `
        <span>${escapeHtml(text)}</span>
        <button type="button" class="tag-remove" onclick="removeTag(this, '${containerId}', '${fieldName}')">×</button>
    `;
    return tag;
}

function handleTagInput(e) {
    if (e.key === 'Enter') {
        e.preventDefault();
        
        const input = e.target;
        const value = input.value.trim();
        
        if (value === '') return;
        
        const targetId = input.dataset.target;
        const fieldName = input.closest('.tags-input-wrapper').dataset.field;
        
        addTag(value, targetId, fieldName);
        input.value = '';
    }
}

function addTag(text, containerId, fieldName) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    // Obter tags atuais
    const currentTags = getTagsFromContainer(container);
    
    // Evitar duplicatas
    if (currentTags.includes(text)) {
        return;
    }
    
    // Adicionar nova tag
    const tagElement = createTagElement(text, containerId, fieldName);
    container.appendChild(tagElement);
    
    // Atualizar textarea hidden
    updateHiddenField(containerId, fieldName);
}

function removeTag(button, containerId, fieldName) {
    const tagElement = button.closest('.tag-item');
    tagElement.classList.add('removing');
    
    setTimeout(() => {
        tagElement.remove();
        updateHiddenField(containerId, fieldName);
    }, 150);
}

function getTagsFromContainer(container) {
    const tags = [];
    container.querySelectorAll('.tag-item span').forEach(span => {
        tags.push(span.textContent);
    });
    return tags;
}

function updateHiddenField(containerId, fieldName) {
    const container = document.getElementById(containerId);
    
    if (!container) return;
    
    const tags = getTagsFromContainer(container);
    
    // Salvar via AJAX ao invés de textarea hidden
    saveTags(fieldName, tags);
}

async function saveTags(fieldName, tags) {
    try {
        const response = await fetch('/knowledge/save-tags/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            },
            body: JSON.stringify({
                field_name: fieldName,
                tags: tags
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || 'Erro ao salvar tags');
        }
        
        const data = await response.json();
        
        // Mostrar feedback discreto (opcional)
        if (window.toaster && tags.length > 0) {
            toaster.success(data.message, { duration: 2000 });
        }
        
    } catch (error) {
        console.error('Erro ao salvar tags:', error);
        if (window.toaster) {
            toaster.error(error.message || 'Erro ao salvar tags');
        }
    }
}

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

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Expor funções globalmente para uso inline
window.removeTag = removeTag;
