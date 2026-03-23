/**
 * PERFIL-FONTS.JS - Gerenciamento de fontes no Perfil
 * Layout pills: nome da fonte + uso + botão X
 */

const googleFontsPopulares = [
    'Roboto', 'Open Sans', 'Lato', 'Montserrat', 'Oswald',
    'Source Sans Pro', 'Raleway', 'PT Sans', 'Merriweather', 'Ubuntu',
    'Playfair Display', 'Poppins', 'Nunito', 'Quicksand', 'Inter',
    'Work Sans', 'Rubik', 'Mulish', 'Karla', 'DM Sans'
];

let perfilFontModal = null;
let currentFontSource = 'google';

document.addEventListener('DOMContentLoaded', function() {
    initPerfilFontModal();
});

function initPerfilFontModal() {
    // Criar modal de adicionar fonte
    const modalHTML = `
        <div id="perfil-font-modal" class="perfil-font-modal">
            <div class="perfil-font-modal-content">
                <h3 class="perfil-font-modal-header">Adicionar fonte</h3>
                
                <div class="perfil-font-source-selector">
                    <div class="perfil-font-source-option active" onclick="selectPerfilFontSource('google')">
                        🌐 Google Fonts
                    </div>
                    <div class="perfil-font-source-option" onclick="selectPerfilFontSource('upload')">
                        📁 Upload TTF
                    </div>
                </div>
                
                <div class="perfil-font-fields">
                    <div class="perfil-font-field">
                        <label>Uso da fonte</label>
                        <select id="perfil-font-usage">
                            <option value="Títulos">Títulos</option>
                            <option value="Subtítulos">Subtítulos</option>
                            <option value="Texto corrido">Texto corrido</option>
                            <option value="Botões">Botões</option>
                            <option value="Legendas">Legendas</option>
                        </select>
                    </div>
                    
                    <div class="perfil-font-google-fields">
                        <div class="perfil-font-field">
                            <label>Fonte</label>
                            <select id="perfil-font-name">
                                <option value="">Selecione...</option>
                                ${googleFontsPopulares.map(font => 
                                    `<option value="${font}">${font}</option>`
                                ).join('')}
                            </select>
                        </div>
                        <div class="perfil-font-field">
                            <label>Peso</label>
                            <select id="perfil-font-weight">
                                <option value="300">Light</option>
                                <option value="400" selected>Regular</option>
                                <option value="500">Medium</option>
                                <option value="600">SemiBold</option>
                                <option value="700">Bold</option>
                            </select>
                        </div>
                    </div>
                    
                    <div class="perfil-font-upload-fields" style="display: none;">
                        <div class="perfil-font-field">
                            <label>Arquivo TTF/OTF</label>
                            <input type="file" id="perfil-font-file" accept=".ttf,.otf,.woff,.woff2">
                        </div>
                    </div>
                </div>
                
                <div class="perfil-font-modal-actions">
                    <button type="button" class="btn-cancel" onclick="closePerfilFontModal()">Cancelar</button>
                    <button type="button" class="btn-confirm" onclick="confirmPerfilFont()">Adicionar</button>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    perfilFontModal = document.getElementById('perfil-font-modal');
    
    // Fechar modal ao clicar fora
    perfilFontModal.addEventListener('click', function(e) {
        if (e.target === perfilFontModal) {
            closePerfilFontModal();
        }
    });
}

function selectPerfilFontSource(source) {
    currentFontSource = source;
    
    // Atualizar botões ativos
    document.querySelectorAll('.perfil-font-source-option').forEach(opt => opt.classList.remove('active'));
    event.target.classList.add('active');
    
    // Mostrar/ocultar campos
    const googleFields = document.querySelector('.perfil-font-google-fields');
    const uploadFields = document.querySelector('.perfil-font-upload-fields');
    
    if (source === 'google') {
        googleFields.style.display = 'flex';
        uploadFields.style.display = 'none';
    } else {
        googleFields.style.display = 'none';
        uploadFields.style.display = 'flex';
    }
}

function addPerfilFont() {
    if (perfilFontModal) {
        perfilFontModal.classList.add('show');
        // Reset campos
        document.getElementById('perfil-font-usage').value = 'Títulos';
        document.getElementById('perfil-font-name').value = '';
        document.getElementById('perfil-font-weight').value = '400';
        if (document.getElementById('perfil-font-file')) {
            document.getElementById('perfil-font-file').value = '';
        }
        selectPerfilFontSource('google');
    }
}

function closePerfilFontModal() {
    if (perfilFontModal) {
        perfilFontModal.classList.remove('show');
    }
}

async function confirmPerfilFont() {
    const usage = document.getElementById('perfil-font-usage').value;
    
    if (currentFontSource === 'google') {
        const fontName = document.getElementById('perfil-font-name').value;
        const fontWeight = document.getElementById('perfil-font-weight').value;
        
        if (!fontName) {
            if (window.toaster) {
                toaster.error('Selecione uma fonte');
            } else {
                alert('Selecione uma fonte');
            }
            return;
        }
        
        try {
            const response = await fetch('/knowledge/perfil/add-font/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                },
                body: JSON.stringify({
                    font_source: 'google',
                    google_font_name: fontName,
                    google_font_weight: fontWeight,
                    usage: usage
                })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.message || 'Erro ao adicionar fonte');
            }
            
            const data = await response.json();
            
            closePerfilFontModal();
            
            if (window.toaster) {
                toaster.success('Fonte adicionada com sucesso!');
            }
            
            // Recarregar página para mostrar a fonte adicionada
            setTimeout(() => {
                window.location.reload();
            }, 1000);
            
        } catch (error) {
            console.error('Erro ao adicionar fonte:', error);
            if (window.toaster) {
                toaster.error(error.message || 'Erro ao adicionar fonte');
            } else {
                alert(error.message || 'Erro ao adicionar fonte');
            }
        }
        
    } else {
        // Upload TTF
        const fileInput = document.getElementById('perfil-font-file');
        if (!fileInput.files || !fileInput.files[0]) {
            if (window.toaster) {
                toaster.error('Selecione um arquivo');
            } else {
                alert('Selecione um arquivo');
            }
            return;
        }
        
        const file = fileInput.files[0];
        const fontName = file.name.replace(/\.(ttf|otf|woff|woff2)$/i, '');
        
        try {
            // Desabilitar botão durante upload
            const confirmBtn = document.querySelector('.perfil-font-modal-actions .btn-confirm');
            if (confirmBtn) {
                confirmBtn.disabled = true;
                confirmBtn.textContent = 'Enviando...';
            }
            
            // 1. Obter Presigned URL
            // Detectar MIME type correto baseado na extensão
            const fontFileExt = file.name.split('.').pop().toLowerCase();
            const mimeTypes = {
                'ttf': 'font/ttf',
                'otf': 'font/otf',
                'woff': 'font/woff',
                'woff2': 'font/woff2'
            };
            const detectedMimeType = mimeTypes[fontFileExt] || 'font/ttf';
            const finalMimeType = file.type || detectedMimeType;
            
            const urlResponse = await fetch('/knowledge/font/upload-url/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': getCsrfToken()
                },
                body: new URLSearchParams({
                    fileName: file.name,
                    fileType: finalMimeType,
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
            
            // 2. Upload para S3
            // IMPORTANTE: Usar signed_headers retornados pela API
            const uploadHeaders = {
                'Content-Type': file.type || 'font/ttf',
                ...(urlData.data.signed_headers || {})
            };
            
            const s3Response = await fetch(urlData.data.upload_url, {
                method: 'PUT',
                body: file,
                headers: uploadHeaders
            });
            
            if (!s3Response.ok) {
                const errorText = await s3Response.text();
                console.error('S3 Error Response:', {
                    status: s3Response.status,
                    statusText: s3Response.statusText,
                    body: errorText
                });
                throw new Error(`Erro ao enviar arquivo para S3 (${s3Response.status}): ${s3Response.statusText}`);
            }
            
            // 3. Criar registro CustomFont no banco
            const fileExt = file.name.split('.').pop().toLowerCase();
            const createResponse = await fetch('/knowledge/font/create/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': getCsrfToken()
                },
                body: new URLSearchParams({
                    s3Key: urlData.data.s3_key,
                    name: fontName,
                    fileFormat: fileExt
                })
            });
            
            if (!createResponse.ok) {
                throw new Error('Erro ao criar registro da fonte');
            }
            
            const createData = await createResponse.json();
            if (!createData.success) {
                throw new Error(createData.error || 'Erro ao criar registro');
            }
            
            const customFontId = createData.data.fontId;
            
            // 4. Criar Typography vinculado ao CustomFont
            const addFontResponse = await fetch('/knowledge/perfil/add-font/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                },
                body: JSON.stringify({
                    font_source: 'upload',
                    custom_font_id: customFontId,
                    usage: usage
                })
            });
            
            if (!addFontResponse.ok) {
                const error = await addFontResponse.json();
                throw new Error(error.message || 'Erro ao adicionar fonte');
            }
            
            closePerfilFontModal();
            
            if (window.toaster) {
                toaster.success(`Fonte ${fontName} enviada com sucesso!`);
            }
            
            // Recarregar página para mostrar a fonte adicionada
            setTimeout(() => {
                window.location.reload();
            }, 1000);
            
        } catch (error) {
            console.error('Erro ao fazer upload:', error);
            if (window.toaster) {
                toaster.error('Erro ao enviar fonte: ' + error.message);
            } else {
                alert('Erro ao enviar fonte: ' + error.message);
            }
            
            // Reabilitar botão
            const confirmBtn = document.querySelector('.perfil-font-modal-actions .btn-confirm');
            if (confirmBtn) {
                confirmBtn.disabled = false;
                confirmBtn.textContent = 'Adicionar';
            }
        }
    }
}

async function removePerfilFont(fontId) {
    // Confirmar remoção
    const confirmed = window.confirmModal 
        ? await window.confirmModal.show('Tem certeza que deseja remover esta fonte?', 'Remover fonte')
        : confirm('Tem certeza que deseja remover esta fonte?');
    
    if (!confirmed) return;
    
    try {
        const response = await fetch('/knowledge/perfil/remove-font/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            },
            body: JSON.stringify({
                font_id: fontId
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || 'Erro ao remover fonte');
        }
        
        if (window.toaster) {
            toaster.success('Fonte removida com sucesso!');
        }
        
        // Recarregar página para atualizar lista
        setTimeout(() => {
            window.location.reload();
        }, 1000);
        
    } catch (error) {
        console.error('Erro ao remover fonte:', error);
        if (window.toaster) {
            toaster.error(error.message || 'Erro ao remover fonte');
        } else {
            alert(error.message || 'Erro ao remover fonte');
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
window.addPerfilFont = addPerfilFont;
window.removePerfilFont = removePerfilFont;
window.closePerfilFontModal = closePerfilFontModal;
window.selectPerfilFontSource = selectPerfilFontSource;
window.confirmPerfilFont = confirmPerfilFont;
