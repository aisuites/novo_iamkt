# 📐 PADRÕES DE DESENVOLVIMENTO FRONTEND - IAMKT

**Versão:** 1.0  
**Data:** 13 de Janeiro de 2026  
**Objetivo:** Estabelecer padrões profissionais de desenvolvimento frontend

---

## 🚫 PROIBIÇÕES ABSOLUTAS

### 1. CSS INLINE - NUNCA USAR

❌ **ERRADO:**
```html
<div style="display:none;">Conteúdo</div>
<span style="font-size:12px; color:#666;">Texto</span>
<button style="background:red;">Botão</button>
```

✅ **CORRETO:**
```html
<!-- HTML -->
<div class="hidden">Conteúdo</div>
<span class="text-small text-muted">Texto</span>
<button class="btn btn-danger">Botão</button>
```

```css
/* CSS */
.hidden { display: none; }
.text-small { font-size: 12px; }
.text-muted { color: var(--femme-gray); }
```

**Exceções:** NENHUMA. Sempre use classes CSS.

---

### 2. JAVASCRIPT INLINE - NUNCA USAR

❌ **ERRADO:**
```html
<button onclick="alert('Clicou')">Clique</button>
<div onload="inicializar()">Conteúdo</div>
```

✅ **CORRETO:**
```html
<!-- HTML -->
<button class="btn-alert">Clique</button>
<div class="content-area">Conteúdo</div>
```

```javascript
// JavaScript
document.querySelector('.btn-alert').addEventListener('click', () => {
  alert('Clicou');
});
```

---

## ✅ BOAS PRÁTICAS OBRIGATÓRIAS

### 1. Hierarquia de CSS

**Ordem de prioridade:**
1. **CSS Global** (`base.css`, `components.css`) - SEMPRE USAR PRIMEIRO
2. **CSS de Módulo** (`knowledge.css`, `dashboard.css`) - Apenas quando necessário
3. **CSS Inline** - ❌ NUNCA

**Exemplo:**
```css
/* base.css - Estilos globais */
.btn { padding: 8px 16px; border-radius: 4px; }
.text-muted { color: var(--femme-gray); }

/* knowledge.css - Estilos específicos do módulo */
.accordion-body { display: none; }
.accordion-block.is-open .accordion-body { display: block; }
```

---

### 2. Classes Semânticas

**Use nomes descritivos e reutilizáveis:**

❌ **ERRADO:**
```css
.div1 { color: red; }
.texto { font-size: 12px; }
.btn1 { background: blue; }
```

✅ **CORRETO:**
```css
.hero-status-label { font-size: 12px; font-weight: 600; }
.accordion-body { display: none; }
.btn-field-action { width: 28px; height: 28px; }
```

---

### 3. Estados com Classes CSS

**Controle de visibilidade e estados via classes:**

❌ **ERRADO (JavaScript manipulando inline):**
```javascript
element.style.display = 'none';
element.style.color = 'red';
```

✅ **CORRETO (JavaScript manipulando classes):**
```javascript
element.classList.add('hidden');
element.classList.add('error-state');
```

```css
.hidden { display: none; }
.error-state { color: var(--femme-red); border-color: var(--femme-red); }
```

---

### 4. Variáveis CSS

**Use variáveis CSS para valores reutilizáveis:**

✅ **CORRETO:**
```css
:root {
  --femme-purple: #7a3d8a;
  --femme-gray: #666;
  --femme-gray-light: #f5f5f5;
  --radius-sm: 4px;
  --radius-md: 8px;
}

.card {
  background: var(--femme-gray-light);
  border-radius: var(--radius-md);
  color: var(--femme-gray);
}
```

---

## 🎨 ESPECIFICIDADE CSS

### Hierarquia de Especificidade

**Ordem de prioridade (menor para maior):**
1. Seletor de elemento: `div` (0,0,1)
2. Seletor de classe: `.classe` (0,1,0)
3. Seletor de ID: `#id` (1,0,0)
4. Inline style: `style=""` (1,0,0,0)
5. `!important` (quebra tudo)

### Regra de Ouro: NUNCA use !important

❌ **ERRADO:**
```css
.hidden {
  display: none !important;
}
```

✅ **CORRETO - Aumentar especificidade naturalmente:**
```css
/* Opção 1: Combinar seletores */
textarea.hidden,
input.hidden {
  display: none;
}

/* Opção 2: Seletor composto */
.modal.modal-hidden {
  display: none;
}

/* Opção 3: Seletor descendente */
.form .hidden-field {
  display: none;
}
```

### Quando !important é Aceitável

**Apenas em casos MUITO específicos:**
1. Sobrescrever CSS de bibliotecas externas (último recurso)
2. Utility classes de framework (ex: Tailwind)
3. Classes de acessibilidade críticas

**Mesmo nesses casos, prefira aumentar especificidade.**

### Como Resolver Conflitos de Especificidade

```css
/* ❌ RUIM - Guerra de !important */
.button { background: blue !important; }
.button-primary { background: red !important; }

/* ✅ BOM - Especificidade natural */
.button { background: blue; }
.button.button-primary { background: red; }
```

---

## 🔄 WORKFLOW DE DESENVOLVIMENTO

### 1. Antes de Escrever Código

**Checklist obrigatório:**
- [ ] Verificar se há classes CSS globais reutilizáveis
- [ ] Verificar se há componentes similares já implementados
- [ ] Planejar estrutura HTML semântica
- [ ] Definir classes CSS necessárias
- [ ] Documentar funcionalidades JavaScript

### 2. Durante o Desenvolvimento

**Checklist obrigatório:**
- [ ] Usar apenas classes CSS (zero inline styles)
- [ ] Usar event listeners (zero inline JavaScript)
- [ ] Testar em diferentes resoluções
- [ ] Validar HTML/CSS com linter
- [ ] Comentar código complexo

### 3. Após o Desenvolvimento

**Checklist obrigatório:**
- [ ] Executar `collectstatic --clear`
- [ ] Limpar cache do Django
- [ ] Reiniciar servidor
- [ ] Testar em navegador (hard refresh)
- [ ] Validar no console do navegador (F12)

---

## 🛠️ COMANDOS ESSENCIAIS

### Coletar Arquivos Estáticos
```bash
docker compose exec iamkt_web python manage.py collectstatic --noinput --clear
```

### Limpar Cache do Django
```bash
docker compose exec iamkt_web python manage.py shell -c "from django.core.cache import cache; cache.clear(); print('Cache limpo')"
```

### Reiniciar Servidor
```bash
docker compose restart iamkt_web
```

### Hard Refresh no Navegador
- **Windows/Linux:** `Ctrl + Shift + R`
- **Mac:** `Cmd + Shift + R`

---

## 📁 ESTRUTURA DE ARQUIVOS

### CSS
```
/app/static/css/
├── base.css           # Estilos globais (reset, variáveis, tipografia)
├── components.css     # Componentes reutilizáveis (botões, cards, forms)
├── knowledge.css      # Estilos específicos do módulo knowledge
├── dashboard.css      # Estilos específicos do módulo dashboard
└── ...
```

### JavaScript
```
/app/static/js/
├── main.js           # JavaScript global
├── knowledge.js      # JavaScript específico do módulo knowledge
├── dashboard.js      # JavaScript específico do módulo dashboard
└── ...
```

### Templates
```
/app/templates/
├── base/
│   └── base.html     # Template base
├── components/
│   ├── header.html   # Componentes reutilizáveis
│   └── sidebar.html
├── knowledge/
│   └── view.html     # Templates do módulo
└── ...
```

---

## 🎯 PADRÕES DE ACCORDION

### HTML
```html
<section class="accordion-block" id="bloco1">
  <div class="accordion-header">
    <div>
      <div class="form-block-kicker">Bloco 1</div>
      <div class="form-block-title">Título do Bloco</div>
    </div>
    <div class="accordion-toggle">
      <span class="completude-badge">100%</span>
      <button type="button" class="btn-icon-toggle">
        <svg>...</svg>
      </button>
    </div>
  </div>
  
  <div class="accordion-body">
    <!-- Conteúdo do bloco -->
  </div>
</section>
```

### CSS
```css
/* Accordion fechado por padrão */
.accordion-body {
  display: none;
  overflow: hidden;
  transition: all 0.3s ease;
}

/* Accordion aberto */
.accordion-block.is-open .accordion-body {
  display: block;
}

/* Ícone rotacionado quando aberto */
.accordion-block.is-open .btn-icon-toggle svg {
  transform: rotate(180deg);
}
```

### JavaScript
```javascript
function toggleAccordion(block, body) {
  const isOpen = block.classList.contains('is-open');
  
  if (isOpen) {
    block.classList.remove('is-open');
  } else {
    block.classList.add('is-open');
  }
}
```

---

## 🎯 PADRÕES DE EDIÇÃO INLINE

### HTML
```html
<div class="field editable-field" data-field="nome_campo" data-block="1">
  <div class="field-label-row">
    <label>Nome do Campo</label>
    <span class="field-required">*</span>
  </div>
  <div class="field-input-wrapper">
    <input type="text" name="nome_campo" value="Valor" disabled class="field-input">
    <div class="field-actions">
      <button type="button" class="btn-field-action btn-edit">✏️</button>
      <button type="button" class="btn-field-action btn-save">💾</button>
      <button type="button" class="btn-field-action btn-cancel">❌</button>
    </div>
  </div>
</div>
```

### CSS
```css
/* Botões ocultos por padrão */
.btn-field-action.btn-save,
.btn-field-action.btn-cancel {
  display: none;
}

/* Quando em edição, mostrar save/cancel e ocultar edit */
.editable-field.is-editing .btn-edit {
  display: none;
}

.editable-field.is-editing .btn-save,
.editable-field.is-editing .btn-cancel {
  display: flex;
}
```

### JavaScript
```javascript
function enableEdit(input) {
  const field = input.closest('.editable-field');
  field.classList.add('is-editing');
  input.disabled = false;
  input.focus();
}

function cancelEdit(input, originalValue) {
  const field = input.closest('.editable-field');
  field.classList.remove('is-editing');
  input.value = originalValue;
  input.disabled = true;
}
```

---

## 🚨 ERROS COMUNS E SOLUÇÕES

### Erro 1: CSS não carrega após mudanças

**Causa:** Cache do navegador ou Django  
**Solução:**
```bash
# 1. Coletar estáticos
docker compose exec iamkt_web python manage.py collectstatic --clear --noinput

# 2. Limpar cache Django
docker compose exec iamkt_web python manage.py shell -c "from django.core.cache import cache; cache.clear()"

# 3. Reiniciar servidor
docker compose restart iamkt_web

# 4. Hard refresh no navegador (Ctrl+Shift+R)
```

### Erro 2: JavaScript não executa

**Causa:** Erro de sintaxe ou carregamento  
**Solução:**
1. Abrir Console do navegador (F12)
2. Verificar erros em vermelho
3. Verificar se `console.log('Initialized')` aparece
4. Verificar se arquivo está em `/staticfiles/js/`

### Erro 3: Accordion não abre/fecha

**Causa:** Classes CSS não aplicadas  
**Solução:**
1. Verificar se `.accordion-body` tem `display: none` no CSS
2. Verificar se JavaScript adiciona classe `.is-open`
3. Verificar no DevTools (F12) se classes estão sendo aplicadas

---

## 📊 VALIDAÇÃO DE CÓDIGO

### HTML Validator
```bash
# Validar HTML (usar ferramenta online)
https://validator.w3.org/
```

### CSS Linter
```bash
# Instalar stylelint (se necessário)
npm install -g stylelint

# Validar CSS
stylelint "app/static/css/**/*.css"
```

### JavaScript Linter
```bash
# Instalar eslint (se necessário)
npm install -g eslint

# Validar JavaScript
eslint app/static/js/**/*.js
```

---

## 🎓 REFERÊNCIAS

- [MDN Web Docs](https://developer.mozilla.org/)
- [CSS Tricks](https://css-tricks.com/)
- [Django Static Files](https://docs.djangoproject.com/en/4.2/howto/static-files/)
- [BEM Methodology](http://getbem.com/)

---

## ✅ CHECKLIST FINAL

Antes de considerar uma tarefa concluída:

- [ ] **Zero CSS inline** no HTML
- [ ] **Zero JavaScript inline** no HTML
- [ ] **Classes semânticas** e reutilizáveis
- [ ] **Variáveis CSS** para valores repetidos
- [ ] **Comentários** em código complexo
- [ ] **collectstatic** executado
- [ ] **Cache limpo**
- [ ] **Servidor reiniciado**
- [ ] **Testado no navegador** (hard refresh)
- [ ] **Console sem erros** (F12)
- [ ] **Responsivo** testado (mobile, tablet, desktop)

---

**Este documento é obrigatório para todo desenvolvimento frontend no projeto IAMKT.**

**Última atualização:** 13/01/2026  
**Responsável:** Equipe de Desenvolvimento
