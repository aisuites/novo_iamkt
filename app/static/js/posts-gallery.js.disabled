/**
 * Posts Gallery - Funcionalidade de galeria de miniaturas
 * Permite trocar imagem principal ao clicar nas miniaturas
 */

(function() {
    'use strict';

    // Cache de imagens em memória
    const imageCache = {};

    /**
     * Obter CSRF token do cookie
     */
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

    /**
     * Configurar galeria de miniaturas
     */
    function setupGallery() {
        const gallery = document.getElementById('postGallery');
        if (!gallery) {
            return;
        }

        const thumbButtons = gallery.querySelectorAll('.gallery-thumb');
        const mainImage = document.querySelector('.post-main-image');
        
        if (!mainImage || thumbButtons.length === 0) {
            return;
        }

        thumbButtons.forEach((btn, index) => {
            btn.addEventListener('click', async function(e) {
                e.preventDefault();
                const s3Key = this.dataset.s3Key;
                
                // Verificar se imagem já está em cache
                if (imageCache[s3Key]) {
                    mainImage.src = imageCache[s3Key];
                    mainImage.setAttribute('data-lazy-load', s3Key);
                    
                    // Atualizar estado ativo dos botões
                    thumbButtons.forEach(b => b.classList.remove('active'));
                    this.classList.add('active');
                    return;
                }
                
                // Se não está em cache, buscar da API
                try {
                    const url = `/knowledge/preview-url/?s3_key=${encodeURIComponent(s3Key)}`;
                    
                    const response = await fetch(url, {
                        method: 'GET',
                        headers: {
                            'Content-Type': 'application/json'
                        }
                    });
                    
                    if (!response.ok) {
                        throw new Error(`Erro ao buscar URL da imagem: ${response.status}`);
                    }
                    
                    const data = await response.json();
                    
                    if (data.success && data.data && data.data.previewUrl) {
                        // Salvar no cache
                        imageCache[s3Key] = data.data.previewUrl;
                        
                        // Atualizar imagem principal
                        mainImage.src = imageCache[s3Key];
                        mainImage.setAttribute('data-lazy-load', s3Key);
                        
                        // Atualizar estado ativo dos botões
                        thumbButtons.forEach(b => b.classList.remove('active'));
                        this.classList.add('active');
                    } else {
                        console.error('❌ Resposta inválida da API:', data);
                    }
                } catch (error) {
                    console.error('❌ Erro ao carregar imagem:', error);
                }
            });
        });
    }

    // Expor função globalmente
    window.setupPostGallery = setupGallery;

    // Inicializar quando DOM estiver pronto
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            setTimeout(setupGallery, 600);
        });
    } else {
        setTimeout(setupGallery, 600);
    }

})();
