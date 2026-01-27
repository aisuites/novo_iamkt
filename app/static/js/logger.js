/**
 * LOGGER.JS - Sistema de logging condicional
 * Logs apenas em desenvolvimento, silencioso em produção
 */

const Logger = {
    // Detecta ambiente (dev ou prod)
    isDevelopment: window.location.hostname === 'localhost' || 
                   window.location.hostname === '127.0.0.1' ||
                   window.location.hostname.includes('dev') ||
                   window.location.hostname.includes('staging'),
    
    /**
     * Log informativo (apenas em dev)
     */
    log: function(...args) {
        if (this.isDevelopment) {
            console.log(...args);
        }
    },
    
    /**
     * Log de erro (sempre exibe, mas pode ser enviado para Sentry)
     */
    error: function(...args) {
        console.error(...args);
        
        // TODO: Integrar com Sentry em produção
        // if (!this.isDevelopment && window.Sentry) {
        //     Sentry.captureException(new Error(args.join(' ')));
        // }
    },
    
    /**
     * Log de warning (apenas em dev)
     */
    warn: function(...args) {
        if (this.isDevelopment) {
            console.warn(...args);
        }
    },
    
    /**
     * Log de debug (apenas em dev)
     */
    debug: function(...args) {
        if (this.isDevelopment) {
            console.debug(...args);
        }
    },
    
    /**
     * Log de informação (sempre exibe)
     */
    info: function(...args) {
        console.info(...args);
    },
    
    /**
     * Agrupa logs (apenas em dev)
     */
    group: function(label) {
        if (this.isDevelopment && console.group) {
            console.group(label);
        }
    },
    
    /**
     * Fecha grupo de logs
     */
    groupEnd: function() {
        if (this.isDevelopment && console.groupEnd) {
            console.groupEnd();
        }
    },
    
    /**
     * Tabela de dados (apenas em dev)
     */
    table: function(data) {
        if (this.isDevelopment && console.table) {
            console.table(data);
        }
    },
    
    /**
     * Timer (apenas em dev)
     */
    time: function(label) {
        if (this.isDevelopment && console.time) {
            console.time(label);
        }
    },
    
    /**
     * Finaliza timer
     */
    timeEnd: function(label) {
        if (this.isDevelopment && console.timeEnd) {
            console.timeEnd(label);
        }
    }
};

// Expor globalmente
window.logger = Logger;

// Alias para compatibilidade (opcional)
if (Logger.isDevelopment) {
    // Em dev, manter console.log funcionando
    window.log = Logger.log.bind(Logger);
} else {
    // Em prod, substituir console.log por noop
    window.log = function() {};
}
