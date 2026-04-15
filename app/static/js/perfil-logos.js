/**
 * PERFIL-LOGOS.JS - Gerenciamento de logotipos no Perfil
 * Upload S3 direto sem modal
 */

let perfilLogoFileInput = null;

document.addEventListener('DOMContentLoaded', function() {
    initPerfilLogoInput();
});

function initPerfilLogoInput() {
    // Criar input file invisível
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.id = 'perfil-logo-file-input';
    fileInput.accept = 'image/png,image/jpeg,image/svg+xml';
    fileInput.style.display = 'none';
    document.body.appendChild(fileInput);
    
    perfilLogoFileInput = fileInput;
    
    // File input change - fazer upload imediatamente
    fileInput.addEventListener('change', async (e) => {
        if (e.target.files && e.target.files[0]) {
            await uploadPerfilLogo(e.target.files[0]);
        }
    });
}

function addPerfilLogo() {
    // Abrir file picker direto
    if (perfilLogoFileInput) {
        perfilLogoFileInput.click();
    }
}

async function uploadPerfilLogo(file) {
    // Validar tipo
    const validTypes = ['image/png', 'image/jpeg', 'image/svg+xml'];
    if (!validTypes.includes(file.type)) {
        if (window.toaster) {
            toaster.error('Formato inválido. Use PNG, JPG ou SVG');
        } else {
            alert('Formato inválido. Use PNG, JPG ou SVG');
        }
        return;
    }
    
    // Validar tamanho (5MB)
    if (file.size > 5 * 1024 * 1024) {
        if (window.toaster) {
            toaster.error('Arquivo muito grande. Máximo 5MB');
        } else {
            alert('Arquivo muito grande. Máximo 5MB');
        }
        return;
    }
    
    try {
        // Mostrar loading via toaster
        if (window.toaster) {
            toaster.info('Enviando logo...');
        }
        
        // 1. Obter Presigned URL
        const urlResponse = await fetch('/knowledge/logo/upload-url/', {
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
        // Usar signed_headers do backend (timestamp sincronizado com assinatura).
        const uploadHeaders = {
            'Content-Type': file.type,
            ...(urlData.data.signed_headers || {
                'x-amz-server-side-encryption': 'AES256',
                'x-amz-storage-class': 'INTELLIGENT_TIERING',
                'x-amz-meta-original-name': file.name,
                'x-amz-meta-organization-id': String(orgId || '0'),
                'x-amz-meta-category': 'logos',
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
        
        // 3. Criar registro Logo no banco
        const fileExt = file.name.split('.').pop().toLowerCase();
        const createResponse = await fetch('/knowledge/logo/create/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': getCsrfToken()
            },
            body: new URLSearchParams({
                s3Key: urlData.data.s3_key,
                name: file.name.replace(/\.(png|jpg|jpeg|svg)$/i, ''),
                logoType: 'principal',
                fileFormat: fileExt,
                isPrimary: 'false'
            })
        });
        
        if (!createResponse.ok) {
            throw new Error('Erro ao criar registro do logo');
        }
        
        const createData = await createResponse.json();
        if (!createData.success) {
            throw new Error(createData.error || 'Erro ao criar registro');
        }
        
        if (window.toaster) {
            toaster.success('Logo adicionado com sucesso!');
        }
        
        // Recarregar página para mostrar o logo adicionado
        setTimeout(() => {
            window.location.reload();
        }, 1000);
        
    } catch (error) {
        console.error('Erro ao fazer upload:', error);
        if (window.toaster) {
            toaster.error('Erro ao enviar logo: ' + error.message);
        } else {
            alert('Erro ao enviar logo: ' + error.message);
        }
    } finally {
        // Limpar input
        if (perfilLogoFileInput) {
            perfilLogoFileInput.value = '';
        }
    }
}

async function removePerfilLogo(logoId) {
    // Confirmar remoção
    const confirmed = window.confirmModal 
        ? await window.confirmModal.show('Tem certeza que deseja remover este logo?', 'Remover logo')
        : confirm('Tem certeza que deseja remover este logo?');
    
    if (!confirmed) return;
    
    try {
        const response = await fetch(`/knowledge/logo/${logoId}/delete/`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': getCsrfToken()
            }
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || 'Erro ao remover logo');
        }
        
        if (window.toaster) {
            toaster.success('Logo removido com sucesso!');
        }
        
        // Recarregar página para atualizar lista
        setTimeout(() => {
            window.location.reload();
        }, 1000);
        
    } catch (error) {
        console.error('Erro ao remover logo:', error);
        if (window.toaster) {
            toaster.error(error.message || 'Erro ao remover logo');
        } else {
            alert(error.message || 'Erro ao remover logo');
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
window.addPerfilLogo = addPerfilLogo;
window.removePerfilLogo = removePerfilLogo;
