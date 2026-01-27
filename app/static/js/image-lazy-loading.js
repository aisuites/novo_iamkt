/**
 * IMAGE LAZY LOADING
 * Carrega previews de imagens apenas quando necessário usando Intersection Observer
 */

(function() {
    'use strict';

    /**
     * Carrega preview de uma imagem
     */
    async function loadImagePreview(imageElement) {
        if (imageElement.dataset.loaded === 'true') {
            return; // Já carregada
        }

        const imageId = imageElement.dataset.imageId;
        const imageType = imageElement.dataset.imageType; // 'logo' ou 'reference'
        
        if (!imageId || !imageType) {
            logger.error('Image element missing data-image-id or data-image-type');
            return;
        }

        try {
            // Buscar URL assinada do backend
            const response = await fetch(`/knowledge/${imageType}/${imageId}/signed-url/`);
            
            if (!response.ok) {
                throw new Error('Failed to get signed URL');
            }
            
            const data = await response.json();
            
            // Atualizar src da imagem
            imageElement.src = data.signed_url;
            imageElement.dataset.loaded = 'true';
            
            // Remover loading spinner se existir
            const spinner = imageElement.parentElement.querySelector('.image-loading-spinner');
            if (spinner) {
                spinner.remove();
            }
            
        } catch (error) {
            logger.error('Error loading image preview:', error);
            
            // Mostrar placeholder de erro
            imageElement.src = '/static/images/placeholder-error.png';
            imageElement.alt = 'Erro ao carregar imagem';
        }
    }

    /**
     * Inicializar Intersection Observer
     */
    function init() {
        // Selecionar todas as imagens com lazy loading
        const lazyImages = document.querySelectorAll('img[data-lazy-load="true"]');
        
        if (lazyImages.length === 0) {
            return; // Nenhuma imagem para carregar
        }

        // Criar Intersection Observer
        const observerOptions = {
            root: null, // viewport
            rootMargin: '50px', // Carregar 50px antes de entrar no viewport
            threshold: 0.01
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    loadImagePreview(img);
                    observer.unobserve(img); // Parar de observar após carregar
                }
            });
        }, observerOptions);

        // Observar todas as imagens
        lazyImages.forEach(img => {
            observer.observe(img);
        });
    }

    // Inicializar quando DOM estiver pronto
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Expor função globalmente para uso manual se necessário
    window.loadImagePreview = loadImagePreview;

})();
