/**
 * UPLOADS.JS - Gerenciamento de Uploads (Logos e Imagens de Referência)
 * Mock para preparar integração futura com S3
 */

// Mock de upload para S3 (será substituído pela integração real)
function mockUploadToS3(file) {
    return new Promise((resolve) => {
        // Simular upload com delay
        setTimeout(() => {
            const mockUrl = URL.createObjectURL(file);
            resolve({
                success: true,
                url: mockUrl,
                key: `mock/${Date.now()}_${file.name}`,
                filename: file.name
            });
        }, 500);
    });
}

// Handle upload de logos
async function handleLogoUpload(event) {
    const files = event.target.files;
    if (!files || files.length === 0) return;
    
    const gallery = document.getElementById('logos-gallery');
    
    for (let file of files) {
        // Validar tipo de arquivo
        if (!file.type.match(/image\/(png|jpeg|svg\+xml)/)) {
            if (window.toaster) {
                toaster.error(`Arquivo ${file.name} não é um formato válido. Use PNG, JPG ou SVG.`);
            }
            continue;
        }
        
        // Validar tamanho (max 5MB)
        if (file.size > 5 * 1024 * 1024) {
            if (window.toaster) {
                toaster.error(`Arquivo ${file.name} é muito grande. Tamanho máximo: 5MB.`);
            }
            continue;
        }
        
        // Mock upload
        const result = await mockUploadToS3(file);
        
        if (result.success) {
            addLogoPreview(result.url, file.name, 'mock-' + Date.now());
        }
    }
    
    // Limpar input
    event.target.value = '';
}

// Adicionar preview de logo
function addLogoPreview(url, name, logoId) {
    const gallery = document.getElementById('logos-gallery');
    if (!gallery) return;
    
    const logoItem = document.createElement('div');
    logoItem.className = 'logo-preview-item';
    logoItem.dataset.logoId = logoId;
    
    logoItem.innerHTML = `
        <img src="${url}" alt="${name}">
        <div class="logo-preview-info">
            <span class="logo-preview-name">${name}</span>
            <span class="logo-preview-type">Novo</span>
        </div>
        <button type="button" class="btn-remove-logo" onclick="removeLogo('${logoId}')" title="Remover">
            ×
        </button>
        <input type="hidden" name="logos_novos[]" value="${url}|${name}">
    `;
    
    gallery.appendChild(logoItem);
}

// Remover logo
function removeLogo(logoId) {
    const logoItem = document.querySelector(`.logo-preview-item[data-logo-id="${logoId}"]`);
    if (!logoItem) return;
    
    if (confirm('Deseja remover este logo?')) {
        logoItem.classList.add('removing');
        setTimeout(() => logoItem.remove(), 200);
        
        // TODO: Quando S3 estiver integrado, fazer chamada para deletar arquivo
    }
}

// Handle upload de imagens de referência
async function handleReferenceUpload(event) {
    const files = event.target.files;
    if (!files || files.length === 0) return;
    
    const gallery = document.getElementById('references-gallery');
    
    for (let file of files) {
        // Validar tipo de arquivo
        if (!file.type.match(/image\/.*/)) {
            if (window.toaster) {
                toaster.error(`Arquivo ${file.name} não é uma imagem válida.`);
            }
            continue;
        }
        
        // Validar tamanho (max 10MB)
        if (file.size > 10 * 1024 * 1024) {
            if (window.toaster) {
                toaster.error(`Arquivo ${file.name} é muito grande. Tamanho máximo: 10MB.`);
            }
            continue;
        }
        
        // Mock upload
        const result = await mockUploadToS3(file);
        
        if (result.success) {
            addReferencePreview(result.url, file.name, 'mock-' + Date.now());
        }
    }
    
    // Limpar input
    event.target.value = '';
}

// Adicionar preview de imagem de referência
function addReferencePreview(url, title, refId) {
    const gallery = document.getElementById('references-gallery');
    if (!gallery) return;
    
    const refItem = document.createElement('div');
    refItem.className = 'reference-preview-item';
    refItem.dataset.refId = refId;
    
    refItem.innerHTML = `
        <img src="${url}" alt="${title}">
        <div class="reference-preview-overlay">
            <span class="reference-preview-title">${title}</span>
            <button type="button" class="btn-remove-reference" onclick="removeReference('${refId}')" title="Remover">
                ×
            </button>
        </div>
        <input type="hidden" name="referencias_novas[]" value="${url}|${title}">
    `;
    
    gallery.appendChild(refItem);
}

// Remover imagem de referência
function removeReference(refId) {
    const refItem = document.querySelector(`.reference-preview-item[data-ref-id="${refId}"]`);
    if (!refItem) return;
    
    if (confirm('Deseja remover esta imagem de referência?')) {
        refItem.classList.add('removing');
        setTimeout(() => refItem.remove(), 200);
        
        // TODO: Quando S3 estiver integrado, fazer chamada para deletar arquivo
    }
}

// Drag & Drop para logos
document.addEventListener('DOMContentLoaded', function() {
    const logoUploadArea = document.getElementById('logo-upload-area');
    const referenceUploadArea = document.getElementById('reference-upload-area');
    
    // Setup drag & drop para logos
    if (logoUploadArea) {
        setupDragAndDrop(logoUploadArea, 'logo-upload-input');
    }
    
    // Setup drag & drop para referências
    if (referenceUploadArea) {
        setupDragAndDrop(referenceUploadArea, 'reference-upload-input');
    }
});

// Configurar drag & drop
function setupDragAndDrop(area, inputId) {
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        area.addEventListener(eventName, preventDefaults, false);
    });
    
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    ['dragenter', 'dragover'].forEach(eventName => {
        area.addEventListener(eventName, () => {
            area.classList.add('drag-over');
        }, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        area.addEventListener(eventName, () => {
            area.classList.remove('drag-over');
        }, false);
    });
    
    area.addEventListener('drop', function(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        
        const input = document.getElementById(inputId);
        if (input) {
            input.files = files;
            input.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }, false);
}

// Expor funções globalmente
window.handleLogoUpload = handleLogoUpload;
window.removeLogo = removeLogo;
window.handleReferenceUpload = handleReferenceUpload;
window.removeReference = removeReference;
