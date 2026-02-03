/**
 * POSTS-MODAL.JS - Modal de Gerar Post
 * VERSÃO: 2026-02-02 21:15 - LOGS REMOVIDOS
 */

(function() {
    'use strict';

    // ============================================
    // DOM ELEMENTS
    // ============================================
    const dom = {
        modal: document.getElementById('modalGerarPost'),
        form: document.getElementById('formGerarPost'),
        redePost: document.getElementById('redePost'),
        formatOptions: document.getElementById('formatOptions'),
        carrosselToggle: document.getElementById('carrosselToggle'),
        carrosselQtyField: document.getElementById('carrosselQtyField'),
        qtdImagens: document.getElementById('qtdImagens'),
        temaPost: document.getElementById('temaPost'),
        temaContador: document.getElementById('temaContador'),
        refImgs: document.getElementById('refImgs'),
        refImgsInfo: document.getElementById('refImgsInfo'),
        refImgsPreview: document.getElementById('refImgsPreview'),
        btnEnviarPost: document.getElementById('btnEnviarPost')
    };

    // Pending uploads para S3
    const pendingUploads = [];

    // ============================================
    // CONTADOR DE CARACTERES
    // ============================================
    function updateTemaCounter() {
        if (!dom.temaPost || !dom.temaContador) return;
        const length = dom.temaPost.value.length;
        dom.temaContador.textContent = `${length}/3000`;
    }

    if (dom.temaPost) {
        dom.temaPost.addEventListener('input', updateTemaCounter);
    }

    // ============================================
    // FORMATO - CHIPS
    // ============================================
    function syncFormatUI() {
        if (!dom.formatOptions) return;

        const formatRadios = dom.formatOptions.querySelectorAll('input[type="radio"]');
        const bothSelected = Array.from(formatRadios).some(r => r.checked && r.value === 'both');

        // Atualizar visual dos chips
        dom.formatOptions.querySelectorAll('.chip-choice').forEach(label => {
            const input = label.querySelector('input[type="radio"]');
            const isActive = !!(input && input.checked);
            label.classList.toggle('active', isActive);
        });

        // REGRA: Feed + Stories desabilita Carrossel
        if (dom.carrosselToggle) {
            if (bothSelected) {
                dom.carrosselToggle.classList.add('chip-disabled');
                dom.carrosselToggle.setAttribute('aria-disabled', 'true');
                dom.carrosselToggle.disabled = true;
                setCarrossel(false);
            } else {
                dom.carrosselToggle.classList.remove('chip-disabled');
                dom.carrosselToggle.removeAttribute('aria-disabled');
                dom.carrosselToggle.disabled = false;
            }
        }
    }

    // Event listeners para formato
    if (dom.formatOptions) {
        const formatRadios = dom.formatOptions.querySelectorAll('input[type="radio"]');
        formatRadios.forEach(radio => {
            radio.addEventListener('change', syncFormatUI);
        });

        // Click nos labels
        dom.formatOptions.querySelectorAll('.chip-choice').forEach(label => {
            label.addEventListener('click', () => {
                const radio = label.querySelector('input[type="radio"]');
                if (radio) {
                    radio.checked = true;
                    syncFormatUI();
                }
            });
        });

        syncFormatUI();
    }

    // ============================================
    // CTA TOGGLE
    // ============================================
    const ctaOptions = document.querySelectorAll('.cta-toggle-option');
    ctaOptions.forEach(option => {
        option.addEventListener('click', () => {
            ctaOptions.forEach(opt => opt.classList.remove('active'));
            option.classList.add('active');
            const radio = option.querySelector('input[type="radio"]');
            if (radio) radio.checked = true;
        });
    });

    // ============================================
    // CARROSSEL TOGGLE
    // ============================================
    function setCarrossel(enabled) {
        if (!dom.carrosselToggle || !dom.carrosselQtyField) {
            console.warn('⚠️ Elementos de carrossel não encontrados');
            return;
        }
        
        dom.carrosselToggle.classList.toggle('active', enabled);
        dom.carrosselToggle.setAttribute('aria-pressed', enabled ? 'true' : 'false');
        dom.carrosselQtyField.hidden = !enabled;
        dom.carrosselQtyField.style.display = enabled ? 'block' : 'none';
        
        // Atualizar texto do botão
        dom.carrosselToggle.textContent = enabled ? 'Desativar' : 'Ativar';
    }

    if (dom.carrosselToggle) {
        dom.carrosselToggle.addEventListener('click', (e) => {
            e.preventDefault();
            if (dom.carrosselToggle.disabled) {
                window.logger?.debug('Carrossel está desabilitado');
                return;
            }
            const enabled = !dom.carrosselToggle.classList.contains('active');
            window.logger?.debug('Toggle carrossel - novo estado:', enabled);
            setCarrossel(enabled);
        });
        window.logger?.debug('Event listener de carrossel registrado');
    } else {
        window.logger?.warn('Botão carrosselToggle não encontrado');
    }

    // ============================================
    // CONTROLES DE QUANTIDADE
    // ============================================
    const qtyButtons = document.querySelectorAll('#carrosselQtyField button[data-step]');
    qtyButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            if (!dom.qtdImagens) return;
            const min = Number(dom.qtdImagens.min) || 2;
            const max = Number(dom.qtdImagens.max) || 5;
            const step = Number(btn.dataset.step) || 0;
            let current = Number(dom.qtdImagens.value) || 3;
            
            current += step;
            if (current < min) current = min;
            if (current > max) current = max;
            
            dom.qtdImagens.value = current;
        });
    });

    // ============================================
    // UPLOAD DE IMAGENS DE REFERÊNCIA
    // ============================================
    async function handleReferenceUpload(event) {
        const files = event.target.files;
        if (!files || files.length === 0) return;

        // Validar quantidade máxima
        const totalFiles = pendingUploads.length + files.length;
        if (totalFiles > 5) {
            window.toaster?.error('Máximo de 5 imagens permitido');
            event.target.value = '';
            return;
        }

        for (let file of files) {
            try {
                // Validar tipo
                if (!file.type.match(/^image\/(jpeg|jpg|png)$/)) {
                    window.toaster?.error(`${file.name}: Apenas JPG ou PNG permitido`);
                    continue;
                }

                // Validar tamanho (5MB)
                if (file.size > 5 * 1024 * 1024) {
                    window.toaster?.error(`${file.name}: Tamanho máximo 5MB`);
                    continue;
                }

                // Gerar preview local
                const preview = await generatePreview(file);
                const tempId = 'temp-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);

                pendingUploads.push({
                    file: file,
                    preview: preview,
                    tempId: tempId,
                    name: file.name
                });

                addPreviewItem(preview, file.name, tempId);
                window.toaster?.success(`${file.name} adicionado`);

            } catch (error) {
                window.logger?.error('Erro ao processar imagem:', error);
                window.toaster?.error(`Erro: ${file.name}`);
            }
        }

        event.target.value = '';
        updateUploadInfo();
    }

    function generatePreview(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    }

    function addPreviewItem(previewUrl, name, tempId) {
        if (!dom.refImgsPreview) return;

        const item = document.createElement('div');
        item.className = 'upload-preview-item';
        item.dataset.tempId = tempId;
        item.innerHTML = `
            <img src="${previewUrl}" alt="${name}">
            <button type="button" class="remove-btn" onclick="window.removeReferenceImage('${tempId}')" title="Remover">×</button>
        `;

        dom.refImgsPreview.appendChild(item);
    }

    function updateUploadInfo() {
        if (!dom.refImgsInfo) return;

        if (pendingUploads.length === 0) {
            dom.refImgsInfo.textContent = 'Nenhum arquivo selecionado — Máx. 5 imagens (.JPG ou .PNG)';
        } else {
            const names = pendingUploads.map(u => u.name).join(', ');
            dom.refImgsInfo.textContent = `${pendingUploads.length} arquivo(s): ${names}`;
        }
    }

    // Função global para remover imagem
    window.removeReferenceImage = function(tempId) {
        const index = pendingUploads.findIndex(u => u.tempId === tempId);
        if (index > -1) {
            pendingUploads.splice(index, 1);
        }

        const item = dom.refImgsPreview?.querySelector(`[data-temp-id="${tempId}"]`);
        if (item) {
            item.remove();
        }

        updateUploadInfo();
        window.toaster?.info('Imagem removida');
    };

    if (dom.refImgs) {
        dom.refImgs.addEventListener('change', handleReferenceUpload);
    }

    // ============================================
    // UPLOAD PARA S3
    // ============================================
    async function uploadReferencesToS3() {
        if (pendingUploads.length === 0) return [];

        const uploadedUrls = [];

        for (let upload of pendingUploads) {
            try {
                // 1. Obter Presigned URL
                const urlResponse = await fetch('/posts/reference/upload-url/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-CSRFToken': window.CSRF_TOKEN || ''
                    },
                    body: new URLSearchParams({
                        fileName: upload.file.name,
                        fileType: upload.file.type,
                        fileSize: upload.file.size
                    })
                });

                if (!urlResponse.ok) {
                    const errorText = await urlResponse.text();
                    console.error('Erro na resposta:', errorText);
                    throw new Error('Erro ao obter URL de upload');
                }

                const urlData = await urlResponse.json();
                if (!urlData.success) throw new Error(urlData.error || 'Erro ao obter URL');

                const { upload_url, s3_key, organization_id } = urlData.data;

                // 2. Upload para S3 com headers completos
                const uploadHeaders = {
                    'Content-Type': upload.file.type,
                    'x-amz-server-side-encryption': 'AES256',
                    'x-amz-storage-class': 'INTELLIGENT_TIERING',
                    'x-amz-meta-original-name': upload.file.name,
                    'x-amz-meta-organization-id': String(organization_id || '0'),
                    'x-amz-meta-category': 'posts',
                    'x-amz-meta-upload-timestamp': Math.floor(Date.now() / 1000).toString()
                };

                const s3Response = await fetch(upload_url, {
                    method: 'PUT',
                    body: upload.file,
                    headers: uploadHeaders
                });

                if (!s3Response.ok) throw new Error('Erro ao fazer upload para S3');

                // 3. Confirmar upload
                const confirmResponse = await fetch('/posts/reference/create/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': window.CSRF_TOKEN || ''
                    },
                    body: JSON.stringify({
                        s3Key: s3_key,
                        name: upload.file.name.replace(/\.(png|jpg|jpeg)$/i, '')
                    })
                });

                if (!confirmResponse.ok) throw new Error('Erro ao confirmar upload');

                const confirmData = await confirmResponse.json();
                if (!confirmData.success) throw new Error(confirmData.error || 'Erro ao confirmar');

                uploadedUrls.push({
                    name: upload.file.name,
                    s3_key: s3_key,
                    s3_url: confirmData.data.s3_url
                });

            } catch (error) {
                window.logger?.error('Erro ao fazer upload:', error);
                throw error;
            }
        }

        return uploadedUrls;
    }

    // ============================================
    // SUBMIT DO FORMULÁRIO
    // ============================================
    async function handleSubmit(event) {
        event.preventDefault();

        if (!dom.form) {
            console.error('Formulário não encontrado');
            return;
        }

        try {
            // Validações
            if (!dom.redePost?.value) {
                console.warn('⚠️ Rede social não selecionada');
                window.toaster?.error('Selecione uma rede social');
                return;
            }

            if (!dom.temaPost?.value.trim()) {
                console.warn('⚠️ Tema não preenchido');
                window.toaster?.error('Digite o tema do post');
                return;
            }

            // Desabilitar botão
            if (dom.btnEnviarPost) {
                dom.btnEnviarPost.disabled = true;
                dom.btnEnviarPost.textContent = 'Enviando...';
            }

            // Upload de imagens para S3
            let referenceImages = [];
            if (pendingUploads.length > 0) {
                window.toaster?.info('Fazendo upload das imagens...');
                referenceImages = await uploadReferencesToS3();
            }

            // Coletar dados do formulário
            const formatRadio = document.querySelector('input[name="formatOption"]:checked');
            const ctaRadio = document.querySelector('input[name="ctaOption"]:checked');
            const carrosselAtivo = dom.carrosselToggle?.classList.contains('active') && !dom.carrosselToggle.disabled;

            const payload = {
                rede_social: dom.redePost.value,
                formato: formatRadio?.value || 'feed',
                cta_requested: ctaRadio?.value === 'sim',
                is_carousel: carrosselAtivo,
                image_count: carrosselAtivo ? Number(dom.qtdImagens?.value || 3) : 1,
                tema: dom.temaPost.value.trim(),
                reference_images: referenceImages
            };

            // Enviar para backend
            const response = await fetch('/posts/gerar/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.CSRF_TOKEN || ''
                },
                body: JSON.stringify(payload)
            });

            const result = await response.json();

            if (!response.ok || !result.success) {
                console.error('Erro na resposta:', result.error);
                throw new Error(result.error || 'Erro ao criar post');
            }
            window.toaster?.success(result.data.message || 'Post criado com sucesso!');
            window.logger?.info('Post criado:', result.data);
            
            // Fechar modal e resetar
            if (typeof window.closeModal === 'function') {
                window.closeModal('modalGerarPost');
            }
            resetForm();
            
            // Opcional: Recarregar página para mostrar novo post
            setTimeout(() => {
                window.location.reload();
            }, 1500);

        } catch (error) {
            window.logger?.error('Erro ao enviar post:', error);
            window.toaster?.error('Erro ao enviar post. Tente novamente.');
        } finally {
            // Reabilitar botão
            if (dom.btnEnviarPost) {
                dom.btnEnviarPost.disabled = false;
                dom.btnEnviarPost.textContent = 'Enviar ao agente';
            }
        }
    }

    function resetForm() {
        if (!dom.form) return;

        dom.form.reset();
        pendingUploads.length = 0;
        if (dom.refImgsPreview) dom.refImgsPreview.innerHTML = '';
        updateUploadInfo();
        updateTemaCounter();
        setCarrossel(false);
        syncFormatUI();
    }

    if (dom.form) {
        dom.form.addEventListener('submit', handleSubmit);
    }

    // ============================================
    // INICIALIZAÇÃO
    // ============================================
    
    // Garantir estado inicial correto do carrossel
    if (dom.carrosselToggle && dom.carrosselQtyField) {
        // Sempre iniciar com carrossel desativado
        dom.carrosselToggle.classList.remove('active');
        dom.carrosselToggle.setAttribute('aria-pressed', 'false');
        dom.carrosselToggle.textContent = 'Ativar';
        
        // Forçar esconder o campo com display none
        dom.carrosselQtyField.hidden = true;
        dom.carrosselQtyField.style.display = 'none';
    }
    
    window.logger?.debug('Posts Modal JS carregado');

})();
