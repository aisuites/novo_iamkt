/**
 * COLORS.JS - Gerenciamento de Paleta de Cores
 * Interface visual com color picker seguindo referência
 */

let colorIndex = 0;

// Adicionar uma nova cor
function addColor(hexValue = '#7A3D8A', colorName = '') {
    const colorList = document.getElementById('color-list');
    if (!colorList) return;
    
    const colorItem = document.createElement('div');
    colorItem.className = 'color-item';
    colorItem.dataset.index = colorIndex;
    
    colorItem.innerHTML = `
        <div class="color-picker-wrapper">
            <input type="color" 
                   class="color-picker-input" 
                   value="${hexValue}"
                   onchange="updateHexInput(${colorIndex}, this.value)">
            <input type="text" 
                   class="color-hex-input" 
                   name="cores[${colorIndex}][hex]"
                   value="${hexValue}"
                   placeholder="#7A3D8A"
                   maxlength="7"
                   oninput="updateColorPicker(${colorIndex}, this.value)">
            <input type="text" 
                   class="color-name-input" 
                   name="cores[${colorIndex}][nome]"
                   value="${colorName}"
                   placeholder="Nome da cor (ex: Roxo FEMME, Verde água)">
        </div>
        <button 
        type="button" 
        class="btn-remove-item" 
        onclick="removeColor(${colorIndex})"
        title="Remover cor"
      >
        Remover
      </button>
    `;
    
    colorList.appendChild(colorItem);
    colorIndex++;
    syncColorsToForm();
}

// Atualizar input HEX quando color picker mudar
function updateHexInput(index, hexValue) {
    const colorItem = document.querySelector(`.color-item[data-index="${index}"]`);
    if (colorItem) {
        const hexInput = colorItem.querySelector('.color-hex-input');
        hexInput.value = hexValue.toUpperCase();
    }
}

// Atualizar color picker quando input HEX mudar
function updateColorPicker(index, hexValue) {
    const colorItem = document.querySelector(`.color-item[data-index="${index}"]`);
    if (colorItem && /^#[0-9A-F]{6}$/i.test(hexValue)) {
        const colorPicker = colorItem.querySelector('.color-picker-input');
        colorPicker.value = hexValue;
    }
    syncColorsToForm();
}

// Remover uma cor (com modal de confirmação)
async function removeColor(button) {
    const colorItem = button.closest('.color-item');
    const nameInput = colorItem.querySelector('.color-name-input');
    const nome = nameInput ? nameInput.value.trim() : '';
    const mensagem = `Tem certeza que deseja remover ${nome ? `a cor "${nome}"` : 'esta cor'}?`;
    
    // Usar modal de confirmação
    if (window.confirmModal && typeof window.confirmModal.show === 'function') {
        const confirmed = await window.confirmModal.show(mensagem, 'Remover cor');
        if (!confirmed) return;
    } else {
        // Fallback: confirmação nativa
        if (!confirm(mensagem)) return;
    }
    
    colorItem.classList.add('removing');
    setTimeout(() => {
        colorItem.remove();
        syncColorsToForm();
    }, 200);
}

function syncColorsToForm() {
    // Os campos já estão no HTML com os nomes corretos (cores[index][hex] e cores[index][nome])
    // Apenas precisamos atualizar os índices se necessário
    const colorsList = document.getElementById('color-list');
    if (!colorsList) return;
    
    const colorItems = colorsList.querySelectorAll('.color-item');
    
    // Atualizar índices dos campos
    colorItems.forEach((item, newIndex) => {
        const hexInput = item.querySelector('.color-hex-input');
        const nameInput = item.querySelector('.color-name-input');
        
        if (hexInput) {
            hexInput.name = `cores[${newIndex}][hex]`;
        }
        if (nameInput) {
            nameInput.name = `cores[${newIndex}][nome]`;
        }
        
        item.dataset.index = newIndex;
    });
}

// Inicializar cores existentes
document.addEventListener('DOMContentLoaded', function() {
    // Carregar cores do backend (via data attributes ou AJAX)
    const colorsData = window.KNOWLEDGE_COLORS || [];
    
    if (colorsData.length > 0) {
        colorsData.forEach(color => {
            addColor(color.hex_code, color.name);
        });
    }
    // Empresas novas começam sem cores pré-preenchidas
});

// Expor funções globalmente
window.addColor = addColor;
window.updateHexInput = updateHexInput;
window.updateColorPicker = updateColorPicker;
window.removeColor = removeColor;
