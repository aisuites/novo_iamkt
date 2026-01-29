# ANÁLISE: CAMPOS ENVIADOS AO N8N vs CAMPOS COLETADOS NO FORM

**Data:** 29/01/2026 18:04  
**Objetivo:** Validar quais campos estão sendo enviados ao N8N e identificar campos faltantes

---

## 📤 CAMPOS ATUALMENTE ENVIADOS AO N8N

**Arquivo:** `app/apps/knowledge/services/n8n_service.py` (linhas 108-128)

```python
payload = {
    # Metadados
    'kb_id': kb_instance.id,
    'organization_id': kb_instance.organization_id,
    'organization_name': kb_instance.organization.name,
    'revision_id': revision_id,
    
    # BLOCO 1: Identidade Institucional
    'mission': kb_instance.missao or '',                      # ✅ Enviado
    'vision': kb_instance.visao or '',                        # ✅ Enviado
    'description': kb_instance.descricao_produto or '',       # ✅ Enviado
    
    # BLOCO 3: Posicionamento
    'value_proposition': kb_instance.proposta_valor or '',    # ✅ Enviado
    'differentials': kb_instance.diferenciais or '',          # ✅ Enviado
    
    # BLOCO 2: Públicos
    'target_audience': kb_instance.publico_externo or '',     # ✅ Enviado
    
    # BLOCO 4: Tom de Voz
    'tone_of_voice': kb_instance.tom_voz_externo or '',       # ✅ Enviado
    
    # BLOCO 5: Identidade Visual
    'palette_colors': [c.hex_code for c in kb_instance.colors.all()],           # ✅ Enviado
    'logo_files': [l.s3_url for l in kb_instance.logos.all() if l.s3_url],      # ✅ Enviado
    'fonts': [{'name': ..., 'url': ...} for t in kb_instance.typography_settings.all()],  # ✅ Enviado
    
    # BLOCO 6: Sites e Redes Sociais
    'website_url': kb_instance.site_institucional or '',                         # ✅ Enviado
    'social_networks': [{'platform': s.platform, 'url': s.url} for s in kb_instance.social_networks.all()],  # ✅ Enviado
    'competitors': kb_instance.concorrentes or [],                               # ✅ Enviado
    
    # BLOCO 7: Dados & Insights
    'reference_images': [r.s3_url for r in kb_instance.reference_images.all() if r.s3_url],  # ✅ Enviado
    
    # Campo vazio (não implementado)
    'phrase_10_words': '',  # ❌ Sempre vazio
}
```

---

## 📋 CAMPOS COLETADOS NO FORM (NÃO ENVIADOS)

### **BLOCO 1: Identidade Institucional**
- ✅ `nome_empresa` - **FALTA ENVIAR**
- ✅ `missao` - Enviado como `mission`
- ✅ `visao` - Enviado como `vision`
- ✅ `valores` - **FALTA ENVIAR**
- ✅ `descricao_produto` - Enviado como `description`

### **BLOCO 2: Públicos & Segmentos**
- ✅ `publico_externo` - Enviado como `target_audience`
- ✅ `publico_interno` - **FALTA ENVIAR**
- ✅ `segmentos_internos` (relacionamento) - **FALTA ENVIAR**

### **BLOCO 3: Posicionamento & Diferenciais**
- ✅ `posicionamento` - **FALTA ENVIAR**
- ✅ `proposta_valor` - Enviado como `value_proposition`
- ✅ `diferenciais` - Enviado como `differentials`

### **BLOCO 4: Tom de Voz**
- ✅ `tom_voz_externo` - Enviado como `tone_of_voice`
- ✅ `tom_voz_interno` - **FALTA ENVIAR**
- ✅ `palavras_recomendadas` (JSON) - **FALTA ENVIAR**
- ✅ `palavras_evitar` (JSON) - **FALTA ENVIAR**

### **BLOCO 5: Identidade Visual**
- ✅ `cores` (relacionamento ColorPalette) - Enviado como `palette_colors`
- ✅ `logos` (relacionamento Logo) - Enviado como `logo_files`
- ✅ `tipografia` (relacionamento Typography) - Enviado como `fonts`

### **BLOCO 6: Sites e Redes Sociais**
- ✅ `site_institucional` - Enviado como `website_url`
- ✅ `redes_sociais` (relacionamento SocialNetwork) - Enviado como `social_networks`
- ✅ `concorrentes` (JSON) - Enviado como `competitors`

### **BLOCO 7: Dados & Insights**
- ✅ `imagens_referencia` (relacionamento ReferenceImage) - Enviado como `reference_images`
- ✅ `fontes_confiaveis` (JSON) - Enviado como `trusted_sources`
- ✅ `canais_trends` (JSON) - Enviado como `trend_channels`

---

## ❌ CAMPOS FALTANDO NO PAYLOAD N8N

### **Campos Importantes:**

1. **`nome_empresa`** - Nome da empresa (BLOCO 1)
2. **`valores`** - Valores e princípios (BLOCO 1)
3. **`publico_interno`** - Público interno/colaboradores (BLOCO 2)
4. **`segmentos_internos`** - Lista de segmentos internos (BLOCO 2)
5. **`posicionamento`** - Posicionamento da marca (BLOCO 3)
6. **`tom_voz_interno`** - Tom de voz para comunicação interna (BLOCO 4)
7. **`palavras_recomendadas`** - Lista de palavras recomendadas (BLOCO 4)
8. **`palavras_evitar`** - Lista de palavras a evitar (BLOCO 4)
9. **`dados_insights`** - Dados e insights adicionais (BLOCO 7)

### **Campos Vazios:**

10. **`phrase_10_words`** - Sempre vazio, não existe no form

---

## 🔍 CAMPOS DA MODEL `KnowledgeBase`

**Arquivo:** `app/apps/knowledge/models.py`

```python
# BLOCO 1: Identidade Institucional
nome_empresa = models.CharField(max_length=255)
missao = models.TextField()
visao = models.TextField(blank=True)
valores = models.TextField()
descricao_produto = models.TextField(blank=True)

# BLOCO 2: Público e Segmentos
publico_externo = models.TextField()
publico_interno = models.TextField(blank=True)
# segmentos_internos -> relacionamento InternalSegment

# BLOCO 3: Posicionamento & Diferenciais
posicionamento = models.TextField(blank=True)
proposta_valor = models.TextField(blank=True)
diferenciais = models.TextField(blank=True)

# BLOCO 4: Tom de Voz
tom_voz_externo = models.TextField()
tom_voz_interno = models.TextField(blank=True)
palavras_recomendadas = models.JSONField(default=list, blank=True)
palavras_evitar = models.JSONField(default=list, blank=True)

# BLOCO 5: Identidade Visual
# cores -> ColorPalette (relacionamento)
# logos -> Logo (relacionamento)
# typography_settings -> Typography (relacionamento)

# BLOCO 6: Sites e Redes Sociais
site_institucional = models.URLField(blank=True)
# social_networks -> SocialNetwork (relacionamento)
concorrentes = models.JSONField(default=list, blank=True)

# BLOCO 7: Dados & Insights
# reference_images -> ReferenceImage (relacionamento)
dados_insights = models.TextField(blank=True)
```

---

## 💡 RECOMENDAÇÕES

### **Campos que DEVEM ser adicionados ao payload N8N:**

1. ✅ **`nome_empresa`** - Essencial para identificação
2. ✅ **`valores`** - Importante para análise de identidade
3. ✅ **`posicionamento`** - Crucial para análise de marca
4. ✅ **`palavras_recomendadas`** - Útil para análise de tom de voz
5. ✅ **`palavras_evitar`** - Útil para análise de tom de voz

### **Campos opcionais (avaliar necessidade):**

- ⚠️ **`publico_interno`** - Pode ser útil se N8N analisar comunicação interna
- ⚠️ **`tom_voz_interno`** - Idem acima
- ⚠️ **`segmentos_internos`** - Depende se N8N precisa dessa segmentação
- ⚠️ **`dados_insights`** - Depende do que é armazenado aqui

### **Campos a remover:**

- ❌ **`phrase_10_words`** - Não existe no form, sempre vazio

---

## 📊 RESUMO

- **Total de campos no form:** ~25 campos
- **Campos enviados ao N8N:** 13 campos
- **Campos faltando:** 9-12 campos (dependendo da necessidade)
- **Taxa de cobertura:** ~52%

---

## ✅ PRÓXIMOS PASSOS

1. **Discutir com usuário** quais campos adicionar
2. **Atualizar payload** em `n8n_service.py`
3. **Testar envio** com todos os campos
4. **Validar no N8N** se está recebendo corretamente
