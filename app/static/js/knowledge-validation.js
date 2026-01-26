/**
 * IAMKT - Knowledge Base Form Validation
 * Validação client-side para formulário de Base de Conhecimento
 */

(function() {
  'use strict';

  // Configuração de campos obrigatórios por bloco
  const REQUIRED_FIELDS = {
    'bloco1': ['nome_empresa', 'missao', 'valores'],
    'bloco2': ['publico_externo'],
    'bloco3': ['posicionamento', 'diferenciais'],
    'bloco4': ['tom_voz_externo'],
    'bloco5': [],
    'bloco6': [],
    'bloco7': []
  };

  // Labels dos campos para mensagens amigáveis
  const FIELD_LABELS = {
    'nome_empresa': 'Nome da empresa',
    'missao': 'Missão',
    'valores': 'Valores & princípios',
    'publico_externo': 'Público externo',
    'posicionamento': 'Posicionamento de mercado',
    'diferenciais': 'Diferenciais competitivos',
    'tom_voz_externo': 'Tom de voz externo'
  };

  /**
   * Valida um campo individual
   */
  function validateField(field) {
    const value = field.value.trim();
    const isValid = value.length > 0;
    
    if (isValid) {
      field.classList.remove('field-error');
      removeFieldError(field);
    } else {
      field.classList.add('field-error');
      showFieldError(field);
    }
    
    return isValid;
  }

  /**
   * Mostra erro visual no campo
   */
  function showFieldError(field) {
    // Remover erro anterior se existir
    removeFieldError(field);
    
    // Criar mensagem de erro
    const errorMsg = document.createElement('div');
    errorMsg.className = 'field-error-message';
    errorMsg.textContent = 'Este campo é obrigatório';
    
    // Inserir após o campo
    field.parentNode.insertBefore(errorMsg, field.nextSibling);
  }

  /**
   * Remove erro visual do campo
   */
  function removeFieldError(field) {
    const errorMsg = field.parentNode.querySelector('.field-error-message');
    if (errorMsg) {
      errorMsg.remove();
    }
  }

  /**
   * Abre um bloco (accordion)
   */
  function openBlock(blockId) {
    const block = document.getElementById(blockId);
    if (block) {
      // Adicionar classe de erro
      block.classList.add('form-block--error');
      
      // Abrir o accordion
      block.classList.remove('accordion-closed');
      block.classList.add('accordion-open');
      
      // Scroll suave até o bloco
      setTimeout(() => {
        block.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
    }
  }

  /**
   * Valida todos os campos obrigatórios do formulário
   */
  function validateForm(form) {
    let isValid = true;
    const errors = [];
    const blocksWithErrors = new Set();

    // Validar cada bloco
    Object.keys(REQUIRED_FIELDS).forEach(blockId => {
      const requiredFields = REQUIRED_FIELDS[blockId];
      
      requiredFields.forEach(fieldName => {
        const field = form.querySelector(`[name="${fieldName}"]`);
        
        if (field && !validateField(field)) {
          isValid = false;
          blocksWithErrors.add(blockId);
          
          const label = FIELD_LABELS[fieldName] || fieldName;
          errors.push({
            block: blockId,
            field: fieldName,
            label: label
          });
        }
      });
    });

    // Se houver erros, abrir blocos com erro e mostrar mensagem
    if (!isValid) {
      // Abrir primeiro bloco com erro
      const firstBlockWithError = Array.from(blocksWithErrors)[0];
      if (firstBlockWithError) {
        openBlock(firstBlockWithError);
      }

      // Mostrar toast com resumo dos erros
      if (window.toaster) {
        const errorCount = errors.length;
        const blockCount = blocksWithErrors.size;
        
        window.toaster.error(
          `Existem ${errorCount} campo(s) obrigatório(s) não preenchido(s) em ${blockCount} bloco(s). Verifique os campos destacados.`,
          { duration: 8000 }
        );
      }
    }

    return isValid;
  }

  /**
   * Inicialização
   */
  function init() {
    const form = document.querySelector('.form-grid');
    if (!form) return;

    // Validação no submit
    form.addEventListener('submit', function(e) {
      if (!validateForm(form)) {
        e.preventDefault();
        return false;
      }
    });

    // Validação em tempo real (ao sair do campo)
    Object.keys(REQUIRED_FIELDS).forEach(blockId => {
      const requiredFields = REQUIRED_FIELDS[blockId];
      
      requiredFields.forEach(fieldName => {
        const field = form.querySelector(`[name="${fieldName}"]`);
        
        if (field) {
          // Validar ao sair do campo (blur)
          field.addEventListener('blur', function() {
            if (this.value.trim().length > 0) {
              validateField(this);
            }
          });

          // Remover erro ao digitar
          field.addEventListener('input', function() {
            if (this.classList.contains('field-error') && this.value.trim().length > 0) {
              this.classList.remove('field-error');
              removeFieldError(this);
            }
          });
        }
      });
    });

    // Se houver erros de validação server-side, destacar blocos
    if (window.VALIDATION_ERRORS) {
      const { blocks, fields } = window.VALIDATION_ERRORS;
      
      // Abrir e destacar blocos com erro
      if (blocks && blocks.length > 0) {
        blocks.forEach(blockNum => {
          const blockId = `bloco${blockNum}`;
          openBlock(blockId);
        });
      }

      // Destacar campos com erro
      if (fields && fields.length > 0) {
        fields.forEach(errorInfo => {
          const field = form.querySelector(`[name="${errorInfo.field}"]`);
          if (field) {
            field.classList.add('field-error');
            showFieldError(field);
          }
        });
      }
    }
  }

  // Inicializar quando DOM estiver pronto
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
