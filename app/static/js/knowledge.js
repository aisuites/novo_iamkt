/**
 * KNOWLEDGE.JS - Base de Conhecimento FEMME
 * Baseado em accordion.js (arquivo de referência)
 * Accordion colapsável com toggle e scroll suave
 */

document.addEventListener('DOMContentLoaded', function() {
    const formBlocks = document.querySelectorAll('.form-block');
    
    formBlocks.forEach(function(block) {
        const header = block.querySelector('.form-block-header');
        const body = block.querySelector('.form-block-body');
        
        if (!header || !body) return;
        
        // Adicionar classe de controle
        block.classList.add('accordion-block');
        
        // Todos os blocos fechados por padrão
        block.classList.add('accordion-closed');
        
        // Adicionar ícone de toggle dentro de .form-block-header-right
        const headerRight = header.querySelector('.form-block-header-right');
        const toggleIcon = document.createElement('span');
        toggleIcon.className = 'accordion-toggle';
        toggleIcon.innerHTML = '▼';
        
        if (headerRight) {
            headerRight.appendChild(toggleIcon);
        } else {
            header.appendChild(toggleIcon);
        }
        
        // Tornar header clicável
        header.addEventListener('click', function() {
            const isOpen = block.classList.contains('accordion-open');
            
            if (isOpen) {
                block.classList.remove('accordion-open');
                block.classList.add('accordion-closed');
            } else {
                block.classList.remove('accordion-closed');
                block.classList.add('accordion-open');
                
                // Scroll suave até o bloco
                setTimeout(function() {
                    block.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }, 300);
            }
        });
    });
    
    // Pills de navegação
    const pills = document.querySelectorAll('.form-step-pill');
    pills.forEach(function(pill) {
        pill.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href').substring(1);
            const targetBlock = document.getElementById(targetId);
            
            if (targetBlock) {
                // Abrir o bloco
                targetBlock.classList.remove('accordion-closed');
                targetBlock.classList.add('accordion-open');
                
                // Scroll até o bloco
                setTimeout(function() {
                    targetBlock.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }, 100);
            }
        });
    });
});
