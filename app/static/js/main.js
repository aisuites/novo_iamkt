/**
 * VibeMKT - JavaScript Principal
 * Funcionalidades globais e utilitários
 */

// Dropdown functionality (global)
document.addEventListener('DOMContentLoaded', function() {
  // Initialize all dropdowns
  const dropdowns = document.querySelectorAll('.dropdown');
  
  dropdowns.forEach(dropdown => {
    const toggle = dropdown.querySelector('.dropdown-toggle');
    const menu = dropdown.querySelector('.dropdown-menu');
    
    if (toggle && menu) {
      toggle.addEventListener('click', function(e) {
        e.stopPropagation();
        
        // Close other dropdowns
        document.querySelectorAll('.dropdown-menu.open').forEach(otherMenu => {
          if (otherMenu !== menu) {
            otherMenu.classList.remove('open');
          }
        });
        
        // Toggle current dropdown
        menu.classList.toggle('open');
        const isOpen = menu.classList.contains('open');
        toggle.setAttribute('aria-expanded', isOpen);
      });
    }
  });
  
  // Close dropdowns when clicking outside
  document.addEventListener('click', function() {
    document.querySelectorAll('.dropdown-menu.open').forEach(menu => {
      menu.classList.remove('open');
      const toggle = menu.previousElementSibling;
      if (toggle) {
        toggle.setAttribute('aria-expanded', 'false');
      }
    });
  });
  
  // Prevent closing when clicking inside dropdown
  document.querySelectorAll('.dropdown-menu').forEach(menu => {
    menu.addEventListener('click', function(e) {
      e.stopPropagation();
    });
  });
});

// FAQ Accordion functionality
function initFAQ() {
  const faqQuestions = document.querySelectorAll('.faq-question');
  
  faqQuestions.forEach(question => {
    question.addEventListener('click', function() {
      const answer = this.nextElementSibling;
      const isOpen = answer.classList.contains('open');
      
      // Close all other answers
      document.querySelectorAll('.faq-answer.open').forEach(openAnswer => {
        if (openAnswer !== answer) {
          openAnswer.classList.remove('open');
          openAnswer.style.maxHeight = '0';
        }
      });
      
      // Toggle current answer
      if (isOpen) {
        answer.classList.remove('open');
        answer.style.maxHeight = '0';
      } else {
        answer.classList.add('open');
        answer.style.maxHeight = answer.scrollHeight + 'px';
      }
    });
  });
}

// Toast notification system
function showToast(message, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `alert alert-${type}`;
  toast.style.position = 'fixed';
  toast.style.top = '20px';
  toast.style.right = '20px';
  toast.style.zIndex = '9999';
  toast.style.minWidth = '300px';
  toast.textContent = message;
  
  document.body.appendChild(toast);
  
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

// Form validation helper
function validateForm(formId) {
  const form = document.getElementById(formId);
  if (!form) return false;
  
  const requiredFields = form.querySelectorAll('[required]');
  let isValid = true;
  
  requiredFields.forEach(field => {
    if (!field.value.trim()) {
      field.style.borderColor = 'var(--femme-danger)';
      isValid = false;
    } else {
      field.style.borderColor = '';
    }
  });
  
  return isValid;
}

// Loading state helper
function setLoading(elementId, isLoading) {
  const element = document.getElementById(elementId);
  if (!element) return;
  
  if (isLoading) {
    element.classList.add('loading');
    element.disabled = true;
  } else {
    element.classList.remove('loading');
    element.disabled = false;
  }
}

// Copy to clipboard
function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => {
    showToast('Copiado para área de transferência!', 'success');
  }).catch(() => {
    showToast('Erro ao copiar', 'danger');
  });
}

// Initialize components on page load
document.addEventListener('DOMContentLoaded', function() {
  // Initialize FAQ if exists
  if (document.querySelector('.faq-wrapper')) {
    initFAQ();
  }
  
  // Auto-hide alerts after 5 seconds
  document.querySelectorAll('.alert').forEach(alert => {
    setTimeout(() => {
      alert.style.opacity = '0';
      alert.style.transition = 'opacity 0.3s';
      setTimeout(() => alert.remove(), 300);
    }, 5000);
  });
});

// Export functions for use in other scripts
window.VibeMKT = {
  showToast,
  validateForm,
  setLoading,
  copyToClipboard,
  initFAQ
};
