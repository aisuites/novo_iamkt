/**
 * UPLOADS-SIMPLE.JS - Upload Simplificado com Preview Local
 * Upload para S3 apenas ao salvar o formulário
 */

const PendingUploads = {logos: [], references: []};
const UploadConfig = {
    validators: {logos: null, references: null},
    endpoints: {
        logoUploadUrl: '/knowledge/logo/upload-url/',
        logoCreate: '/knowledge/logo/create/',
        referenceUploadUrl: '/knowledge/reference/upload-url/',
        referenceCreate: '/knowledge/reference/create/'
    }
};

async function handleLogoUpload(event) {
    const files = event.target.files;
    if (!files || files.length === 0) return;
    
    for (let file of files) {
        try {
            const validator = UploadConfig.validators.logos;
            const validation = await validator.validate(file);
            
            if (!validation.valid) {
                toaster.error(`${file.name}: ${validation.errors.join(', ')}`);
                continue;
            }
            
            const preview = await validator.generatePreview(file);
            const tempId = 'temp-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
            
            PendingUploads.logos.push({file: file, preview: preview.dataUrl, tempId: tempId, name: file.name});
            addLogoPreviewLocal(preview.dataUrl, file.name, tempId);
            toaster.success(`${file.name} adicionado. Salve o formulário para enviar.`);
        } catch (error) {
            toaster.error(`Erro: ${file.name}`);
        }
    }
    event.target.value = '';
}

function addLogoPreviewLocal(previewUrl, name, tempId) {
    const gallery = document.getElementById('logos-gallery');
    if (!gallery) return;
    
    const logoItem = document.createElement('div');
    logoItem.className = 'logo-preview-item logo-pending';
    logoItem.dataset.logoId = tempId;
    logoItem.innerHTML = `
        <img src="${previewUrl}" alt="${name}">
        <div class="logo-preview-info">
            <span class="logo-preview-name">${name}</span>
            <span class="logo-preview-type">Novo</span>
        </div>
        <button type="button" class="btn-remove-logo" onclick="removeLogoPending('${tempId}')" title="Remover">×</button>
    `;
    gallery.appendChild(logoItem);
}

function removeLogoPending(tempId) {
    const index = PendingUploads.logos.findIndex(item => item.tempId === tempId);
    if (index !== -1) PendingUploads.logos.splice(index, 1);
    
    const logoItem = document.querySelector(`.logo-preview-item[data-logo-id="${tempId}"]`);
    if (logoItem) logoItem.remove();
    toaster.info('Logo removido');
}

async function handleReferenceUpload(event) {
    const files = event.target.files;
    if (!files || files.length === 0) return;
    
    for (let file of files) {
        try {
            const validator = UploadConfig.validators.references;
            const validation = await validator.validate(file);
            
            if (!validation.valid) {
                toaster.error(`${file.name}: ${validation.errors.join(', ')}`);
                continue;
            }
            
            const preview = await validator.generatePreview(file);
            const tempId = 'temp-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
            
            PendingUploads.references.push({file: file, preview: preview.dataUrl, tempId: tempId, name: file.name});
            addReferencePreviewLocal(preview.dataUrl, file.name, tempId);
            toaster.success(`${file.name} adicionado. Salve o formulário para enviar.`);
        } catch (error) {
            toaster.error(`Erro: ${file.name}`);
        }
    }
    event.target.value = '';
}

function addReferencePreviewLocal(previewUrl, title, tempId) {
    const gallery = document.getElementById('references-gallery');
    if (!gallery) return;
    
    const refItem = document.createElement('div');
    refItem.className = 'reference-preview-item reference-pending';
    refItem.dataset.refId = tempId;
    refItem.innerHTML = `
        <img src="${previewUrl}" alt="${title}">
        <div class="reference-preview-overlay">
            <span class="reference-preview-title">${title}</span>
            <button type="button" class="btn-remove-reference" onclick="removeReferencePending('${tempId}')" title="Remover">×</button>
        </div>
    `;
    gallery.appendChild(refItem);
}

function removeReferencePending(tempId) {
    const index = PendingUploads.references.findIndex(item => item.tempId === tempId);
    if (index !== -1) PendingUploads.references.splice(index, 1);
    
    const refItem = document.querySelector(`.reference-preview-item[data-ref-id="${tempId}"]`);
    if (refItem) refItem.remove();
    toaster.info('Imagem removida');
}

async function uploadFileToS3(file, type, uploadUrlEndpoint, createRecordEndpoint) {
    try {
        logger.debug('Iniciando upload:', {file: file.name, type, endpoint: uploadUrlEndpoint});
        
        // 1. Obter Presigned URL
        const urlResponse = await fetch(uploadUrlEndpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: new URLSearchParams({
                fileName: file.name,
                fileType: file.type,
                fileSize: file.size
            })
        });
        
        logger.debug('Response status:', urlResponse.status);
        logger.debug('Response URL:', urlResponse.url);
        
        if (!urlResponse.ok) {
            const contentType = urlResponse.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                const error = await urlResponse.json();
                throw new Error(error.error || 'Erro ao obter URL de upload');
            } else {
                const text = await urlResponse.text();
                logger.error('Response HTML:', text.substring(0, 500));
                
                // Verificar se é redirect de login
                if (text.includes('login') || text.includes('Login') || urlResponse.status === 302) {
                    throw new Error('Você precisa estar logado para fazer upload. Faça login e tente novamente.');
                }
                
                throw new Error(`Erro ${urlResponse.status}: Endpoint não encontrado ou retornou HTML. URL: ${uploadUrlEndpoint}`);
            }
        }
        
        const urlData = await urlResponse.json();
        logger.debug('Presigned URL obtida:', urlData.success);
        logger.debug('Data recebida:', urlData.data);
        
        if (!urlData.success) {
            throw new Error(urlData.error || 'Erro ao obter URL de upload');
        }
        
        // Extrair organization_id do s3_key se não vier no data
        let orgId = urlData.data.organization_id;
        if (!orgId && urlData.data.s3_key) {
            const match = urlData.data.s3_key.match(/org-(\d+)\//);
            if (match) {
                orgId = match[1];
                logger.debug('Organization ID extraído do s3_key:', orgId);
            }
        }
        
        // 2. Upload para S3
        // Usar signed_headers retornados pelo backend
        const uploadHeaders = {
            'Content-Type': file.type,
            ...(urlData.data.signed_headers || {})
        };
        
        logger.debug('Headers enviados para S3:', uploadHeaders);
        logger.debug('URL S3:', urlData.data.upload_url.substring(0, 150) + '...');
        
        const s3Response = await fetch(urlData.data.upload_url, {
            method: 'PUT',
            body: file,
            headers: uploadHeaders
        });
        
        logger.debug('S3 Response status:', s3Response.status);
        
        if (!s3Response.ok) {
            const errorText = await s3Response.text();
            logger.error('S3 Error response:', errorText.substring(0, 500));
            throw new Error('Erro ao enviar arquivo para S3');
        }
        
        // 3. Criar registro no banco
        const createResponse = await fetch(createRecordEndpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: new URLSearchParams({
                s3Key: urlData.data.s3_key,
                name: file.name.replace(/\.[^/.]+$/, ''),
                fileFormat: file.type.split('/')[1],
                ...(type === 'logo' ? {logoType: 'principal'} : {category: 'geral'})
            })
        });
        
        if (!createResponse.ok) {
            const errorText = await createResponse.text();
            logger.error('Erro ao criar registro (status ' + createResponse.status + '):', errorText.substring(0, 500));
            try {
                const error = JSON.parse(errorText);
                throw new Error(error.error || 'Erro ao criar ' + type);
            } catch (e) {
                throw new Error('Erro ao criar ' + type);
            }
        }
        
        const createData = await createResponse.json();
        if (!createData.success) {
            throw new Error(createData.error || 'Erro ao criar registro');
        }
        
        return createData.data;
        
    } catch (error) {
        logger.error('Erro no upload:', error);
        throw error;
    }
}

function getCookie(name) {
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

function setupDragAndDrop(area, inputId) {
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        area.addEventListener(eventName, (e) => {e.preventDefault(); e.stopPropagation();}, false);
    });
    
    ['dragenter', 'dragover'].forEach(eventName => {
        area.addEventListener(eventName, () => area.classList.add('drag-over'), false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        area.addEventListener(eventName, () => area.classList.remove('drag-over'), false);
    });
    
    area.addEventListener('drop', function(e) {
        const input = document.getElementById(inputId);
        if (input) {
            input.files = e.dataTransfer.files;
            input.dispatchEvent(new Event('change', {bubbles: true}));
        }
    }, false);
}

document.addEventListener('DOMContentLoaded', function() {
    UploadConfig.validators.logos = new ImageValidator('logos');
    UploadConfig.validators.references = new ImageValidator('references');
    
    const logoUploadArea = document.getElementById('logo-upload-area');
    const referenceUploadArea = document.getElementById('reference-upload-area');
    
    if (logoUploadArea) setupDragAndDrop(logoUploadArea, 'logo-upload-input');
    if (referenceUploadArea) setupDragAndDrop(referenceUploadArea, 'reference-upload-input');
    
    const logoInput = document.getElementById('logo-upload-input');
    if (logoInput) logoInput.addEventListener('change', handleLogoUpload);
    
    const referenceInput = document.getElementById('reference-upload-input');
    if (referenceInput) referenceInput.addEventListener('change', handleReferenceUpload);
    
    document.addEventListener('click', function(e) {
        if (e.target.matches('[data-action="trigger-logo-upload"]') || e.target.closest('[data-action="trigger-logo-upload"]')) {
            e.preventDefault();
            e.stopPropagation();
            document.getElementById('logo-upload-input')?.click();
        }
        if (e.target.matches('[data-action="trigger-reference-upload"]') || e.target.closest('[data-action="trigger-reference-upload"]')) {
            e.preventDefault();
            e.stopPropagation();
            document.getElementById('reference-upload-input')?.click();
        }
    });
    
    // Interceptar submit do formulário para fazer upload antes
    const form = document.querySelector('form.form-grid');
    if (form) {
        form.addEventListener('submit', async function(e) {
            const hasPendingFiles = PendingUploads.logos.length > 0 || PendingUploads.references.length > 0;
            
            if (hasPendingFiles) {
                e.preventDefault();
                
                // Mostrar spinner
                const submitBtn = form.querySelector('button[type="submit"]');
                const originalBtnText = submitBtn.innerHTML;
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="spinner"></span> Enviando arquivos...';
                
                try {
                    const uploadedLogos = [];
                    const uploadedReferences = [];
                    
                    // Upload de logos
                    for (let item of PendingUploads.logos) {
                        const result = await uploadFileToS3(item.file, 'logo', UploadConfig.endpoints.logoUploadUrl, UploadConfig.endpoints.logoCreate);
                        uploadedLogos.push(result);
                    }
                    
                    // Upload de referências
                    for (let item of PendingUploads.references) {
                        const result = await uploadFileToS3(item.file, 'reference', UploadConfig.endpoints.referenceUploadUrl, UploadConfig.endpoints.referenceCreate);
                        uploadedReferences.push(result);
                    }
                    
                    // Adicionar previews permanentes na galeria
                    uploadedLogos.forEach(logo => addLogoToGallery(logo));
                    uploadedReferences.forEach(ref => addReferenceToGallery(ref));
                    
                    // Limpar pendentes e remover previews temporários
                    PendingUploads.logos.forEach(item => {
                        const preview = document.querySelector(`[data-pending-id="${item.id}"]`);
                        if (preview) preview.remove();
                    });
                    PendingUploads.references.forEach(item => {
                        const preview = document.querySelector(`[data-pending-id="${item.id}"]`);
                        if (preview) preview.remove();
                    });
                    
                    PendingUploads.logos = [];
                    PendingUploads.references = [];
                    
                    // Submeter formulário
                    toaster.success('Arquivos enviados com sucesso!');
                    form.submit();
                    
                } catch (error) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalBtnText;
                    toaster.error('Erro ao enviar arquivos: ' + error.message);
                }
            }
        });
    }
});

function addLogoToGallery(logoData) {
    const gallery = document.getElementById('logos-gallery');
    if (!gallery) return;
    
    const preview = document.createElement('div');
    preview.className = 'logo-preview-item';
    preview.setAttribute('data-logo-id', logoData.logoId);
    preview.innerHTML = `
        <img src="${logoData.previewUrl}" alt="Logo">
        <div class="logo-preview-info">
            <span class="logo-preview-name">${logoData.name || 'Logo'}</span>
            <span class="logo-preview-type">Principal</span>
        </div>
        <button type="button" class="btn-remove-logo" data-action="remove-logo" data-logo-id="${logoData.logoId}" title="Remover">
            ×
        </button>
    `;
    gallery.appendChild(preview);
}

function addReferenceToGallery(refData) {
    const gallery = document.getElementById('references-gallery');
    if (!gallery) return;
    
    const preview = document.createElement('div');
    preview.className = 'reference-preview-item';
    preview.setAttribute('data-ref-id', refData.referenceId);
    preview.innerHTML = `
        <img src="${refData.previewUrl}" alt="Referência">
        <div class="reference-preview-overlay">
            <span class="reference-preview-title">${refData.name || 'Imagem'}</span>
            <button type="button" class="btn-remove-reference" data-action="remove-reference" data-ref-id="${refData.referenceId}" title="Remover">
                ×
            </button>
        </div>
    `;
    gallery.appendChild(preview);
}

// Remover logo existente (já salvo no banco)
async function removeLogo(logoId) {
    const confirmed = await showConfirm(
        'Esta ação não pode ser desfeita. O logo será removido permanentemente.',
        'Remover logo?'
    );
    if (!confirmed) return;
    
    try {
        const response = await fetch(`/knowledge/logo/${logoId}/delete/`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            const logoItem = document.querySelector(`.logo-preview-item[data-logo-id="${logoId}"]`);
            if (logoItem) logoItem.remove();
            toaster.success('Logo removido com sucesso!');
        } else {
            toaster.error(data.error || 'Erro ao remover logo');
        }
    } catch (error) {
        logger.error('Erro ao remover logo:', error);
        toaster.error('Erro ao remover logo');
    }
}

// Remover referência existente (já salva no banco)
async function removeReference(refId) {
    const confirmed = await showConfirm(
        'Esta ação não pode ser desfeita. A imagem será removida permanentemente.',
        'Remover imagem?'
    );
    if (!confirmed) return;
    
    try {
        const response = await fetch(`/knowledge/reference/${refId}/delete/`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            const refItem = document.querySelector(`.reference-preview-item[data-ref-id="${refId}"]`);
            if (refItem) refItem.remove();
            toaster.success('Imagem removida com sucesso!');
        } else {
            toaster.error(data.error || 'Erro ao remover imagem');
        }
    } catch (error) {
        logger.error('Erro ao remover referência:', error);
        toaster.error('Erro ao remover imagem');
    }
}

window.handleLogoUpload = handleLogoUpload;
window.removeLogoPending = removeLogoPending;
window.removeLogo = removeLogo;
window.handleReferenceUpload = handleReferenceUpload;
window.removeReferencePending = removeReferencePending;
window.removeReference = removeReference;
window.addLogoToGallery = addLogoToGallery;
window.addReferenceToGallery = addReferenceToGallery;
window.PendingUploads = PendingUploads;
