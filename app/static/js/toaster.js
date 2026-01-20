/**
 * TOASTER.JS - Sistema de notificações toast
 * Exibe mensagens de sucesso, erro, aviso e info no canto superior direito
 */

class Toaster {
    constructor() {
        this.container = null;
        this.init();
    }

    init() {
        // Criar container se não existir
        if (!document.getElementById('toaster-container')) {
            this.container = document.createElement('div');
            this.container.id = 'toaster-container';
            this.container.className = 'toaster-container';
            document.body.appendChild(this.container);
        } else {
            this.container = document.getElementById('toaster-container');
        }
    }

    show(message, type = 'success', duration = 4000) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        // Ícone baseado no tipo
        const icons = {
            success: '✓',
            error: '✕',
            warning: '⚠',
            info: 'ℹ'
        };
        
        toast.innerHTML = `
            <div class="toast-icon">${icons[type] || icons.info}</div>
            <div class="toast-message">${message}</div>
            <button class="toast-close" onclick="this.parentElement.remove()">×</button>
        `;
        
        this.container.appendChild(toast);
        
        // Animação de entrada
        setTimeout(() => toast.classList.add('toast-show'), 10);
        
        // Auto-remover após duração
        setTimeout(() => {
            toast.classList.remove('toast-show');
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }

    success(message, duration) {
        this.show(message, 'success', duration);
    }

    error(message, duration) {
        this.show(message, 'error', duration);
    }

    warning(message, duration) {
        this.show(message, 'warning', duration);
    }

    info(message, duration) {
        this.show(message, 'info', duration);
    }
}

// Instância global
window.toaster = new Toaster();
