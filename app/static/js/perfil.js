/**
 * PERFIL.JS - Interações da página "Perfil da Empresa"
 * Gerencia aceitar/rejeitar sugestões e envio de dados
 */

// Variáveis globais para integração com perfil-tags.js
window.editedFields = {};
window.updateCounter = null;

document.addEventListener('DOMContentLoaded', function() {
    // Estado das decisões do usuário
    const decisions = {};
    
    // Estado das edições nos campos INFORMADO
    const editedFields = window.editedFields; // Usar referência global
    
    // Inicializar todos os cards com "Rejeitar" selecionado por padrão
    const allCards = document.querySelectorAll('.analysis-card');
    allCards.forEach(card => {
        const fieldName = card.dataset.field;
        const rejectBtn = card.querySelector('.btn-action-reject');
        const feedbackRejected = card.querySelector('.analysis-feedback-rejected');
        
        // Só processar se o card tiver sugestão (botões existem)
        if (rejectBtn && feedbackRejected) {
            // Marcar como rejeitado por padrão
            decisions[fieldName] = 'reject';
            rejectBtn.classList.add('active');
            feedbackRejected.classList.add('show');
        }
    });
    
    // Rastrear edições nos campos INFORMADO (textarea)
    const editableFields = document.querySelectorAll('.editable-field');
    editableFields.forEach(field => {
        const fieldName = field.dataset.field;
        const originalValue = field.dataset.original;
        
        field.addEventListener('input', function() {
            const currentValue = this.value.trim();
            
            // Verificar se houve mudança
            if (currentValue !== originalValue) {
                editedFields[fieldName] = currentValue;
                this.classList.add('edited');
            } else {
                delete editedFields[fieldName];
                this.classList.remove('edited');
            }
            
            updateCounter();
        });
        
        field.addEventListener('blur', function() {
            // Salvar valor ao perder foco
            const currentValue = this.value.trim();
            if (currentValue !== originalValue) {
                console.log(`Campo ${fieldName} editado: "${originalValue}" → "${currentValue}"`);
            }
        });
    });
    
    // Atualizar contador inicial (deve ser 0 aceitos)
    updateCounter();
    
    // Botões de ação (aceitar/rejeitar)
    const actionButtons = document.querySelectorAll('.btn-action');
    
    actionButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            
            const card = this.closest('.analysis-card');
            const fieldName = card.dataset.field;
            const action = this.classList.contains('btn-action-accept') ? 'accept' : 'reject';
            
            handleDecision(card, fieldName, action);
        });
    });
    
    /**
     * Processa decisão de aceitar/rejeitar
     */
    function handleDecision(card, fieldName, action) {
        const acceptBtn = card.querySelector('.btn-action-accept');
        const rejectBtn = card.querySelector('.btn-action-reject');
        const feedbackAccepted = card.querySelector('.analysis-feedback-accepted');
        const feedbackRejected = card.querySelector('.analysis-feedback-rejected');
        
        // Verificar se elementos existem
        if (!acceptBtn || !rejectBtn || !feedbackAccepted || !feedbackRejected) {
            console.warn(`Elementos de feedback não encontrados para campo: ${fieldName}`);
            return;
        }
        
        // Remover estados anteriores
        acceptBtn.classList.remove('active');
        rejectBtn.classList.remove('active');
        feedbackAccepted.classList.remove('show');
        feedbackRejected.classList.remove('show');
        
        if (action === 'accept') {
            // Se já estava aceito, desmarcar
            if (decisions[fieldName] === 'accept') {
                delete decisions[fieldName];
            } else {
                // Aceitar sugestão
                decisions[fieldName] = 'accept';
                acceptBtn.classList.add('active');
                feedbackAccepted.classList.add('show');
            }
        } else {
            // Se já estava rejeitado, desmarcar
            if (decisions[fieldName] === 'reject') {
                delete decisions[fieldName];
            } else {
                // Rejeitar sugestão
                decisions[fieldName] = 'reject';
                rejectBtn.classList.add('active');
                feedbackRejected.classList.add('show');
            }
        }
        
        // Atualizar contador de sugestões selecionadas
        updateCounter();
    }
    
    /**
     * Atualiza o contador de sugestões aceitas + campos editados
     */
    function updateCounter() {
        const acceptedCount = Object.values(decisions).filter(d => d === 'accept').length;
        const editedCount = Object.keys(editedFields).length;
        const totalChanges = acceptedCount + editedCount;
        
        const counter = document.querySelector('.counter');
        const submitBtn = document.getElementById('btn-submit-suggestions');
        
        if (counter) {
            counter.textContent = totalChanges;
        }
        
        if (submitBtn) {
            submitBtn.disabled = totalChanges === 0;
            
            // Atualizar texto do botão
            if (editedCount > 0 && acceptedCount > 0) {
                submitBtn.innerHTML = `Salvar Alterações <span class="counter">${totalChanges}</span>`;
            } else if (editedCount > 0) {
                submitBtn.innerHTML = `Salvar Edições <span class="counter">${totalChanges}</span>`;
            } else {
                submitBtn.innerHTML = `Aplicar Sugestões Selecionadas <span class="counter">${totalChanges}</span>`;
            }
        }
    }
    
    // Expor updateCounter globalmente para perfil-tags.js
    window.updateCounter = updateCounter;
    
    /**
     * Enviar sugestões selecionadas
     */
    const submitBtn = document.getElementById('btn-submit-suggestions');
    if (submitBtn) {
        submitBtn.addEventListener('click', async function(e) {
            e.preventDefault();
            
            const acceptedFields = Object.entries(decisions)
                .filter(([_, action]) => action === 'accept')
                .map(([field, _]) => field);
            
            const editedCount = Object.keys(editedFields).length;
            const totalChanges = acceptedFields.length + editedCount;
            
            if (totalChanges === 0) {
                // Usar modal de confirmação ao invés de alert
                if (window.confirmModal) {
                    await window.confirmModal.show(
                        'Você precisa aceitar pelo menos uma sugestão ou editar um campo antes de aplicar as alterações.',
                        'Nenhuma alteração'
                    );
                }
                return;
            }
            
            // Preparar mensagem de confirmação
            let message = '';
            if (editedCount > 0 && acceptedFields.length > 0) {
                message = `Você editou ${editedCount} campo(s) e aceitou ${acceptedFields.length} sugestão(ões).\n\n`;
            } else if (editedCount > 0) {
                message = `Você editou ${editedCount} campo(s).\n\n`;
            } else {
                message = `Você aceitou ${acceptedFields.length} sugestão(ões).\n\n`;
            }
            message += 'Isso irá atualizar os campos da sua Base de Conhecimento.\n\nDeseja continuar?';
            
            // Usar modal de confirmação
            if (!window.confirmModal) {
                console.error('Modal de confirmação não encontrado');
                return;
            }
            
            const confirmed = await window.confirmModal.show(
                message,
                'Confirmar Alterações'
            );
            
            if (!confirmed) return;
            
            // Desabilitar botão e mostrar loading
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner"></span> Processando...';
            
            try {
                const response = await fetch('/knowledge/perfil/apply-suggestions/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    body: JSON.stringify({
                        accepted_suggestions: acceptedFields,
                        edited_fields: editedFields
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    console.log('✅ Resposta do servidor:', data);
                    
                    // Mostrar mensagem de sucesso
                    if (window.toaster) {
                        window.toaster.success(data.message || 'Alterações aplicadas com sucesso!');
                    }
                    
                    // Redirecionar para página de visualização
                    setTimeout(() => {
                        window.location.href = data.redirect_url || '/knowledge/perfil-visualizacao/';
                    }, 1500);
                } else {
                    // Mostrar erro
                    if (window.toaster) {
                        window.toaster.error(data.error || 'Erro ao processar sugestões');
                    }
                    submitBtn.disabled = false;
                    updateCounter();
                }
            } catch (error) {
                console.error('Erro ao enviar sugestões:', error);
                
                // Mostrar erro
                if (window.toaster) {
                    window.toaster.error('Erro ao enviar sugestões. Tente novamente.');
                }
                submitBtn.disabled = false;
                updateCounter();
            }
        });
    }
    
    /**
     * Obter cookie CSRF
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
    
});
