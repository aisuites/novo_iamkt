# 📐 ESPECIFICAÇÃO TÉCNICA - KNOWLEDGE BASE FRONTEND

**Data:** 13 de Janeiro de 2026  
**Baseado em:** `base_femme_form.html` e `accordion.js` (arquivos de referência)

---

## 🎯 OBJETIVO

Implementar página de edição da Base de Conhecimento FEMME com:
- Layout accordion colapsável
- Formulário tradicional (campos normais, não edição inline)
- 7 blocos temáticos
- Primeiro bloco aberto por padrão
- Pills de navegação com scroll suave

---

## 📋 ANÁLISE DOS ARQUIVOS DE REFERÊNCIA

### **base_femme_form.html**

**Estrutura HTML:**
```html
<section class="form-wrapper">
  <div class="form-header">
    <div class="section-title">Cadastro / edição da Base FEMME</div>
    <div class="section-subtitle">Preencha os blocos abaixo...</div>
  </div>
  
  <div class="form-steps">
    <a href="#bloco-institucional" class="form-step-pill">1. Institucional</a>
    <a href="#bloco-publicos" class="form-step-pill">2. Públicos</a>
    <!-- ... -->
  </div>
  
  <form method="post" class="form-grid">
    <section class="form-block" id="bloco-institucional">
      <div class="form-block-header">
        <div>
          <div class="form-block-kicker">Bloco 1</div>
          <div class="form-block-title">Identidade institucional</div>
        </div>
        <!-- ícone de toggle adicionado via JS -->
      </div>
      
      <div class="form-block-body">
        <div class="form-block-description">
          <p>Descrição do bloco...</p>
        </div>
        
        <div class="form-fields">
          <div class="field">
            <label>Nome da empresa</label>
            <input type="text" name="nome_empresa" />
          </div>
          <!-- mais campos... -->
        </div>
      </div>
    </section>
    <!-- mais blocos... -->
  </form>
</section>
```

**CSS Accordion (linhas 539-590):**
```css
.accordion-block .form-block-header {
  cursor: pointer;
  user-select: none;
  transition: background 0.2s ease;
  padding: 8px;
  margin: -8px;
  border-radius: var(--radius-sm);
}

.accordion-toggle {
  display: inline-flex;
  width: 24px;
  height: 24px;
  border-radius: 999px;
  background: rgba(122, 61, 138, 0.08);
  transition: transform 0.3s ease;
}

.accordion-open .accordion-toggle {
  transform: rotate(180deg);
}

.accordion-closed .form-block-body {
  display: none;
}

.accordion-open .form-block-body {
  display: block;
  animation: slideDown 0.3s ease;
}
```

### **accordion.js**

**Funcionalidades:**
1. Adiciona classe `accordion-block` a todos `.form-block`
2. Primeiro bloco (`#bloco-institucional`) recebe classe `accordion-open`
3. Demais blocos recebem classe `accordion-closed`
4. Cria elemento `<span class="accordion-toggle">▼</span>` e adiciona ao header
5. Ao clicar no header, toggle entre `accordion-open` e `accordion-closed`
6. Scroll suave ao abrir bloco
7. Pills de navegação abrem o bloco correspondente e fazem scroll

---

## 🎨 COMPONENTES NECESSÁRIOS

### 1. **Hero Section**
- Título com gradient
- Status da base (completa/parcialmente preenchida)
- Última atualização
- Tags de categorias

### 2. **Form Header**
- Título "Cadastro / edição da Base FEMME"
- Subtítulo explicativo
- Pills de navegação (7 blocos)

### 3. **Form Grid (Accordion)**
- 7 blocos `.form-block`
- Cada bloco tem:
  - Header clicável
  - Ícone de toggle (▼)
  - Body colapsável
  - Campos de formulário normais

### 4. **Form Footer**
- Texto informativo sobre campos obrigatórios
- Botões: "Cancelar" e "Salvar Base FEMME"

---

## 🔧 IMPLEMENTAÇÃO DETALHADA

### **PASSO 1: Template HTML**

**Estrutura:**
```django
{% extends 'base/base.html' %}
{% load static %}

{% block extra_css %}
<link rel="stylesheet" href="{% static 'css/knowledge.css' %}?v=3.0">
{% endblock %}

{% block content %}
<!-- HERO -->
<section class="hero-base">
  <!-- conteúdo do hero -->
</section>

<!-- FORM -->
<section class="form-wrapper">
  <div class="form-header">
    <div class="section-title">Cadastro / edição da Base FEMME</div>
    <div class="section-subtitle">
      Clique nos blocos abaixo para expandir. Edite cada campo individualmente clicando no ícone de lápis.
    </div>
  </div>
  
  <div class="form-steps">
    <a href="#bloco1" class="form-step-pill">1. Institucional</a>
    <a href="#bloco2" class="form-step-pill">2. Públicos</a>
    <a href="#bloco3" class="form-step-pill">3. Posicionamento</a>
    <a href="#bloco4" class="form-step-pill">4. Tom de voz</a>
    <a href="#bloco5" class="form-step-pill">5. Visual</a>
    <a href="#bloco6" class="form-step-pill">6. Redes</a>
    <a href="#bloco7" class="form-step-pill">7. Dados</a>
  </div>
  
  <form method="post" class="form-grid">
    {% csrf_token %}
    
    <!-- BLOCO 1 -->
    <section class="form-block" id="bloco1">
      <div class="form-block-header">
        <div>
          <div class="form-block-kicker">Bloco 1</div>
          <div class="form-block-title">Identidade institucional</div>
        </div>
        <span class="completude-badge">100%</span>
      </div>
      
      <div class="form-block-body">
        <div class="form-block-description">
          <p>Descreva o FEMME de forma clara e estratégica...</p>
        </div>
        
        <div class="form-fields">
          <div class="field">
            <div class="field-label-row">
              <label for="nome_empresa">Nome da empresa</label>
              <span class="field-required">*</span>
            </div>
            <input type="text" 
                   id="nome_empresa" 
                   name="nome_empresa" 
                   value="{{ kb.nome_empresa }}"
                   placeholder="Ex.: FEMME - Diagnóstico e Medicina Preventiva">
          </div>
          
          <div class="field">
            <div class="field-label-row">
              <label for="missao">Missão</label>
              <span class="field-required">*</span>
            </div>
            <textarea id="missao" 
                      name="missao" 
                      placeholder="Razão de existir da empresa">{{ kb.missao }}</textarea>
          </div>
          
          <!-- mais campos... -->
        </div>
      </div>
    </section>
    
    <!-- BLOCOS 2-7... -->
    
  </form>
  
  <div class="form-footer">
    <div class="form-footer-left">
      Campos marcados com <span class="field-required">*</span> são obrigatórios.
    </div>
    <div class="form-footer-actions">
      <a href="{% url 'core:dashboard' %}" class="btn btn-ghost">Cancelar</a>
      <button type="submit" class="btn btn-primary">✅ Salvar Base FEMME</button>
    </div>
  </div>
</section>
{% endblock %}

{% block extra_js %}
<script src="{% static 'js/knowledge.js' %}?v=3.0"></script>
{% endblock %}
```

---

### **PASSO 2: CSS (knowledge.css)**

**Copiar do base_femme_form.html:**
```css
/* Accordion styles */
.accordion-block .form-block-header {
  cursor: pointer;
  user-select: none;
  transition: background 0.2s ease;
  padding: 8px;
  margin: -8px;
  border-radius: var(--radius-sm);
}

.accordion-block .form-block-header:hover {
  background: rgba(122, 61, 138, 0.04);
}

.accordion-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 999px;
  background: rgba(122, 61, 138, 0.08);
  color: var(--femme-purple);
  font-size: 10px;
  transition: transform 0.3s ease, background 0.2s ease;
}

.accordion-open .accordion-toggle {
  transform: rotate(180deg);
  background: rgba(122, 61, 138, 0.12);
}

.accordion-closed .form-block-body {
  display: none;
}

.accordion-open .form-block-body {
  display: block;
  animation: slideDown 0.3s ease;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Completude badge */
.completude-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(122, 61, 138, 0.08);
  color: var(--femme-purple);
}
```

---

### **PASSO 3: JavaScript (knowledge.js)**

**Copiar do accordion.js:**
```javascript
document.addEventListener('DOMContentLoaded', function() {
    const formBlocks = document.querySelectorAll('.form-block');
    
    formBlocks.forEach(function(block) {
        const header = block.querySelector('.form-block-header');
        const body = block.querySelector('.form-block-body');
        
        if (!header || !body) return;
        
        // Adicionar classe de controle
        block.classList.add('accordion-block');
        
        // Primeiro bloco aberto por padrão
        if (block.id === 'bloco1') {
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
    
    console.log('Knowledge Base initialized');
});
```

---

## ✅ CHECKLIST DE IMPLEMENTAÇÃO

### **Fase 1: Preparação**
- [x] Analisar `base_femme_form.html`
- [x] Analisar `accordion.js`
- [x] Criar especificação técnica
- [ ] Backup dos arquivos atuais

### **Fase 2: Implementação**
- [ ] Criar novo `view.html` do zero (baseado na referência)
- [ ] Criar novo `knowledge.css` do zero (copiar accordion styles)
- [ ] Criar novo `knowledge.js` do zero (copiar accordion.js)
- [ ] Implementar os 7 blocos completos

### **Fase 3: Validação**
- [ ] Executar `collectstatic --clear`
- [ ] Reiniciar servidor
- [ ] Testar accordion (toggle funciona)
- [ ] Testar pills de navegação (scroll funciona)
- [ ] Confirmar layout idêntico à imagem de referência

---

## 🚨 DIFERENÇAS IMPORTANTES

### **O QUE NÃO FAZER:**
❌ Edição inline com ícones ✏️ 💾 ❌  
❌ Campos disabled que precisam ser habilitados  
❌ Salvamento AJAX individual por campo  
❌ Botões de ação ao lado de cada campo  

### **O QUE FAZER:**
✅ Formulário tradicional com campos normais  
✅ Accordion colapsável (toggle via header)  
✅ Ícone ▼ que rota 180° ao abrir  
✅ Primeiro bloco aberto por padrão  
✅ Pills de navegação com scroll suave  
✅ Botão "Salvar Base FEMME" no final  

---

## 📊 ESTRUTURA DOS 7 BLOCOS

### **Bloco 1: Identidade Institucional**
- nome_empresa (text, obrigatório)
- missao (textarea, obrigatório)
- visao (textarea)
- valores (textarea, obrigatório)
- historia (textarea)

### **Bloco 2: Públicos & Segmentos**
- publico_externo (textarea, obrigatório)
- publico_interno (textarea)
- segmentos_internos (textarea → array)

### **Bloco 3: Posicionamento & Diferenciais**
- posicionamento (textarea, obrigatório)
- diferenciais (textarea, obrigatório)
- proposta_valor (textarea)

### **Bloco 4: Tom de Voz**
- tom_voz_externo (textarea, obrigatório)
- tom_voz_interno (textarea)
- palavras_recomendadas (textarea → array, obrigatório)
- palavras_evitar (textarea → array, obrigatório)

### **Bloco 5: Identidade Visual**
- ColorPalette (lista gerenciável)
- CustomFont (upload)
- Logo (upload)
- ReferenceImage (upload)

### **Bloco 6: Sites & Redes**
- site_institucional (url, obrigatório)
- SocialNetwork (lista gerenciável)
- SocialNetworkTemplate (lista gerenciável)

### **Bloco 7: Dados & Insights**
- fontes_confiaveis (textarea → array, obrigatório)
- canais_trends (textarea JSON)
- palavras_chave_trends (textarea → array)

---

## 🎯 RESULTADO ESPERADO

Ao final da implementação, a página deve:
1. Ter layout idêntico à imagem de referência
2. Accordion funcionar perfeitamente (toggle ao clicar no header)
3. Ícone ▼ rotar 180° ao abrir bloco
4. Primeiro bloco aberto por padrão
5. Pills de navegação abrirem e scrollarem até o bloco
6. Formulário tradicional (sem edição inline)
7. Botão "Salvar Base FEMME" submeter o form via POST

---

**Próximo passo:** Implementar do zero seguindo esta especificação.
