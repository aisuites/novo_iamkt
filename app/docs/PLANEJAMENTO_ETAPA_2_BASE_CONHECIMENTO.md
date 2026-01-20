# 📚 PLANEJAMENTO ETAPA 2: BASE DE CONHECIMENTO

**Data:** 13 de Janeiro de 2026  
**Duração Estimada:** 2 semanas  
**Pré-requisito:** ✅ Etapa 1 Concluída

---

## 🎯 OBJETIVO

Desenvolver interface completa de edição da Base de Conhecimento FEMME com 7 blocos accordion, upload de assets para S3, sistema anti-repetição de imagens e histórico de alterações.

---

## 📋 ANÁLISE DOS 7 BLOCOS

### BLOCO 1: IDENTIDADE INSTITUCIONAL

**Campos no Model KnowledgeBase:**
```python
nome_empresa = CharField(max_length=200)           # ✅ Existe
missao = TextField()                                # ✅ Existe
visao = TextField(blank=True)                       # ✅ Existe
valores = TextField()                               # ✅ Existe
historia = TextField(blank=True)                    # ✅ Existe
```

**Tipo de Campos:**
- ✅ Todos são TextField/CharField simples
- ✅ Podem ser editados via formulário padrão
- ✅ Validação: nome_empresa, missao, valores são obrigatórios

**Interface Necessária:**
- Input text para nome_empresa
- Textarea para missao, visao, valores, historia
- Indicador de obrigatoriedade

---

### BLOCO 2: PÚBLICO E SEGMENTOS

**Campos no Model KnowledgeBase:**
```python
publico_externo = TextField()                       # ✅ Existe
publico_interno = TextField(blank=True)             # ✅ Existe
segmentos_internos = JSONField(default=list)        # ✅ Existe
```

**Tipo de Campos:**
- ✅ publico_externo, publico_interno: TextField
- ✅ segmentos_internos: JSONField (Array de strings)

**Interface Necessária:**
- Textarea para publico_externo, publico_interno
- **Campo dinâmico** para segmentos_internos:
  - Lista editável (adicionar/remover itens)
  - Cada item é uma string
  - Exemplo: ["Gestores", "Operacional", "Médicos Solicitantes"]

**Validação:**
- publico_externo é obrigatório
- segmentos_internos pode ser vazio (lista vazia)

---

### BLOCO 3: POSICIONAMENTO E DIFERENCIAIS

**Campos no Model KnowledgeBase:**
```python
posicionamento = TextField()                        # ✅ Existe
diferenciais = TextField()                          # ✅ Existe
proposta_valor = TextField(blank=True)              # ✅ Existe
```

**Tipo de Campos:**
- ✅ Todos são TextField simples

**Interface Necessária:**
- Textarea para posicionamento, diferenciais, proposta_valor
- Indicador de obrigatoriedade (posicionamento, diferenciais)

**Model Relacionado: Competitor**
- ✅ Já existe no banco
- ✅ Gerenciado via Admin Django
- ✅ Não precisa estar no accordion (link para admin)

---

### BLOCO 4: TOM DE VOZ E LINGUAGEM

**Campos no Model KnowledgeBase:**
```python
tom_voz_externo = TextField()                       # ✅ Existe
tom_voz_interno = TextField(blank=True)             # ✅ Existe
palavras_recomendadas = JSONField(default=list)     # ✅ Existe
palavras_evitar = JSONField(default=list)           # ✅ Existe
```

**Tipo de Campos:**
- ✅ tom_voz_externo, tom_voz_interno: TextField
- ✅ palavras_recomendadas, palavras_evitar: JSONField (Array de strings)

**Interface Necessária:**
- Textarea para tom_voz_externo, tom_voz_interno
- **Campos dinâmicos** para palavras:
  - Lista editável (adicionar/remover)
  - Tags visuais (chips/badges)
  - Exemplo: ["cuidar", "prevenir", "saúde", "bem-estar"]

**Validação:**
- tom_voz_externo é obrigatório
- palavras_recomendadas e palavras_evitar devem ter pelo menos 1 item cada

---

### BLOCO 5: IDENTIDADE VISUAL

**Campos no Model KnowledgeBase:**
```python
paleta_cores = JSONField(default=dict)              # ✅ Existe
tipografia = JSONField(default=dict)                # ✅ Existe
```

**⚠️ ATENÇÃO: Documentação vs Model**

**Documentação especifica:**
- ColorPalette como model separado
- CustomFont como model separado (✅ já existe)
- Logo como model separado (✅ já existe)
- ReferenceImage como model separado (✅ já existe)

**Model atual usa:**
- paleta_cores: JSONField (dict)
- tipografia: JSONField (dict)

**DECISÃO NECESSÁRIA:**

**Opção A: Manter JSONField (mais simples)**
```json
{
  "paleta_cores": {
    "primaria": "#6B2C91",
    "secundaria": "#E91E63",
    "acento": "#2196F3"
  },
  "tipografia": {
    "titulo": "Montserrat",
    "corpo": "Open Sans",
    "destaque": "Playfair Display"
  }
}
```

**Opção B: Criar models separados (mais flexível)**
- Criar model ColorPalette (nome, hex, tipo, ordem)
- Usar CustomFont existente
- Permite color picker visual
- Permite upload de fontes

**RECOMENDAÇÃO:** Opção B (seguir documentação)
- Mais escalável
- Melhor UX (color picker)
- Permite upload de fontes customizadas
- Já temos CustomFont, Logo, ReferenceImage

**Models Relacionados:**
- ✅ CustomFont (já existe)
- ✅ Logo (já existe)
- ✅ ReferenceImage (já existe)
- ❌ ColorPalette (PRECISA CRIAR)

**Interface Necessária:**
- **Color Picker** para paleta_cores
- **Upload de fontes** (TTF/OTF/WOFF) para S3
- **Upload de logos** (SVG/PNG) para S3
- **Upload de imagens de referência** para S3
- **Sistema anti-repetição** (hash perceptual)

---

### BLOCO 6: SITES E REDES SOCIAIS

**Campos no Model KnowledgeBase:**
```python
site_institucional = URLField(blank=True)           # ✅ Existe
redes_sociais = JSONField(default=dict)             # ✅ Existe
templates_redes = JSONField(default=dict)           # ✅ Existe
```

**⚠️ ATENÇÃO: Documentação vs Model**

**Documentação especifica:**
- SocialNetwork como model separado
- SocialNetworkTemplate como model separado

**Model atual usa:**
- redes_sociais: JSONField (dict)
- templates_redes: JSONField (dict)

**DECISÃO NECESSÁRIA:**

**Opção A: Manter JSONField**
```json
{
  "redes_sociais": {
    "instagram": {
      "url": "https://instagram.com/femme",
      "username": "@femme",
      "ativa": true
    },
    "linkedin": {
      "url": "https://linkedin.com/company/femme",
      "username": "FEMME",
      "ativa": true
    }
  }
}
```

**Opção B: Criar models separados**
- Model SocialNetwork (nome, tipo, url, username, ativa, ordem)
- Model SocialNetworkTemplate (rede, nome, width, height, aspect_ratio, limite_caracteres)

**RECOMENDAÇÃO:** Opção B (seguir documentação)
- Gerenciável via Admin sem código
- Mais flexível para adicionar novas redes
- Melhor para validações específicas

**Models a Criar:**
- ❌ SocialNetwork (PRECISA CRIAR)
- ❌ SocialNetworkTemplate (PRECISA CRIAR)

**Interface Necessária:**
- Input URL para site_institucional
- **Lista gerenciável** de redes sociais (via Admin ou interface)
- Link para Admin Django para gerenciar templates

---

### BLOCO 7: DADOS E INSIGHTS

**Campos no Model KnowledgeBase:**
```python
fontes_confiaveis = JSONField(default=list)         # ✅ Existe
canais_trends = JSONField(default=list)             # ✅ Existe
palavras_chave_trends = JSONField(default=list)     # ✅ Existe
```

**Tipo de Campos:**
- ✅ Todos são JSONField (Array)

**Interface Necessária:**
- **Lista editável** de URLs para fontes_confiaveis
  - Validação de URL
  - Exemplo: ["https://www.saude.gov.br", "https://portal.fiocruz.br"]
- **Lista editável** de canais_trends (JSON complexo)
  - Cada item: {nome, tipo, url, ativo}
  - Tipos: rss, youtube, scraping
- **Lista editável** de palavras_chave_trends
  - Tags visuais
  - Exemplo: ["saúde", "prevenção", "exames"]

**Validação:**
- fontes_confiaveis deve ter pelo menos 1 URL

---

## 🔧 MODELS A CRIAR/AJUSTAR

### ❌ ColorPalette (NOVO)

```python
class ColorPalette(models.Model):
    knowledge_base = models.ForeignKey(KnowledgeBase, on_delete=models.CASCADE, related_name='colors')
    name = models.CharField(max_length=100)  # "Roxo FEMME"
    hex_code = models.CharField(max_length=7)  # "#6B2C91"
    color_type = models.CharField(
        max_length=20,
        choices=[
            ('primary', 'Primária'),
            ('secondary', 'Secundária'),
            ('accent', 'Acento'),
        ]
    )
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['order', 'name']
        unique_together = [['knowledge_base', 'name']]
```

### ❌ SocialNetwork (NOVO)

```python
class SocialNetwork(models.Model):
    knowledge_base = models.ForeignKey(KnowledgeBase, on_delete=models.CASCADE, related_name='social_networks')
    name = models.CharField(max_length=100)
    network_type = models.CharField(
        max_length=20,
        choices=[
            ('instagram', 'Instagram'),
            ('facebook', 'Facebook'),
            ('linkedin', 'LinkedIn'),
            ('youtube', 'YouTube'),
            ('tiktok', 'TikTok'),
            ('twitter', 'Twitter/X'),
            ('other', 'Outro'),
        ]
    )
    url = models.URLField()
    username = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['order', 'name']
```

### ❌ SocialNetworkTemplate (NOVO)

```python
class SocialNetworkTemplate(models.Model):
    social_network = models.ForeignKey(SocialNetwork, on_delete=models.CASCADE, related_name='templates')
    name = models.CharField(max_length=100)  # "Feed 1:1", "Stories"
    width = models.IntegerField()  # 1080
    height = models.IntegerField()  # 1080
    aspect_ratio = models.CharField(max_length=10)  # "1:1"
    character_limit = models.IntegerField(null=True, blank=True)  # 2200
    hashtag_limit = models.IntegerField(null=True, blank=True)  # 30
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['social_network', 'name']
```

### ✅ ReferenceImage (JÁ EXISTE - AJUSTAR)

**Adicionar campo perceptual_hash se não existir:**
```python
perceptual_hash = models.CharField(max_length=64, help_text='Para evitar imagens similares')
```

**Implementar função de hash perceptual:**
- Usar biblioteca `imagehash` (PIL)
- Calcular ao fazer upload
- Comparar antes de aceitar nova imagem

---

## 🎨 INTERFACE ACCORDION (7 BLOCOS)

### Estrutura HTML

```html
<div class="knowledge-accordion">
  <!-- Bloco 1: Identidade -->
  <div class="accordion-item" data-block="identidade">
    <div class="accordion-header">
      <span class="block-icon">🏢</span>
      <h3>1. Identidade Institucional</h3>
      <span class="completude-badge">80%</span>
      <button class="toggle-btn">▼</button>
    </div>
    <div class="accordion-body">
      <form id="form-bloco-1">
        <!-- Campos do bloco 1 -->
        <button type="submit">Salvar Bloco</button>
      </form>
    </div>
  </div>
  
  <!-- Repetir para blocos 2-7 -->
</div>

<div class="knowledge-actions">
  <button id="save-all">Salvar Tudo</button>
  <button id="view-history">Ver Histórico</button>
</div>
```

### Funcionalidades JavaScript

**1. Toggle Accordion**
```javascript
// Expandir/recolher blocos
// Salvar estado no localStorage
// Permitir múltiplos blocos abertos
```

**2. Salvamento Individual**
```javascript
// AJAX para salvar cada bloco
// Atualizar completude em tempo real
// Feedback visual de sucesso/erro
```

**3. Salvamento Geral**
```javascript
// Salvar todos os blocos de uma vez
// Validação global
// Redirect após sucesso
```

**4. Indicador de Completude**
```javascript
// Calcular % de preenchimento
// Atualizar badge em tempo real
// Cor: vermelho (<30%), amarelo (30-70%), verde (>70%)
```

**5. Upload de Arquivos**
```javascript
// Drag & drop para imagens/fontes/logos
// Preview antes do upload
// Progress bar
// Upload para S3 via backend
```

**6. Campos Dinâmicos (Arrays)**
```javascript
// Adicionar/remover itens de lista
// Tags visuais (chips)
// Validação de duplicatas
```

**7. Color Picker**
```javascript
// Seletor de cor visual
// Preview da paleta
// Validação de hex code
```

---

## 🔄 SISTEMA ANTI-REPETIÇÃO DE IMAGENS

### Implementação

**1. Biblioteca:**
```bash
pip install imagehash pillow
```

**2. Função de Hash Perceptual:**
```python
import imagehash
from PIL import Image

def calculate_perceptual_hash(image_file):
    """
    Calcula hash perceptual da imagem
    Retorna: string de 64 caracteres
    """
    img = Image.open(image_file)
    hash_value = imagehash.phash(img, hash_size=16)
    return str(hash_value)
```

**3. Verificação de Similaridade:**
```python
def is_image_similar(new_hash, threshold=10):
    """
    Verifica se imagem é similar às existentes
    threshold: diferença máxima permitida (0-64)
    """
    existing_images = ReferenceImage.objects.all()
    
    for img in existing_images:
        hash_diff = imagehash.hex_to_hash(new_hash) - imagehash.hex_to_hash(img.perceptual_hash)
        if hash_diff < threshold:
            return True, img  # Similar encontrada
    
    return False, None  # Não é similar
```

**4. Workflow de Upload:**
```
1. Usuário faz upload
2. Backend calcula hash perceptual
3. Compara com imagens existentes
4. Se similar (diff < 10): alerta usuário
5. Se não similar: salva no S3 + banco
```

---

## 📊 INDICADOR DE COMPLETUDE

### Cálculo Automático

**Já implementado no model:**
```python
def calculate_completude(self):
    score = 0
    total_blocks = 7
    
    # Bloco 1: 3 campos obrigatórios
    if all([self.nome_empresa, self.missao, self.valores]):
        score += 1
    
    # Bloco 2: 1 campo obrigatório
    if self.publico_externo:
        score += 1
    
    # Bloco 3: 2 campos obrigatórios
    if all([self.posicionamento, self.diferenciais]):
        score += 1
    
    # Bloco 4: 3 campos obrigatórios
    if all([
        self.tom_voz_externo,
        len(self.palavras_recomendadas) > 0,
        len(self.palavras_evitar) > 0
    ]):
        score += 1
    
    # Bloco 5: 2 campos obrigatórios
    if all([
        len(self.paleta_cores) > 0,
        len(self.tipografia) > 0
    ]):
        score += 1
    
    # Bloco 6: 1 campo obrigatório
    if self.site_institucional or len(self.redes_sociais) > 0:
        score += 1
    
    # Bloco 7: 1 campo obrigatório
    if len(self.fontes_confiaveis) > 0:
        score += 1
    
    return int((score / total_blocks) * 100)
```

**Interface Visual:**
```html
<div class="completude-indicator">
  <div class="progress-bar">
    <div class="progress-fill" style="width: 80%"></div>
  </div>
  <span class="percentage">80%</span>
</div>
```

---

## 📜 HISTÓRICO DE ALTERAÇÕES

### Model KnowledgeChangeLog

**Já implementado:**
```python
class KnowledgeChangeLog(models.Model):
    knowledge_base = ForeignKey(KnowledgeBase)
    user = ForeignKey(User)
    block_name = CharField(max_length=50)  # "Identidade", "Público", etc
    field_name = CharField(max_length=100)  # "missao", "valores", etc
    old_value = TextField(blank=True)
    new_value = TextField()
    change_summary = CharField(max_length=500)
    created_at = DateTimeField(auto_now_add=True)
```

### Implementação

**1. Signal para capturar mudanças:**
```python
from django.db.models.signals import pre_save
from django.dispatch import receiver

@receiver(pre_save, sender=KnowledgeBase)
def log_knowledge_changes(sender, instance, **kwargs):
    if instance.pk:  # Se já existe (update)
        old_instance = KnowledgeBase.objects.get(pk=instance.pk)
        
        # Comparar campos e registrar mudanças
        fields_to_track = ['missao', 'visao', 'valores', ...]
        
        for field in fields_to_track:
            old_val = getattr(old_instance, field)
            new_val = getattr(instance, field)
            
            if old_val != new_val:
                KnowledgeChangeLog.objects.create(
                    knowledge_base=instance,
                    user=instance.last_updated_by,
                    block_name=get_block_name(field),
                    field_name=field,
                    old_value=str(old_val),
                    new_value=str(new_val),
                    change_summary=f"Alterou {field}"
                )
```

**2. Interface de Histórico:**
```html
<div class="history-modal">
  <h2>Histórico de Alterações</h2>
  <div class="timeline">
    <div class="timeline-item">
      <span class="date">13/01/2026 10:30</span>
      <span class="user">João Silva</span>
      <span class="block">Identidade</span>
      <span class="field">Missão</span>
      <button class="view-diff">Ver Diferença</button>
    </div>
  </div>
</div>
```

---

## 🚀 PLANO DE IMPLEMENTAÇÃO

### Fase 1: Models e Migrations (2 dias)

**Dia 1:**
- ✅ Criar model ColorPalette
- ✅ Criar model SocialNetwork
- ✅ Criar model SocialNetworkTemplate
- ✅ Ajustar ReferenceImage (adicionar perceptual_hash se necessário)
- ✅ Criar migrations
- ✅ Aplicar migrations
- ✅ Testar no Admin Django

**Dia 2:**
- ✅ Implementar sistema de hash perceptual
- ✅ Criar função calculate_perceptual_hash()
- ✅ Criar função is_image_similar()
- ✅ Testar upload e comparação
- ✅ Implementar signal para KnowledgeChangeLog

### Fase 2: Views e Forms (3 dias)

**Dia 3:**
- ✅ Criar view knowledge_edit (GET)
- ✅ Criar forms para cada bloco
- ✅ Implementar validações
- ✅ Testar renderização

**Dia 4:**
- ✅ Implementar salvamento individual (AJAX)
- ✅ Implementar salvamento geral
- ✅ Implementar upload de arquivos para S3
- ✅ Testar fluxo completo

**Dia 5:**
- ✅ Implementar view de histórico
- ✅ Implementar filtros de histórico
- ✅ Implementar diff viewer
- ✅ Testar histórico

### Fase 3: Frontend (4 dias)

**Dia 6:**
- ✅ Criar template accordion
- ✅ Implementar CSS (seguir design FEMME)
- ✅ Implementar JavaScript toggle
- ✅ Testar responsividade

**Dia 7:**
- ✅ Implementar campos dinâmicos (arrays)
- ✅ Implementar tags visuais
- ✅ Implementar color picker
- ✅ Testar interações

**Dia 8:**
- ✅ Implementar upload drag & drop
- ✅ Implementar preview de imagens
- ✅ Implementar progress bar
- ✅ Testar uploads

**Dia 9:**
- ✅ Implementar indicador de completude
- ✅ Implementar atualização em tempo real
- ✅ Implementar feedback visual
- ✅ Testar UX completa

### Fase 4: Testes e Ajustes (3 dias)

**Dia 10:**
- ✅ Testes de integração
- ✅ Testes de validação
- ✅ Testes de upload S3
- ✅ Testes de hash perceptual

**Dia 11:**
- ✅ Testes de permissões
- ✅ Testes de histórico
- ✅ Testes de performance
- ✅ Correção de bugs

**Dia 12:**
- ✅ Testes de responsividade
- ✅ Testes de acessibilidade
- ✅ Ajustes finais de UX
- ✅ Documentação

### Fase 5: Deploy e Validação (2 dias)

**Dia 13:**
- ✅ Deploy em staging
- ✅ Testes de aceitação
- ✅ Ajustes finais
- ✅ Preparar dados de exemplo

**Dia 14:**
- ✅ Deploy em produção
- ✅ Validação final
- ✅ Treinamento de usuários
- ✅ Documentação de uso

---

## ✅ CHECKLIST DE ENTREGA

### Models
- [ ] ColorPalette criado e testado
- [ ] SocialNetwork criado e testado
- [ ] SocialNetworkTemplate criado e testado
- [ ] ReferenceImage com perceptual_hash
- [ ] KnowledgeChangeLog funcionando

### Backend
- [ ] View knowledge_edit (GET/POST)
- [ ] Forms para 7 blocos
- [ ] Upload para S3 funcionando
- [ ] Hash perceptual implementado
- [ ] Signal de histórico funcionando
- [ ] Validações completas

### Frontend
- [ ] Interface accordion responsiva
- [ ] 7 blocos funcionais
- [ ] Salvamento individual
- [ ] Salvamento geral
- [ ] Upload drag & drop
- [ ] Color picker
- [ ] Campos dinâmicos (arrays)
- [ ] Tags visuais
- [ ] Indicador de completude
- [ ] Modal de histórico

### Testes
- [ ] Testes unitários (models)
- [ ] Testes de integração (views)
- [ ] Testes de upload S3
- [ ] Testes de hash perceptual
- [ ] Testes de permissões
- [ ] Testes de responsividade

### Documentação
- [ ] README de uso
- [ ] Documentação técnica
- [ ] Guia de usuário
- [ ] Changelog

---

## 🎯 CRITÉRIOS DE ACEITE

### Funcionalidades Obrigatórias
- ✅ Interface accordion com 7 blocos expansíveis
- ✅ Salvamento individual por bloco
- ✅ Salvamento geral de todos os blocos
- ✅ Upload de logos para S3
- ✅ Upload de fontes para S3
- ✅ Upload de imagens de referência para S3
- ✅ Sistema anti-repetição de imagens (hash perceptual)
- ✅ Indicador de completude em tempo real
- ✅ Histórico de alterações com diff viewer
- ✅ Validação de campos obrigatórios
- ✅ Feedback visual de sucesso/erro
- ✅ Responsivo (mobile, tablet, desktop)

### Performance
- ✅ Carregamento da página < 2s
- ✅ Upload de imagem < 5s
- ✅ Salvamento de bloco < 1s
- ✅ Cálculo de completude instantâneo

### Segurança
- ✅ Apenas usuários autenticados
- ✅ Permissões por perfil (admin, ti, gestor)
- ✅ Validação de tipos de arquivo
- ✅ Sanitização de inputs
- ✅ CSRF protection

### UX
- ✅ Interface intuitiva
- ✅ Feedback claro de ações
- ✅ Indicadores visuais de obrigatoriedade
- ✅ Preview de uploads
- ✅ Confirmação antes de ações destrutivas

---

**Próximo Passo:** Iniciar Fase 1 - Criar models ColorPalette, SocialNetwork e SocialNetworkTemplate
