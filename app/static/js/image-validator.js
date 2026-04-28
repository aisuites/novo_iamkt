/**
 * ImageValidator - Valida imagem no frontend antes do upload
 * Seguindo padrão do guia Django S3
 */

class ImageValidator {
    constructor(category) {
        this.category = category;
        
        // Configurações por categoria
        this.config = {
            logos: {
                minDimensions: { width: 100, height: 100 },
                maxDimensions: { width: 10000, height: 10000 },
                maxFileSize: 5 * 1024 * 1024,  // 5MB
                allowedTypes: ['image/png', 'image/jpeg', 'image/svg+xml', 'image/webp']
            },
            references: {
                minDimensions: { width: 200, height: 200 },
                maxDimensions: { width: 10000, height: 10000 },
                maxFileSize: 10 * 1024 * 1024,  // 10MB
                allowedTypes: ['image/png', 'image/jpeg', 'image/gif', 'image/webp']
            },
            fonts: {
                maxFileSize: 2 * 1024 * 1024,  // 2MB
                allowedTypes: ['font/ttf', 'font/otf', 'font/woff', 'font/woff2', 'application/x-font-ttf', 'application/x-font-otf']
            },
            posts: {
                minDimensions: { width: 200, height: 200 },
                maxDimensions: { width: 10000, height: 10000 },
                maxFileSize: 10 * 1024 * 1024,  // 10MB
                allowedTypes: ['image/png', 'image/jpeg', 'image/webp']
            }
        };
    }
    
    /**
     * Valida arquivo completo
     */
    async validate(file) {
        const errors = [];
        
        // 1. Validar tipo
        const typeError = this.validateFileType(file);
        if (typeError) errors.push(typeError);
        
        // 2. Validar tamanho
        const sizeError = this.validateFileSize(file);
        if (sizeError) errors.push(sizeError);
        
        // 3. Validar dimensões (se imagem)
        if (file.type.startsWith('image/') && file.type !== 'image/svg+xml') {
            const dimensionsError = await this.validateDimensions(file);
            if (dimensionsError) errors.push(dimensionsError);
        }
        
        return {
            valid: errors.length === 0,
            errors: errors
        };
    }
    
    /**
     * Valida tipo de arquivo
     */
    validateFileType(file) {
        const config = this.config[this.category];
        
        if (!config) {
            return `Categoria inválida: ${this.category}`;
        }
        
        if (!config.allowedTypes.includes(file.type)) {
            return `Tipo não permitido. Aceitos: ${config.allowedTypes.join(', ')}`;
        }
        
        return null;
    }
    
    /**
     * Valida tamanho do arquivo
     */
    validateFileSize(file) {
        const config = this.config[this.category];
        
        if (file.size > config.maxFileSize) {
            const maxMB = Math.round(config.maxFileSize / (1024 * 1024));
            return `Arquivo muito grande. Máximo: ${maxMB}MB`;
        }
        
        if (file.size === 0) {
            return 'Arquivo vazio';
        }
        
        return null;
    }
    
    /**
     * Valida dimensões da imagem
     */
    async validateDimensions(file) {
        const config = this.config[this.category];
        
        if (!config.minDimensions && !config.maxDimensions) {
            return null;  // Categoria não requer validação de dimensões
        }
        
        return new Promise((resolve) => {
            const img = new Image();
            const url = URL.createObjectURL(file);
            
            img.onload = () => {
                URL.revokeObjectURL(url);
                
                const { width, height } = img;
                
                // Verificar mínimo
                if (config.minDimensions) {
                    if (width < config.minDimensions.width || height < config.minDimensions.height) {
                        resolve(
                            `Dimensões muito pequenas. Mínimo: ${config.minDimensions.width}x${config.minDimensions.height}px`
                        );
                        return;
                    }
                }
                
                // Verificar máximo
                if (config.maxDimensions) {
                    if (width > config.maxDimensions.width || height > config.maxDimensions.height) {
                        resolve(
                            `Dimensões muito grandes. Máximo: ${config.maxDimensions.width}x${config.maxDimensions.height}px`
                        );
                        return;
                    }
                }
                
                resolve(null);
            };
            
            img.onerror = () => {
                URL.revokeObjectURL(url);
                resolve('Erro ao carregar imagem para validação');
            };
            
            img.src = url;
        });
    }
    
    /**
     * Gera preview da imagem
     */
    async generatePreview(file, maxWidth = 300, maxHeight = 300) {
        return new Promise((resolve) => {
            const reader = new FileReader();
            
            reader.onload = (e) => {
                const img = new Image();
                
                img.onload = () => {
                    // Calcular dimensões do preview mantendo aspect ratio
                    let width = img.width;
                    let height = img.height;
                    
                    if (width > maxWidth) {
                        height = (height * maxWidth) / width;
                        width = maxWidth;
                    }
                    
                    if (height > maxHeight) {
                        width = (width * maxHeight) / height;
                        height = maxHeight;
                    }
                    
                    // Criar canvas para resize
                    const canvas = document.createElement('canvas');
                    canvas.width = width;
                    canvas.height = height;
                    
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0, width, height);
                    
                    resolve({
                        dataUrl: canvas.toDataURL(file.type),
                        width: img.width,
                        height: img.height
                    });
                };
                
                img.onerror = () => {
                    resolve(null);
                };
                
                img.src = e.target.result;
            };
            
            reader.onerror = () => {
                resolve(null);
            };
            
            reader.readAsDataURL(file);
        });
    }
}
