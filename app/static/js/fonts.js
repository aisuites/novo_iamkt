/**
 * FONTS.JS - Gerenciamento de Tipografia
 * Interface com Google Fonts + Upload TTF seguindo referência
 */

// Lista de Google Fonts populares
const googleFonts = [
    'Roboto', 'Open Sans', 'Lato', 'Montserrat', 'Oswald',
    'Source Sans Pro', 'Raleway', 'PT Sans', 'Merriweather', 'Ubuntu',
    'Playfair Display', 'Poppins', 'Nunito', 'Quicksand', 'Inter',
    'Work Sans', 'Rubik', 'Mulish', 'Karla', 'DM Sans'
];

let fonteIndex = 0;
const loadedGoogleFonts = new Set();
const usosOcupados = new Set();

// Carregar fonte do Google Fonts
function loadGoogleFont(fontName) {
    if (loadedGoogleFonts.has(fontName)) return;
    
    const link = document.createElement('link');
    link.href = `https://fonts.googleapis.com/css2?family=${fontName.replace(' ', '+')}:wght@300;400;500;600;700&display=swap`;
    link.rel = 'stylesheet';
    document.head.appendChild(link);
    loadedGoogleFonts.add(fontName);
}

// Obter usos disponíveis
function getUsosDisponiveis(usoAtual = '') {
    const usoLabels = {
        'TITULO': 'Títulos (H1)',
        'SUBTITULO': 'Subtítulos (H2)',
        'TEXTO': 'Texto corrido',
        'BOTAO': 'Botões',
        'LEGENDA': 'Legendas'
    };
    
    return Object.entries(usoLabels).filter(([value]) => 
        !usosOcupados.has(value) || value === usoAtual
    );
}

// Adicionar uma nova fonte
function addFonte(tipo = 'GOOGLE', nomeFonte = '', variante = '', uso = '', arquivoUrl = '', fontId = null) {
    const fontesList = document.getElementById('fontes-list');
    if (!fontesList) return;
    
    const fonteItem = document.createElement('div');
    fonteItem.className = 'fonte-item collapsed';  // Iniciar fechada
    fonteItem.setAttribute('data-index', fonteIndex);
    fonteItem.setAttribute('data-uso-atual', uso);
    fonteItem.setAttribute('data-tipo', tipo);  // Adicionar tipo como data attribute
    
    // Se for fonte customizada com ID, adicionar data-font-id
    if (fontId) {
        fonteItem.setAttribute('data-font-id', fontId);
        logger.debug(`DEBUG: data-font-id="${fontId}" adicionado ao fonteItem`);
    }
    
    // Obter usos disponíveis ANTES de marcar como ocupado
    const usosDisponiveis = getUsosDisponiveis();
    
    // Se não foi passado um uso ou o uso já está ocupado, pegar o primeiro disponível
    if (!uso || (usosOcupados.has(uso) && !arquivoUrl)) {
        uso = usosDisponiveis.length > 0 ? usosDisponiveis[0][0] : 'TITULO';
    }
    
    fonteItem.setAttribute('data-uso-atual', uso);
    
    // Marcar uso como ocupado
    usosOcupados.add(uso);
    
    const usoLabel = usosDisponiveis.find(([value]) => value === uso)?.[1] || 'Selecione...';
    
    fonteItem.innerHTML = `
        <div class="fonte-item-header" onclick="toggleFonteItem(${fonteIndex})">
            <div class="fonte-item-title">
                <span class="toggle-icon">▶</span>
                <span>Fonte #${fonteIndex + 1} - ${nomeFonte || 'Selecione...'} - ${usoLabel}</span>
            </div>
            <div class="fonte-item-actions" onclick="event.stopPropagation()">
                <button type="button" class="btn-remove-fonte" onclick="removeFonte(${fonteIndex}, '${uso}')">Remover</button>
            </div>
        </div>
        <div class="fonte-item-body">
        
        <div class="fonte-tipo-selector">
            <div class="fonte-tipo-option ${tipo === 'GOOGLE' ? 'active' : ''}" 
                 onclick="selectFonteTipo(${fonteIndex}, 'GOOGLE')">
                🌐 Google Fonts
            </div>
            <div class="fonte-tipo-option ${tipo === 'UPLOAD' ? 'active' : ''}" 
                 onclick="selectFonteTipo(${fonteIndex}, 'UPLOAD')">
                📁 Upload TTF
            </div>
        </div>
        
        <div class="fonte-fields">
            <div class="fonte-field-full">
                <label style="font-size: 12px; font-weight: 600; color: #6B7280; margin-bottom: 4px; display: block;">
                    Uso da fonte
                </label>
                <select name="fontes[${fonteIndex}][uso]" class="fonte-uso-select" 
                        onchange="updateFonteUso(${fonteIndex})" 
                        style="width: 100%; padding: 8px 12px; border: 1px solid #E5E7EB; border-radius: 8px; font-size: 13px;">
                    ${usosDisponiveis.map(([value, label]) => 
                        `<option value="${value}" ${uso === value ? 'selected' : ''}>${label}</option>`
                    ).join('')}
                </select>
            </div>
            
            <div class="fonte-google-fields" style="display: ${tipo === 'GOOGLE' ? 'contents' : 'none'};">
                <div>
                    <label style="font-size: 12px; font-weight: 600; color: #6B7280; margin-bottom: 4px; display: block;">
                        Fonte
                    </label>
                    <select name="fontes[${fonteIndex}][nome_fonte]" class="fonte-nome-select" 
                            onchange="updateFontePreview(${fonteIndex})"
                            style="width: 100%; padding: 8px 12px; border: 1px solid #E5E7EB; border-radius: 8px; font-size: 13px;">
                        <option value="">Selecione...</option>
                        ${googleFonts.map(font => 
                            `<option value="${font}" ${nomeFonte === font ? 'selected' : ''}>${font}</option>`
                        ).join('')}
                    </select>
                </div>
                <div>
                    <label style="font-size: 12px; font-weight: 600; color: #6B7280; margin-bottom: 4px; display: block;">
                        Peso
                    </label>
                    <select name="fontes[${fonteIndex}][variante]" class="fonte-variante-select" 
                            onchange="updateFontePreview(${fonteIndex})"
                            style="width: 100%; padding: 8px 12px; border: 1px solid #E5E7EB; border-radius: 8px; font-size: 13px;">
                        <option value="300" ${variante === '300' ? 'selected' : ''}>Light</option>
                        <option value="400" ${variante === '400' || !variante ? 'selected' : ''}>Regular</option>
                        <option value="500" ${variante === '500' ? 'selected' : ''}>Medium</option>
                        <option value="600" ${variante === '600' ? 'selected' : ''}>SemiBold</option>
                        <option value="700" ${variante === '700' ? 'selected' : ''}>Bold</option>
                    </select>
                </div>
            </div>
            
            <div class="fonte-upload-fields fonte-field-full" style="display: ${tipo === 'UPLOAD' ? 'block' : 'none'};">
                <label style="font-size: 12px; font-weight: 600; color: #6B7280; margin-bottom: 4px; display: block;">
                    Arquivo TTF
                </label>
                <input type="file" name="fontes[${fonteIndex}][arquivo]" accept=".ttf" 
                       onchange="handleFonteUpload(${fonteIndex}, this)"
                       style="width: 100%; padding: 8px 12px; border: 1px solid #E5E7EB; border-radius: 8px; font-size: 13px;">
                <input type="hidden" name="fontes[${fonteIndex}][nome_fonte_upload]" value="${nomeFonte}">
                ${arquivoUrl ? `<div style="margin-top: 8px; padding: 8px 12px; background: #F3F4F6; border-radius: 6px; font-size: 12px; color: #6B7280;">
                    📎 Arquivo atual: <strong>${nomeFonte}.ttf</strong>
                </div>` : ''}
            </div>
            
            <input type="hidden" name="fontes[${fonteIndex}][tipo]" value="${tipo}" class="fonte-tipo-input">
            
            <div class="fonte-preview">
                <p class="fonte-preview-text ${uso.toLowerCase()}" id="fonte-preview-${fonteIndex}">
                    Aa Bb Cc 123
                </p>
            </div>
        </div>
    `;
    
    fontesList.appendChild(fonteItem);
    const currentIndex = fonteIndex;
    fonteIndex++;
    
    // Carregar fonte e atualizar preview
    if (tipo === 'GOOGLE' && nomeFonte) {
        loadGoogleFont(nomeFonte);
        setTimeout(() => updateFontePreview(currentIndex), 200);
    }
}

// Toggle accordion da fonte
function toggleFonteItem(index) {
    const fonteItem = document.querySelector(`.fonte-item[data-index="${index}"]`);
    if (!fonteItem) return;
    
    const isCollapsed = fonteItem.classList.contains('collapsed');
    const icon = fonteItem.querySelector('.toggle-icon');
    
    if (isCollapsed) {
        fonteItem.classList.remove('collapsed');
        icon.textContent = '▼';
    } else {
        fonteItem.classList.add('collapsed');
        icon.textContent = '▶';
    }
}

// Selecionar tipo de fonte (Google ou Upload)
function selectFonteTipo(index, tipo) {
    const fonteItem = document.querySelector(`.fonte-item[data-index="${index}"]`);
    if (!fonteItem) return;
    
    // Atualizar data-tipo
    fonteItem.setAttribute('data-tipo', tipo);
    
    // Atualizar botões ativos
    fonteItem.querySelectorAll('.fonte-tipo-option').forEach(opt => opt.classList.remove('active'));
    fonteItem.querySelector(`.fonte-tipo-option:nth-child(${tipo === 'GOOGLE' ? 1 : 2})`).classList.add('active');
    
    const googleFields = fonteItem.querySelector('.fonte-google-fields');
    const uploadFields = fonteItem.querySelector('.fonte-upload-fields');
    
    if (tipo === 'GOOGLE') {
        googleFields.style.display = 'contents';
        uploadFields.style.display = 'none';
    } else {
        googleFields.style.display = 'none';
        uploadFields.style.display = 'block';
    }
}

// Atualizar preview da fonte
function updateFontePreview(index) {
    const fonteItem = document.querySelector(`.fonte-item[data-index="${index}"]`);
    if (!fonteItem) return;
    
    const nomeFonte = fonteItem.querySelector('.fonte-nome-select').value;
    const variante = fonteItem.querySelector('.fonte-variante-select').value;
    const preview = fonteItem.querySelector('.fonte-preview-text');
    
    if (nomeFonte) {
        loadGoogleFont(nomeFonte);
        preview.style.fontFamily = `"${nomeFonte}", sans-serif`;
        preview.style.fontWeight = variante;
        
        // ✅ Atualizar título com nome da fonte
        const usoLabel = fonteItem.querySelector('.fonte-uso-select option:checked').textContent;
        fonteItem.querySelector('.fonte-item-title span:last-child').textContent = 
            `Fonte #${parseInt(index) + 1} - ${nomeFonte} - ${usoLabel}`;
    }
}

// Atualizar uso da fonte
function updateFonteUso(index) {
    const fonteItem = document.querySelector(`.fonte-item[data-index="${index}"]`);
    if (!fonteItem) return;
    
    const usoAtual = fonteItem.getAttribute('data-uso-atual');
    const novoUso = fonteItem.querySelector('.fonte-uso-select').value;
    
    // Atualizar set de usos ocupados
    usosOcupados.delete(usoAtual);
    usosOcupados.add(novoUso);
    
    fonteItem.setAttribute('data-uso-atual', novoUso);
    
    // Atualizar título com nome da fonte
    const nomeFonte = fonteItem.querySelector('.fonte-nome-select')?.value || 'Selecione...';
    const usoLabel = fonteItem.querySelector('.fonte-uso-select option:checked').textContent;
    fonteItem.querySelector('.fonte-item-title span:last-child').textContent = 
        `Fonte #${parseInt(index) + 1} - ${nomeFonte} - ${usoLabel}`;
}

// Remover fonte
async function removeFonte(indexOrButton, uso) {
    let fonteItem;
    
    // Se recebeu um número (índice), buscar pelo data-index
    if (typeof indexOrButton === 'number') {
        fonteItem = document.querySelector(`.fonte-item[data-index="${indexOrButton}"]`);
    } else {
        // Se recebeu um elemento (button), buscar o pai
        fonteItem = indexOrButton.closest('.fonte-item');
    }
    
    if (!fonteItem) {
        logger.debug('DEBUG: fonteItem não encontrado');
        return;
    }
    
    // Verificar se é fonte customizada (UPLOAD)
    const fontId = fonteItem.dataset.fontId;
    const tipo = fonteItem.dataset.tipo;  // Usar data-tipo ao invés de querySelector
    const isCustomFont = tipo === 'UPLOAD';
    
    logger.debug('DEBUG removeFonte:', {
        fontId: fontId,
        tipo: tipo,
        isCustomFont: isCustomFont,
        datasetKeys: Object.keys(fonteItem.dataset)
    });
    
    // Se for fonte customizada, deletar do banco
    if (isCustomFont && fontId) {
        const confirmed = await showConfirm(
            'Esta ação não pode ser desfeita. A fonte será removida permanentemente do sistema.',
            'Remover fonte?'
        );
        if (!confirmed) {
            return;
        }
        
        try {
            const response = await fetch(`/knowledge/font/${fontId}/delete/`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken')
                }
            });
            
            const data = await response.json();
            
            if (!data.success) {
                if (typeof toaster !== 'undefined') {
                    toaster.error(data.error || 'Erro ao remover fonte');
                } else {
                    alert(data.error || 'Erro ao remover fonte');
                }
                return;
            }
            
            if (typeof toaster !== 'undefined') {
                toaster.success('Fonte removida com sucesso!');
            }
        } catch (error) {
            logger.error('Erro ao remover fonte:', error);
            if (typeof toaster !== 'undefined') {
                toaster.error('Erro ao remover fonte');
            } else {
                alert('Erro ao remover fonte');
            }
            return;
        }
    }
    
    // Remover visualmente
    const usoSelect = fonteItem.querySelector('.fonte-uso');
    if (usoSelect) {
        usosOcupados.delete(usoSelect.value);
    }
    
    fonteItem.classList.add('removing');
    
    setTimeout(() => {
        fonteItem.remove();
        syncFontsToForm();
    }, 200);
}

// Helper para obter CSRF token
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

function syncFontsToForm() {
    const fontesList = document.getElementById('fontes-list');
    if (!fontesList) return;
    
    const fonteItems = fontesList.querySelectorAll('.fonte-item');
    const form = document.querySelector('form[action*="save_all"]');
    if (!form) return;
    
    // Remover campos hidden antigos de fontes
    form.querySelectorAll('input[name^="fontes["]').forEach(input => {
        if (input.type === 'hidden') input.remove();
    });
    
    // Criar campos hidden para cada fonte
    fonteItems.forEach((item, index) => {
        const tipoRadios = item.querySelectorAll('input[name^="fonte_tipo_"]');
        let tipo = 'GOOGLE';
        tipoRadios.forEach(radio => {
            if (radio.checked) tipo = radio.value;
        });
        
        const nomeFonteSelect = item.querySelector('.fonte-nome');
        const varianteSelect = item.querySelector('.fonte-variante');
        const usoSelect = item.querySelector('.fonte-uso');
        
        if (nomeFonteSelect && usoSelect) {
            // Tipo
            const tipoField = document.createElement('input');
            tipoField.type = 'hidden';
            tipoField.name = `fontes[${index}][tipo]`;
            tipoField.value = tipo;
            form.appendChild(tipoField);
            
            // Nome da fonte
            const nomeField = document.createElement('input');
            nomeField.type = 'hidden';
            nomeField.name = `fontes[${index}][nome_fonte]`;
            nomeField.value = nomeFonteSelect.value;
            form.appendChild(nomeField);
            
            // Variante (se existir)
            if (varianteSelect && varianteSelect.value) {
                const varianteField = document.createElement('input');
                varianteField.type = 'hidden';
                varianteField.name = `fontes[${index}][variante]`;
                varianteField.value = varianteSelect.value;
                form.appendChild(varianteField);
            }
            
            // Uso
            const usoField = document.createElement('input');
            usoField.type = 'hidden';
            usoField.name = `fontes[${index}][uso]`;
            usoField.value = usoSelect.value;
            form.appendChild(usoField);
        }
    });
}

// Handle upload de arquivo TTF
async function handleFonteUpload(index, input) {
    if (input.files && input.files[0]) {
        const file = input.files[0];
        const fonteItem = document.querySelector(`.fonte-item[data-index="${index}"]`);
        if (!fonteItem) return;
        
        const hiddenInput = fonteItem.querySelector('input[name*="nome_fonte_upload"]');
        const fontName = file.name.replace(/\.(ttf|otf|woff|woff2)$/i, '');
        hiddenInput.value = fontName;
        
        // Upload para S3
        try {
            // Mostrar loading
            input.disabled = true;
            
            // 1. Obter Presigned URL
            const urlResponse = await fetch('/knowledge/font/upload-url/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: new URLSearchParams({
                    fileName: file.name,
                    fileType: file.type || 'font/ttf',
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
            const uploadHeaders = {
                'Content-Type': file.type || 'font/ttf',
                'x-amz-server-side-encryption': 'AES256',
                'x-amz-storage-class': 'INTELLIGENT_TIERING',
                'x-amz-meta-original-name': file.name,
                'x-amz-meta-organization-id': String(orgId || '0'),
                'x-amz-meta-category': 'fonts',
                'x-amz-meta-upload-timestamp': Math.floor(Date.now() / 1000).toString()
            };
            
            const s3Response = await fetch(urlData.data.upload_url, {
                method: 'PUT',
                body: file,
                headers: uploadHeaders
            });
            
            if (!s3Response.ok) {
                throw new Error('Erro ao enviar arquivo para S3');
            }
            
            // 3. Criar registro no banco
            const fileExt = file.name.split('.').pop().toLowerCase();
            const createResponse = await fetch('/knowledge/font/create/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': getCookie('csrftoken')
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
            
            // Sucesso!
            if (typeof toaster !== 'undefined') {
                toaster.success(`Fonte ${fontName} enviada com sucesso!`);
            }
            
            // Adicionar ID da fonte no input hidden para referência
            const fontIdInput = document.createElement('input');
            fontIdInput.type = 'hidden';
            fontIdInput.name = `fontes[${index}][font_id]`;
            fontIdInput.value = createData.data.fontId;
            fonteItem.appendChild(fontIdInput);
            
        } catch (error) {
            logger.error('Erro no upload da fonte:', error);
            if (typeof toaster !== 'undefined') {
                toaster.error('Erro ao enviar fonte: ' + error.message);
            }
            hiddenInput.value = '';
        } finally {
            input.disabled = false;
        }
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

// Inicializar fontes existentes
document.addEventListener('DOMContentLoaded', function() {
    const fontesData = window.KNOWLEDGE_FONTS || [];
    const customFontsData = window.KNOWLEDGE_CUSTOM_FONTS || [];
    
    // Adicionar fontes do Typography (Google Fonts)
    if (fontesData.length > 0) {
        fontesData.forEach(font => {
            addFonte(font.tipo, font.nome, font.variante, font.uso, font.arquivo_url);
        });
    }
    
    // Adicionar fontes customizadas (Upload)
    if (customFontsData.length > 0) {
        customFontsData.forEach(font => {
            logger.debug('DEBUG: Adicionando fonte customizada:', font);
            // Passar ID como 5º parâmetro para ser adicionado como data-font-id
            addFonte('UPLOAD', font.name, '', font.font_type.toUpperCase(), font.s3_url, font.id);
        });
    }
    
    // Não adicionar fonte padrão - deixar vazio para usuário escolher
});

// Expor funções globalmente
window.addFonte = addFonte;
window.toggleFonteItem = toggleFonteItem;
window.selectFonteTipo = selectFonteTipo;
window.updateFontePreview = updateFontePreview;
window.updateFonteUso = updateFonteUso;
window.removeFonte = removeFonte;
window.handleFonteUpload = handleFonteUpload;
