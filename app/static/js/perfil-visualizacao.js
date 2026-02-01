/**
 * Perfil Visualização - JavaScript
 * Lazy loading de imagens e interações
 */

document.addEventListener('DOMContentLoaded', function() {
    
    // Lazy Loading de Imagens
    const lazyImages = document.querySelectorAll('.lazy-load, .lazy-load-image');
    
    // Função para carregar imagem via S3 key
    async function loadImageFromS3Key(img, s3Key) {
        try {
            const response = await fetch(`/knowledge/preview-url/?s3_key=${encodeURIComponent(s3Key)}`);
            const data = await response.json();
            
            if (data.success && data.data.previewUrl) {
                img.src = data.data.previewUrl;
                img.addEventListener('load', () => {
                    img.classList.add('loaded');
                });
            } else {
                console.error('Erro ao carregar imagem:', data.error);
                img.classList.add('error');
            }
        } catch (error) {
            console.error('Erro ao buscar URL de preview:', error);
            img.classList.add('error');
        }
    }
    
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    
                    // Se já tem src válido, apenas adicionar classe loaded
                    if (img.src && img.src !== window.location.href + '#') {
                        img.classList.add('loaded');
                        observer.unobserve(img);
                        return;
                    }
                    
                    // Se tem data-s3-key, buscar URL assinada
                    if (img.dataset.s3Key) {
                        loadImageFromS3Key(img, img.dataset.s3Key);
                        observer.unobserve(img);
                        return;
                    }
                    
                    // Se tem data-src, carregar imagem diretamente
                    if (img.dataset.src) {
                        img.src = img.dataset.src;
                        img.addEventListener('load', () => {
                            img.classList.add('loaded');
                        });
                        observer.unobserve(img);
                    }
                }
            });
        }, {
            rootMargin: '50px'
        });
        
        lazyImages.forEach(img => {
            imageObserver.observe(img);
        });
    } else {
        // Fallback para navegadores sem suporte
        lazyImages.forEach(img => {
            if (img.dataset.s3Key) {
                loadImageFromS3Key(img, img.dataset.s3Key);
            } else if (img.dataset.src) {
                img.src = img.dataset.src;
            }
            img.classList.add('loaded');
        });
    }
    
    // Smooth scroll para links internos
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
    
    // Log para debug
    console.log('✅ Perfil Visualização carregado');
    console.log(`📊 ${lazyImages.length} imagens com lazy loading`);
});
