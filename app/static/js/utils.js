/**
 * UTILS.JS - Funções utilitárias globais
 * Centraliza funções comuns usadas em múltiplos arquivos
 */

/**
 * Obtém valor de cookie pelo nome
 * @param {string} name - Nome do cookie
 * @returns {string|null} - Valor do cookie ou null
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
 * Formata bytes para formato legível (KB, MB, GB)
 * @param {number} bytes - Tamanho em bytes
 * @param {number} decimals - Casas decimais (padrão: 2)
 * @returns {string} - Tamanho formatado
 */
function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

/**
 * Debounce function - Atrasa execução até que chamadas parem
 * @param {Function} func - Função a ser executada
 * @param {number} wait - Tempo de espera em ms
 * @returns {Function} - Função debounced
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Throttle function - Limita execução a uma vez por intervalo
 * @param {Function} func - Função a ser executada
 * @param {number} limit - Intervalo mínimo em ms
 * @returns {Function} - Função throttled
 */
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

/**
 * Valida se string é email válido
 * @param {string} email - Email a validar
 * @returns {boolean} - True se válido
 */
function isValidEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(String(email).toLowerCase());
}

/**
 * Valida se string é URL válida
 * @param {string} url - URL a validar
 * @returns {boolean} - True se válido
 */
function isValidUrl(url) {
    try {
        new URL(url);
        return true;
    } catch (_) {
        return false;
    }
}

/**
 * Escapa HTML para prevenir XSS
 * @param {string} text - Texto a escapar
 * @returns {string} - Texto escapado
 */
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

/**
 * Gera ID único
 * @returns {string} - ID único
 */
function generateUniqueId() {
    return 'id-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
}

/**
 * Copia texto para clipboard
 * @param {string} text - Texto a copiar
 * @returns {Promise<boolean>} - True se copiado com sucesso
 */
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        return true;
    } catch (err) {
        logger.error('Erro ao copiar:', err);
        return false;
    }
}

/**
 * Scroll suave até elemento
 * @param {string|HTMLElement} target - Seletor CSS ou elemento
 * @param {number} offset - Offset em pixels (padrão: 0)
 */
function scrollToElement(target, offset = 0) {
    const element = typeof target === 'string' ? document.querySelector(target) : target;
    if (!element) return;
    
    const elementPosition = element.getBoundingClientRect().top;
    const offsetPosition = elementPosition + window.pageYOffset - offset;
    
    window.scrollTo({
        top: offsetPosition,
        behavior: 'smooth'
    });
}

/**
 * Aguarda tempo especificado
 * @param {number} ms - Milissegundos
 * @returns {Promise} - Promise que resolve após tempo
 */
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// Expor funções globalmente
window.getCookie = getCookie;
window.formatBytes = formatBytes;
window.debounce = debounce;
window.throttle = throttle;
window.isValidEmail = isValidEmail;
window.isValidUrl = isValidUrl;
window.escapeHtml = escapeHtml;
window.generateUniqueId = generateUniqueId;
window.copyToClipboard = copyToClipboard;
window.scrollToElement = scrollToElement;
window.sleep = sleep;
