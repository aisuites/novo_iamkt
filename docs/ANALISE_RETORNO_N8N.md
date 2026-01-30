# ANÁLISE: RETORNO N8N E PREPARAÇÃO DA APLICAÇÃO

**Data:** 29/01/2026 23:11

---

## 📥 ESTRUTURA DO RETORNO N8N

```json
{
  "kb_id": 5,
  "organization_id": 9,
  "revision_id": "9bd15d0bef1940ba",
  "payload": [{
    "company_name": {
      "informado_pelo_usuario": "fulanas",
      "avaliacao": "nome da empresa alinhado com o segmento de mercado.",
      "status": "bom",
      "sugestao_do_agente_iamkt": null
    },
    "mission": {
      "informado_pelo_usuario": "ser a melhor pizzaria...",
      "avaliacao": "missão clara e focada.",
      "status": "bom",
      "sugestao_do_agente_iamkt": null
    },
    // ... 22 campos no total
  }],
  "reference_images_analysis": []
}
```

### **Campos Retornados pelo N8N:**
1. company_name
2. mission
3. vision
4. values
5. description
6. target_audience
7. internal_audience
8. internal_segments
9. positioning
10. value_proposition
11. differentials
12. tone_of_voice
13. internal_tone_of_voice
14. recommended_words
15. words_to_avoid
16. palette_colors
17. logo_files
18. fonts
19. website_url
20. social_networks
21. competitors
22. reference_images

---

## ✅ APLICAÇÃO JÁ ESTÁ PREPARADA

### **1. Model `KnowledgeBase` tem campo `n8n_analysis`**
**Arquivo:** `app/apps/knowledge/models.py` (linha 269)

```python
n8n_analysis = models.JSONField(
    default=dict,
    blank=True,
    verbose_name='Análise N8N',
    help_text='Payload completo retornado pelo N8N (primeira análise)'
)
```

✅ **Campo existe e está pronto para receber o retorno**

### **2. View `perfil_view` processa `n8n_analysis`**
**Arquivo:** `app/apps/knowledge/views.py` (linhas 671-734)

```python
# Extrair payload da análise
payload = kb.n8n_analysis.get('payload', [])
campos_raw = payload[0] if isinstance(payload, list) else {}

# Mapear nomes técnicos para labels amigáveis
field_labels = {
    'missao': 'Missão',
    'visao': 'Visão',
    'valores': 'Valores',
    # ... mais campos
}

# Processar campos para o template
campos_analise = {}
for campo_nome, campo_data in campos_raw.items():
    campos_analise[campo_nome] = {
        'label': field_labels.get(campo_nome, ...),
        'status': campo_data.get('status', ''),
        'informado': campo_data.get('informado_pelo_usuario', ''),
        'avaliacao': campo_data.get('avaliacao', ''),
        'sugestao': campo_data.get('sugestao_do_agente_iamkt', '')
    }
```

✅ **View já processa o retorno corretamente**

### **3. Template `perfil.html` exibe os dados**
**Arquivo:** `app/templates/knowledge/perfil.html` (linhas 82-96)

```html
{% for campo_nome, campo_data in campos_analise.items %}
<div class="analysis-card" data-field="{{ campo_nome }}">
    <div class="analysis-card-header">
        <h3 class="analysis-card-title">{{ campo_data.label }}</h3>
        <span class="badge badge-{{ campo_data.status }}">{{ campo_data.status }}</span>
    </div>
    <div class="analysis-card-body">
        <label>INFORMADO</label>
        <p>{{ campo_data.informado }}</p>
        
        <label>AVALIAÇÃO</label>
        <p>{{ campo_data.avaliacao }}</p>
        
        <label>SUGESTÃO</label>
        <p>{{ campo_data.sugestao }}</p>
    </div>
</div>
{% endfor %}
```

✅ **Template já exibe os dados dinamicamente**

---

## ⚠️ PROBLEMAS IDENTIFICADOS

### **1. Labels dos Campos Incompletos**

**Arquivo:** `app/apps/knowledge/views.py` (linha 674)

```python
field_labels = {
    'missao': 'Missão',
    'visao': 'Visão',
    'valores': 'Valores',
    # ... FALTAM MUITOS CAMPOS
}
```

**Campos faltando:**
- company_name
- description
- internal_audience
- internal_segments
- positioning
- value_proposition
- differentials
- tone_of_voice
- internal_tone_of_voice
- recommended_words
- words_to_avoid
- palette_colors
- logo_files
- fonts
- website_url
- social_networks
- competitors
- reference_images

### **2. Ordem dos Campos na Página Perfil**

**Problema:** Campos aparecem na ordem retornada pelo N8N, não na ordem dos blocos da Base de Conhecimento.

**Ordem correta (Base de Conhecimento):**

**BLOCO 1: Identidade Institucional**
1. Nome da empresa
2. Missão
3. Visão
4. Valores & princípios
5. Descrição do Produto/Serviço

**BLOCO 2: Públicos & Segmentos**
6. Público externo
7. Público interno
8. Segmentos internos

**BLOCO 3: Posicionamento & Diferenciais**
9. Posicionamento de mercado
10. Diferenciais competitivos
11. Proposta de valor

**BLOCO 4: Tom de Voz & Linguagem**
12. Tom de voz externo
13. Tom de voz interno
14. Palavras recomendadas
15. Palavras a evitar

**BLOCO 5: Identidade Visual**
16. Cores da identidade visual
17. Tipografia da marca
18. Logotipos
19. Imagens de referência

**BLOCO 6: Sites e Redes Sociais**
20. Site institucional
21. Redes sociais
22. Concorrentes

---

## 🔧 CORREÇÕES NECESSÁRIAS

### **1. Completar `field_labels` com TODOS os campos**

Adicionar labels para todos os 22 campos retornados pelo N8N, usando os mesmos títulos da página Base de Conhecimento.

### **2. Ordenar campos por bloco**

Criar uma lista ordenada de campos seguindo a estrutura dos 6 blocos da Base de Conhecimento.

### **3. Agrupar campos por bloco no template**

Modificar o template para exibir campos agrupados por bloco, com títulos de seção.

---

## ✅ PRÓXIMOS PASSOS

1. ✅ Atualizar `field_labels` com todos os campos
2. ✅ Criar lista ordenada de campos por bloco
3. ✅ Modificar template para agrupar por bloco
4. ✅ Testar com dados reais da Fulanas
