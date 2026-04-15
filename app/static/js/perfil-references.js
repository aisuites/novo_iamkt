/**
 * PERFIL-REFERENCES.JS - Gerenciamento de imagens de referência no Perfil
 * Upload S3 direto (reutiliza lógica de logos)
 */

let perfilReferenceFileInput = null;

document.addEventListener('DOMContentLoaded', function() {
    initPerfilReferenceInput();
});

function initPerfilReferenceInput() {
    // Criar input file invisível
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.id = 'perfil-reference-file-input';
    fileInput.accept = 'image/png,image/jpeg,image/jpg';
    fileInput.multiple = true;  // Permitir múltiplas imagens
    fileInput.style.display = 'none';
    document.body.appendChild(fileInput);
    
    perfilReferenceFileInput = fileInput;
    
    // File input change - fazer upload imediatamente
    fileInput.addEventListener('change', async (e) => {
        if (e.target.files && e.target.files.length > 0) {
            let uploadCount = 0;
            let errorCount = 0;
            
            // Copiar FileList para array para evitar perda de referência
            const files = Array.from(e.target.files);
            
            // Upload de múltiplos arquivos
            for (let i = 0; i < files.length; i++) {
                const success = await uploadPerfilReference(files[i], false); // false = não limpar input
                if (success) {
                    uploadCount++;
                } else {
                    errorCount++;
                }
            }
            
            // Limpar input após todos os uploads
            if (perfilReferenceFileInput) {
                perfilReferenceFileInput.value = '';
            }
            
            // Recarregar página após todos os uploads
            if (uploadCount > 0) {
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
            }
        }
    });
}

function addPerfilReference() {
    // Abrir file picker direto
    if (perfilReferenceFileInput) {
        perfilReferenceFileInput.click();
    }
}

async function uploadPerfilReference(file, clearInput = true) {
    // Validar tipo
    const validTypes = ['image/png', 'image/jpeg', 'image/jpg'];
    if (!validTypes.includes(file.type)) {
        if (window.toaster) {
            toaster.error('Formato inválido. Use PNG ou JPG');
        } else {
            alert('Formato inválido. Use PNG ou JPG');
        }
        return false;
    }
    
    // Validar tamanho (10MB)
    if (file.size > 10 * 1024 * 1024) {
        if (window.toaster) {
            toaster.error('Arquivo muito grande. Máximo 10MB');
        } else {
            alert('Arquivo muito grande. Máximo 10MB');
        }
        return false;
    }
    
    try {
        // Mostrar loading via toaster
        if (window.toaster) {
            toaster.info('Enviando imagem...');
        }
        
        // 1. Obter Presigned URL
        const urlResponse = await fetch('/knowledge/reference/upload-url/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': getCsrfToken()
            },
            body: new URLSearchParams({
                fileName: file.name,
                fileType: file.type,
                fileSize: file.size
            })
        });
        
        if (!urlResponse.ok) {
            throw new Error('Erro ao obter URL de upload');
        }
        
        const urlData = await urlResponse.json();
        if (!urlData.success) {
            throw new Error(urlData.error || 'Erro ao obter URL de upload');
        }
        
        // Extrair organization_id do s3_key
        let orgId = urlData.data.organization_id;
        if (!orgId && urlData.data.s3_key) {
            const match = urlData.data.s3_key.match(/org-(\d+)\//);
            if (match) orgId = match[1];
        }
        
        // 2. Upload para S3
        // IMPORTANTE: usar signed_headers retornados pelo backend (contem o timestamp
        // usado na assinatura). Gerar timestamp no client quebra a assinatura (403).
        const uploadHeaders = {
            'Content-Type': file.type,
            ...(urlData.data.signed_headers || {
                'x-amz-server-side-encryption': 'AES256',
                'x-amz-storage-class': 'INTELLIGENT_TIERING',
                'x-amz-meta-original-name': file.name,
                'x-amz-meta-organization-id': String(orgId || '0'),
                'x-amz-meta-category': 'references',
                'x-amz-meta-upload-timestamp': Math.floor(Date.now() / 1000).toString()
            })
        };
        
        const s3Response = await fetch(urlData.data.upload_url, {
            method: 'PUT',
            body: file,
            headers: uploadHeaders
        });
        
        if (!s3Response.ok) {
            throw new Error('Erro ao enviar arquivo para S3');
        }
        
        // 3. Criar registro ReferenceImage no banco
        const createResponse = await fetch('/knowledge/reference/create/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': getCsrfToken()
            },
            body: new URLSearchParams({
                s3Key: urlData.data.s3_key,
                name: file.name.replace(/\.(png|jpg|jpeg)$/i, ''),
                description: ''
            })
        });
        
        if (!createResponse.ok) {
            throw new Error('Erro ao criar registro da imagem');
        }
        
        const createData = await createResponse.json();
        if (!createData.success) {
            throw new Error(createData.error || 'Erro ao criar registro');
        }
        
        if (window.toaster) {
            toaster.success('Imagem adicionada com sucesso!');
        }
        
        return true;
        
    } catch (error) {
        console.error('Erro ao fazer upload:', error);
        if (window.toaster) {
            toaster.error('Erro ao enviar imagem: ' + error.message);
        } else {
            alert('Erro ao enviar imagem: ' + error.message);
        }
        return false;
    }
}

async function removePerfilReference(refId) {
    // Confirmar remoção
    const confirmed = window.confirmModal 
        ? await window.confirmModal.show('Tem certeza que deseja remover esta imagem?', 'Remover imagem')
        : confirm('Tem certeza que deseja remover esta imagem?');
    
    if (!confirmed) return;
    
    try {
        const response = await fetch(`/knowledge/reference/${refId}/delete/`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': getCsrfToken()
            }
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || 'Erro ao remover imagem');
        }
        
        if (window.toaster) {
            toaster.success('Imagem removida com sucesso!');
        }
        
        // Recarregar página para atualizar lista
        setTimeout(() => {
            window.location.reload();
        }, 1000);
        
    } catch (error) {
        console.error('Erro ao remover imagem:', error);
        if (window.toaster) {
            toaster.error(error.message || 'Erro ao remover imagem');
        } else {
            alert(error.message || 'Erro ao remover imagem');
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

// Expor funções globalmente
window.addPerfilReference = addPerfilReference;
window.removePerfilReference = removePerfilReference;
