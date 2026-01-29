/**
 * PERFIL.JS - Interações da página "Perfil da Empresa"
 * Gerencia aceitar/rejeitar sugestões e envio de dados
 */

document.addEventListener('DOMContentLoaded', function() {
    // Estado das decisões do usuário
    const decisions = {};
    
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
     * Atualiza contador de sugestões aceitas
     */
    function updateCounter() {
        const acceptedCount = Object.values(decisions).filter(d => d === 'accept').length;
        const submitBtn = document.getElementById('btn-submit-suggestions');
        
        if (submitBtn) {
            const counterSpan = submitBtn.querySelector('.counter');
            if (counterSpan) {
                counterSpan.textContent = acceptedCount;
            }
            
            // Habilitar/desabilitar botão
            submitBtn.disabled = acceptedCount === 0;
        }
    }
    
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
            
            if (acceptedFields.length === 0) {
                alert('Selecione pelo menos uma sugestão para aplicar.');
                return;
            }
            
            // Confirmar ação
            const confirmed = confirm(
                `Você está prestes a aplicar ${acceptedFields.length} sugestão(ões).\n\n` +
                'Isso irá atualizar os campos da sua Base de Conhecimento e solicitar ' +
                'a compilação final ao agente IAMKT.\n\n' +
                'Deseja continuar?'
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
                        accepted_suggestions: decisions
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    // Redirecionar para estado de loading (compilação)
                    window.location.href = '/knowledge/perfil/?status=compiling';
                } else {
                    alert('Erro ao processar sugestões: ' + (data.error || 'Erro desconhecido'));
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = 'Aplicar Sugestões Selecionadas <span class="counter">0</span>';
                }
            } catch (error) {
                console.error('Erro ao enviar sugestões:', error);
                alert('Erro ao enviar sugestões. Tente novamente.');
                submitBtn.disabled = false;
                submitBtn.innerHTML = 'Aplicar Sugestões Selecionadas <span class="counter">0</span>';
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
    
    /**
     * Polling para verificar status de compilação
     */
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('status') === 'compiling') {
        checkCompilationStatus();
    }
    
    async function checkCompilationStatus() {
        try {
            const response = await fetch('/knowledge/perfil/status/');
            const data = await response.json();
            
            if (data.status === 'compiled') {
                // Compilação concluída, redirecionar para modo visualização
                window.location.href = '/knowledge/perfil/?status=compiled';
            } else if (data.status === 'error') {
                alert('Erro ao gerar compilação. Por favor, tente novamente.');
                window.location.href = '/knowledge/perfil/';
            } else {
                // Ainda processando, verificar novamente em 10 segundos
                setTimeout(checkCompilationStatus, 10000);
            }
        } catch (error) {
            console.error('Erro ao verificar status:', error);
            setTimeout(checkCompilationStatus, 10000);
        }
    }
});
