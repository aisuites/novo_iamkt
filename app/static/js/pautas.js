// JavaScript para a página de Pautas

document.addEventListener('DOMContentLoaded', function() {
    // Botão Gerar Pauta
    const formGerarPauta = document.getElementById('form-gerar-pauta');
    const btnGerar = document.getElementById('btn-gerar');
    let isSubmitting = false; // Bloqueio para duplo clique
    
    if (formGerarPauta) {
        formGerarPauta.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Bloquear se já está enviando
            if (isSubmitting) {
                return;
            }
            isSubmitting = true;
            
            const formData = new FormData(formGerarPauta);
            const tema = formData.get('tema');
            const rede_social = formData.get('rede_social');
            
            // Validação básica - apenas rede social é obrigatória
            if (!rede_social) {
                toaster.warning('Por favor, selecione uma rede social.');
                isSubmitting = false; // Liberar bloqueio
                return;
            }
            
            // Desabilitar botão e mostrar loading
            btnGerar.disabled = true;
            btnGerar.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Gerando...';
            
            // Preparar dados para envio JSON
            const data = {
                rede_social: rede_social,
                tema: tema
            };
            
            // Enviar requisição AJAX
            fetch('/pautas/gerar/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify(data)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    toaster.success(data.message);
                    // Fechar modal
                    closeModal('modalGerarPauta');
                    
                    // Limpar formulário
                    formGerarPauta.reset();
                    
                    // Não recarregar automaticamente para evitar duplicidade
                    // Usuário pode recarregar manualmente se quiser ver novas pautas
                } else {
                    toaster.error(data.error);
                }
            })
            .catch(error => {
                toaster.error('Ocorreu um erro ao gerar as pautas. Tente novamente.');
            })
            .finally(() => {
                // Restaurar botão
                btnGerar.disabled = false;
                btnGerar.innerHTML = '<i class="fas fa-magic me-1"></i> Gerar Pautas';
                isSubmitting = false; // Liberar bloqueio
            });
        });
    }
    
    // Botões Editar
    document.querySelectorAll('.btn-edit').forEach(button => {
        button.addEventListener('click', function() {
            const pautaId = this.dataset.pautaId;
            toggleEditMode(pautaId, true);
        });
    });
    
    // Botões Cancelar Edição
    document.querySelectorAll('.btn-cancel-edit').forEach(button => {
        button.addEventListener('click', function() {
            const pautaId = this.dataset.pautaId;
            toggleEditMode(pautaId, false);
        });
    });
    
    // Botões Salvar Edição
    document.querySelectorAll('.btn-save-edit').forEach(button => {
        button.addEventListener('click', function() {
            const pautaId = this.dataset.pautaId;
            savePautaEdit(pautaId);
        });
    });
    
    // Botões Excluir
    let pautaParaExcluir = null;
    
    document.querySelectorAll('.btn-delete').forEach(button => {
        button.addEventListener('click', function() {
            pautaParaExcluir = {
                id: this.dataset.pautaId,
                title: this.dataset.pautaTitle
            };
            
            // Preencher modal de confirmação
            document.getElementById('pauta-excluir-titulo').textContent = pautaParaExcluir.title;
            
            // Abrir modal
            const modal = new bootstrap.Modal(document.getElementById('modalExcluirPauta'));
            modal.show();
        });
    });
    
    // Botão Confirmar Exclusão no Modal
    const btnConfirmarExcluir = document.getElementById('btn-confirmar-excluir');
    if (btnConfirmarExcluir) {
        btnConfirmarExcluir.addEventListener('click', function() {
            if (!pautaParaExcluir) return;
            
            deletePauta(pautaParaExcluir.id, pautaParaExcluir.title);
            
            // Fechar modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('modalExcluirPauta'));
            if (modal) {
                modal.hide();
            }
        });
    }
    
    // Função para alternar entre modo visualização e edição
    function toggleEditMode(pautaId, isEdit) {
        const contentDiv = document.getElementById(`pauta-content-${pautaId}`);
        const editDiv = document.getElementById(`pauta-edit-${pautaId}`);
        
        if (isEdit) {
            contentDiv.style.display = 'none';
            editDiv.style.display = 'block';
        } else {
            contentDiv.style.display = 'block';
            editDiv.style.display = 'none';
        }
    }
    
    // Função para salvar edição da pauta
    function savePautaEdit(pautaId) {
        const title = document.getElementById(`edit-title-${pautaId}`).value.trim();
        const content = document.getElementById(`edit-content-${pautaId}`).value.trim();
        
        if (!title) {
            toaster.warning('O título não pode estar vazio.');
            return;
        }
        
        if (!content) {
            toaster.warning('O conteúdo não pode estar vazio.');
            return;
        }
        
        // Enviar requisição de atualização
        fetch(`/pautas/editar/${pautaId}/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                title: title,
                content: content
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                toaster.success(data.message);
                
                // Atualizar conteúdo na visualização
                const contentDiv = document.getElementById(`pauta-content-${pautaId}`);
                contentDiv.querySelector('h5').textContent = title;
                contentDiv.querySelector('p').textContent = content;
                
                // Voltar para modo visualização
                toggleEditMode(pautaId, false);
            } else {
                toaster.error(data.error);
            }
        })
        .catch(error => {
            toaster.error('Ocorreu um erro ao salvar. Tente novamente.');
        });
    }
    
    // Função para excluir pauta
    function deletePauta(pautaId, pautaTitle) {
        fetch(`/pautas/excluir/${pautaId}/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                toaster.success(data.message);
                
                // Recarregar página após 1 segundo
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
            } else {
                toaster.error(data.error);
            }
        })
        .catch(error => {
            toaster.error('Ocorreu um erro ao excluir. Tente novamente.');
        });
    }
    
    // Botões Gerar Post
    document.querySelectorAll('.btn').forEach(button => {
        if (button.textContent.trim() === 'Gerar Post') {
            button.addEventListener('click', function() {
                const pautaId = this.dataset.pautaId;
                
                // TODO: Implementar fluxo de geração de posts
                toaster.info('Fluxo de geração de posts ainda não implementado.');
            });
        }
    });
});

// Funções auxiliares
function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = 'auto';
    }
}

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
