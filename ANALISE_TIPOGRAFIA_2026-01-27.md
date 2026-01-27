# 🔍 ANÁLISE PROFUNDA: TIPOGRAFIA - PROBLEMAS E SOLUÇÕES

**Data:** 27/01/2026 10:35  
**Objetivo:** Identificar e corrigir inconsistências no sistema de tipografia

---

## 🐛 PROBLEMAS IDENTIFICADOS

### **1. CONFLITO DE NOMENCLATURA: `font_type` vs `usage`**

#### **CustomFont Model (apps/knowledge/models.py:355-363)**
```python
font_type = models.CharField(
    max_length=20,
    choices=[
        ('titulo', 'Título'),
        ('corpo', 'Corpo'),
        ('destaque', 'Destaque'),
    ],
    verbose_name='Tipo'
)
```
- ✅ Usa: `font_type` (titulo, corpo, destaque)
- ✅ Valores: lowercase, português

#### **Typography Model (apps/knowledge/models.py:564-567)**
```python
usage = models.CharField(
    max_length=50,
    verbose_name='Uso da Fonte',
    help_text='Ex: Texto corrido, Títulos, Botões, etc'
)
```
- ✅ Usa: `usage` (texto livre)
- ✅ Valores: qualquer string

#### **fonts.js (linha 96)**
```javascript
<select name="fontes[${fonteIndex}][uso]" class="fonte-uso-select">
```
- ✅ Envia: `uso` (TITULO, SUBTITULO, TEXTO, BOTAO, LEGENDA)
- ✅ Valores: UPPERCASE, português

#### **FontService.FONT_TYPE_MAP (apps/knowledge/services.py:203-209)**
```python
FONT_TYPE_MAP = {
    'TITULO': 'titulo',
    'SUBTITULO': 'corpo',
    'TEXTO': 'corpo',
    'BOTAO': 'destaque',
    'LEGENDA': 'corpo'
}
```
- ✅ Mapeia: `uso` (UPPERCASE) → `font_type` (lowercase)

#### **fonts_to_json (templatetags/knowledge_filters.py:63-67)**
```python
font_type_to_uso = {
    'titulo': 'TITULO',
    'corpo': 'TEXTO',
    'destaque': 'BOTAO'
}
```
- ✅ Mapeia: `font_type` (lowercase) → `uso` (UPPERCASE)
- ❌ **PROBLEMA:** Mapeamento inverso incompleto e ambíguo
  - 'corpo' pode ser SUBTITULO, TEXTO ou LEGENDA
  - Sempre retorna TEXTO para 'corpo'

---

### **2. CAMPO `uploaded_by` NÃO PREENCHIDO**

#### **CustomFont Model (apps/knowledge/models.py:377-382)**
```python
uploaded_by = models.ForeignKey(
    User,
    on_delete=models.SET_NULL,
    null=True,
    verbose_name='Enviado por'
)
```

#### **FontService.process_fonts (apps/knowledge/services.py:223-231)**
```python
CustomFont.objects.create(
    knowledge_base=kb,
    name=nome_fonte,
    font_type=font_type,
    s3_key=f'google-fonts/{nome_fonte.replace(" ", "-").lower()}',
    s3_url=f'https://fonts.googleapis.com/css2?family={nome_fonte.replace(" ", "+")}',
    file_format='woff2'
)
```
- ❌ **PROBLEMA:** `uploaded_by` não está sendo preenchido
- ❌ Deveria ser: `uploaded_by=request.user`

---

### **3. TÍTULO DA FONTE NÃO MOSTRA NOME**

#### **fonts.js (linha 72)**
```javascript
<span>Fonte #${fonteIndex + 1} - ${usoLabel}</span>
```
- ❌ **PROBLEMA:** Mostra apenas "Fonte #1 - Texto Corrido"
- ✅ **DEVERIA:** "Fonte #1 - Roboto - Texto Corrido"

#### **Após reload (linha 243)**
```javascript
fonteItem.querySelector('.fonte-item-title span:last-child').textContent = 
    `Fonte #${parseInt(index) + 1} - ${usoLabel}`;
```
- ❌ **PROBLEMA:** Mesmo problema ao atualizar título

---

### **4. MODEL TYPOGRAPHY NÃO ESTÁ SENDO USADO**

#### **Typography Model existe mas:**
- ❌ Não é usado em `FontService.process_fonts()`
- ❌ Não é usado em `fonts.js`
- ❌ Não é usado em `fonts_to_json`
- ❌ `CustomFont` está sendo usado diretamente

**Decisão necessária:**
- Usar `Typography` como model principal?
- Ou remover `Typography` e usar apenas `CustomFont`?

---

## 🎯 ESTRATÉGIA DE CORREÇÃO

### **OPÇÃO A: Usar Typography como Model Principal (RECOMENDADO)**

**Vantagens:**
- ✅ Separação clara: Typography (configuração) vs CustomFont (arquivo)
- ✅ Suporta Google Fonts sem criar CustomFont
- ✅ Campo `usage` mais flexível que `font_type`
- ✅ Permite múltiplos usos da mesma fonte

**Mudanças necessárias:**
1. `FontService.process_fonts()` cria `Typography` ao invés de `CustomFont`
2. `fonts_to_json` lê de `Typography` ao invés de `CustomFont`
3. `fonts.js` envia dados compatíveis com `Typography`
4. `CustomFont` usado apenas para uploads TTF/OTF

---

### **OPÇÃO B: Usar CustomFont como Model Principal**

**Vantagens:**
- ✅ Menos mudanças no código existente
- ✅ Model mais simples

**Desvantagens:**
- ❌ Precisa criar CustomFont mesmo para Google Fonts
- ❌ `font_type` limitado a 3 opções
- ❌ Não suporta múltiplos usos da mesma fonte

---

## ✅ SOLUÇÃO ESCOLHIDA: OPÇÃO A (Typography)

### **Mudanças a implementar:**

#### **1. FontService.process_fonts()**
```python
# ANTES: Criar CustomFont
CustomFont.objects.create(...)

# DEPOIS: Criar Typography
Typography.objects.create(
    knowledge_base=kb,
    usage=uso,  # 'TITULO', 'TEXTO', etc
    font_source='google',
    google_font_name=nome_fonte,
    google_font_weight=variante,
    google_font_url=f'https://fonts.googleapis.com/css2?family={nome_fonte}',
    order=int(index),
    updated_by=request.user  # ✅ CORRIGE PROBLEMA 2
)
```

#### **2. fonts_to_json()**
```python
# ANTES: Ler de CustomFont
for font in queryset:  # queryset = kb.custom_fonts.all()

# DEPOIS: Ler de Typography
for typo in queryset:  # queryset = kb.typography_settings.all()
    fonts_list.append({
        'id': typo.id,
        'tipo': 'GOOGLE' if typo.font_source == 'google' else 'UPLOAD',
        'nome': typo.google_font_name or typo.custom_font.name,
        'uso': typo.usage,  # Já está correto
        'variante': typo.google_font_weight or '400',
        'arquivo_url': typo.custom_font.s3_url if typo.custom_font else ''
    })
```

#### **3. fonts.js - Título com nome da fonte**
```javascript
// ANTES:
<span>Fonte #${fonteIndex + 1} - ${usoLabel}</span>

// DEPOIS:
<span>Fonte #${fonteIndex + 1} - ${nomeFonte || 'Selecione...'} - ${usoLabel}</span>
```

#### **4. fonts.js - Atualizar título ao mudar fonte**
```javascript
function updateFontePreview(index) {
    // ... código existente ...
    
    // ✅ ADICIONAR: Atualizar título
    const usoLabel = fonteItem.querySelector('.fonte-uso-select option:checked').textContent;
    fonteItem.querySelector('.fonte-item-title span:last-child').textContent = 
        `Fonte #${parseInt(index) + 1} - ${nomeFonte || 'Selecione...'} - ${usoLabel}`;
}
```

---

## 📋 CHECKLIST DE IMPLEMENTAÇÃO

### **Backend:**
- [ ] Modificar `FontService.process_fonts()` para criar `Typography`
- [ ] Adicionar `updated_by=request.user` na criação
- [ ] Modificar `fonts_to_json()` para ler de `typography_settings`
- [ ] Atualizar mapeamento de campos
- [ ] Limpar fontes antigas: `kb.custom_fonts.all().delete()` → `kb.typography_settings.all().delete()`

### **Frontend:**
- [ ] Atualizar título inicial em `addFonte()` para incluir nome da fonte
- [ ] Atualizar título em `updateFontePreview()` ao mudar fonte
- [ ] Atualizar título em `updateFonteUso()` ao mudar uso
- [ ] Garantir que nome da fonte aparece após reload

### **Testes:**
- [ ] Adicionar fonte Google Fonts
- [ ] Verificar que `updated_by` é preenchido
- [ ] Verificar que título mostra "Fonte #1 - Roboto - Texto Corrido"
- [ ] Salvar e recarregar página
- [ ] Verificar que dados persistem corretamente
- [ ] Verificar que título permanece correto após reload

---

## 🔄 FLUXO CORRETO APÓS CORREÇÃO

### **Salvamento:**
1. User preenche formulário: uso=TITULO, nome=Roboto, variante=400
2. `fonts.js` envia: `fontes[0][uso]=TITULO`, `fontes[0][nome_fonte]=Roboto`, `fontes[0][variante]=400`
3. `FontService.process_fonts()` recebe dados
4. Cria `Typography`:
   - `usage='TITULO'`
   - `font_source='google'`
   - `google_font_name='Roboto'`
   - `google_font_weight='400'`
   - `updated_by=request.user` ✅
5. Salva no banco

### **Reload:**
1. View carrega: `typography_settings = kb.typography_settings.all()`
2. `fonts_to_json(typography_settings)` converte para JSON
3. `fonts.js` recebe: `{tipo: 'GOOGLE', nome: 'Roboto', uso: 'TITULO', variante: '400'}`
4. `addFonte('GOOGLE', 'Roboto', '400', 'TITULO')` cria item
5. Título mostra: "Fonte #1 - Roboto - Títulos (H1)" ✅

---

**Análise completa. Pronto para implementar correções.**
