/**
 * ImagePreviewLoader - Lazy loading de imagens S3 com Presigned URLs
 * Seguindo padrão do guia Django S3
 * 
 * Uso:
 *   const loader = new ImagePreviewLoader('/knowledge/preview-url/');
 *   loader.observeAll('.lazy-s3-image');
 */

class ImagePreviewLoader {
    constructor(previewUrlEndpoint) {
        this.previewUrlEndpoint = previewUrlEndpoint;
        this.cache = new Map();  // Cache de URLs
        
        // IntersectionObserver para detectar imagens no viewport
        this.observer = new IntersectionObserver(
            this.handleIntersection.bind(this),
            {
                root: null,
                rootMargin: '50px',  // Pré-carrega 50px antes
                threshold: 0.01
            }
        );
    }
    
    /**
     * Observa todas as imagens com a classe especificada
     */
    observeAll(selector) {
        const images = document.querySelectorAll(selector);
        images.forEach(img => this.observe(img));
    }
    
    /**
     * Observa uma imagem específica
     */
    observe(imageElement) {
        this.observer.observe(imageElement);
    }
    
    /**
     * Callback quando imagem entra/sai do viewport
     */
    async handleIntersection(entries) {
        for (const entry of entries) {
            if (entry.isIntersecting) {
                const img = entry.target;
                const s3Key = img.getAttribute('data-lazy-load');
                
                // Validar s3Key
                if (!s3Key || s3Key === 'undefined' || s3Key === '#') {
                    logger.warn('s3Key inválido:', s3Key);
                    continue;
                }
                
                // Já carregada? Pular
                if (img.dataset.loaded === 'true') continue;
                
                try {
                    // Mostrar loading
                    img.classList.add('loading');
                    
                    // Obter URL do preview
                    const previewUrl = await this.getPreviewUrl(s3Key);
                    
                    // Carregar imagem
                    await this.loadImage(img, previewUrl);
                    
                    // Marcar como carregada
                    img.dataset.loaded = 'true';
                    img.classList.remove('loading');
                    img.classList.add('loaded');
                    
                    // Parar de observar
                    this.observer.unobserve(img);
                    
                } catch (error) {
                    logger.error('Erro ao carregar preview:', error);
                    img.classList.remove('loading');
                    img.classList.add('error');
                    
                    // Mostrar imagem de erro
                    img.src = '/static/images/image-error.png';
                }
            }
        }
    }
    
    /**
     * Obtém Presigned URL do backend (com cache)
     */
    async getPreviewUrl(s3Key) {
        // Verificar cache
        if (this.cache.has(s3Key)) {
            const cached = this.cache.get(s3Key);
            
            // URL ainda válida? (expira em 55 minutos)
            if (Date.now() - cached.timestamp < 55 * 60 * 1000) {
                return cached.url;
            }
        }
        
        // Buscar do backend
        const response = await fetch(
            `${this.previewUrlEndpoint}?s3_key=${encodeURIComponent(s3Key)}`,
            {
                headers: {
                    'X-CSRFToken': this.getCookie('csrftoken')
                }
            }
        );
        
        if (!response.ok) {
            throw new Error(`Erro HTTP: ${response.status}`);
        }
        
        const data = await response.json();
        const previewUrl = data.data.previewUrl;
        
        // Salvar no cache
        this.cache.set(s3Key, {
            url: previewUrl,
            timestamp: Date.now()
        });
        
        return previewUrl;
    }
    
    /**
     * Carrega imagem (Promise que resolve quando carregada)
     */
    loadImage(imgElement, url) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            
            img.onload = () => {
                imgElement.src = url;
                resolve();
            };
            
            img.onerror = () => {
                reject(new Error('Falha ao carregar imagem'));
            };
            
            img.src = url;
        });
    }
    
    /**
     * Obtém cookie CSRF
     */
    getCookie(name) {
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
     * Limpa cache (chamar periodicamente)
     */
    clearCache() {
        this.cache.clear();
    }
}

// Inicialização automática
document.addEventListener('DOMContentLoaded', function() {
    const loader = new ImagePreviewLoader('/knowledge/preview-url/');
    
    // Observar todas as imagens com data-lazy-load
    const images = document.querySelectorAll('img[data-lazy-load]');
    images.forEach(img => loader.observe(img));
    
    // Expor globalmente para uso em uploads dinâmicos
    window.imagePreviewLoader = loader;
});
