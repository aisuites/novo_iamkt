/**
 * IAMKT - Knowledge Navigation
 * Navegação por hero-tags com abertura automática de sanfonas
 */

(function() {
  'use strict';

  /**
   * Abre um bloco (accordion)
   */
  function openBlock(blockId) {
    const block = document.getElementById(blockId);
    if (!block) return;

    // Remover classe de fechado e adicionar classe de aberto
    block.classList.remove('accordion-closed');
    block.classList.add('accordion-open');

    // Scroll suave até o bloco
    setTimeout(() => {
      block.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
  }

  /**
   * Inicialização
   */
  function init() {
    // Adicionar event listeners nos botões hero-tag
    const heroTags = document.querySelectorAll('.hero-tag');
    
    heroTags.forEach(tag => {
      tag.addEventListener('click', function(e) {
        e.preventDefault();
        
        // Extrair ID do bloco do href (#bloco1, #bloco2, etc)
        const href = this.getAttribute('href');
        if (href && href.startsWith('#')) {
          const blockId = href.substring(1);
          openBlock(blockId);
        }
      });
    });
  }

  // Inicializar quando DOM estiver pronto
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
