// Accordion functionality for form blocks
// Para reverter: basta remover o script do template

document.addEventListener('DOMContentLoaded', function() {
    const formBlocks = document.querySelectorAll('.form-block');
    
    formBlocks.forEach(function(block) {
        const header = block.querySelector('.form-block-header');
        const body = block.querySelector('.form-block-body');
        
        if (!header || !body) return;
        
        // Adicionar classe de controle
        block.classList.add('accordion-block');
        
        // Primeiro bloco aberto por padrão
        if (block.id === 'bloco-institucional') {
            block.classList.add('accordion-open');
        } else {
            block.classList.add('accordion-closed');
        }
        
        // Adicionar ícone de toggle
        const toggleIcon = document.createElement('span');
        toggleIcon.className = 'accordion-toggle';
        toggleIcon.innerHTML = '▼';
        header.appendChild(toggleIcon);
        
        // Tornar header clicável
        header.style.cursor = 'pointer';
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
    
    // Permitir que os pills abram o bloco correspondente
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
