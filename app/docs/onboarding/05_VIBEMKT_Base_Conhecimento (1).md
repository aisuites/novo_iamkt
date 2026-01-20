# 📚 IAMKT - BASE DE CONHECIMENTO FEMME

**Documento:** 05 de 10  
**Versão:** 1.0  
**Data:** Janeiro 2026

---

## 🎯 VISÃO GERAL

A **Base de Conhecimento FEMME** é o coração da plataforma IAMKT. Funciona como o "DNA" da marca que alimenta todas as gerações de conteúdo, garantindo consistência e alinhamento em todas as comunicações.

### Características Principais

- **Instância Única (Singleton)**: Existe apenas UMA base de conhecimento
- **7 Blocos Temáticos**: Organização clara e lógica
- **Interface Sanfona (Accordion)**: Edição organizada bloco por bloco
- **Salvamento Incremental**: Salvar cada bloco individualmente ou tudo de uma vez
- **Histórico de Alterações**: Rastreabilidade completa
- **Status de Completude**: Indicador visual de preenchimento

---

## 📋 ESTRUTURA DOS 7 BLOCOS

### BLOCO 1: IDENTIDADE INSTITUCIONAL

**Objetivo:** Definir quem é a empresa, sua missão, visão e valores.

#### Campos

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| **Nome da Empresa** | Texto curto | ✅ | Nome oficial e variações aceitas |
| **Descrição Resumida** | Texto longo | ✅ | Elevator pitch (2-3 linhas) |
| **Missão** | Texto longo | ✅ | Razão de existir da empresa |
| **Visão** | Texto longo | ✅ | Onde a empresa quer chegar |
| **Valores e Princípios** | Lista (Array) | ✅ | Lista de valores fundamentais |

#### Exemplo de Preenchimento

```yaml
Nome da Empresa: "FEMME - Diagnóstico e Medicina Preventiva"

Descrição Resumida: "Centro de diagnóstico e medicina preventiva que oferece exames laboratoriais e de imagem com tecnologia de ponta e atendimento humanizado."

Missão: "Promover saúde e bem-estar através de diagnósticos precisos e atendimento acolhedor, contribuindo para a prevenção de doenças e qualidade de vida."

Visão: "Ser referência regional em medicina diagnóstica, reconhecida pela excelência técnica e atendimento humanizado."

Valores e Princípios:
  - "Excelência técnica"
  - "Atendimento humanizado"
  - "Ética e transparência"
  - "Inovação e tecnologia"
  - "Compromisso com a prevenção"
```

---

### BLOCO 2: PÚBLICO E SEGMENTOS

**Objetivo:** Definir perfis de público-alvo e segmentações internas.

#### Campos

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| **Público-Alvo Externo** | Texto longo | ✅ | Perfil dos clientes/pacientes |
| **Público Interno** | Texto longo | ✅ | Perfil dos colaboradores |
| **Segmentos Internos** | Lista (Array) | ❌ | Divisões de público específicas |

#### Exemplo de Preenchimento

```yaml
Público-Alvo Externo: |
  Homens e mulheres de 25 a 65 anos, classes B e C, residentes em 
  São Gonçalo do Amarante e região. Preocupados com saúde preventiva, 
  buscam qualidade e agilidade nos exames. Valorizam atendimento 
  humanizado e resultados confiáveis.

Público Interno: |
  Equipe multidisciplinar composta por médicos, enfermeiros, técnicos 
  de laboratório e atendentes. Profissionais comprometidos com 
  excelência técnica e atendimento acolhedor.

Segmentos Internos:
  - "Médicos Solicitantes"
  - "Pacientes de Check-up Executivo"
  - "Pacientes de Exames de Rotina"
  - "Empresas (Medicina do Trabalho)"
  - "Idosos (60+)"
  - "Gestantes"
```

**Uso:** Quando gerar pautas/posts, usuário seleciona "Externo" ou "Interno".

---

### BLOCO 3: POSICIONAMENTO E DIFERENCIAIS

**Objetivo:** Definir como a marca quer ser percebida e o que a torna única.

#### Campos

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| **Posicionamento da Marca** | Texto longo | ✅ | Como quer ser percebida |
| **Principais Diferenciais** | Lista (Array) | ✅ | O que torna a marca única |
| **Concorrentes** | Relacionado | ❌ | Gerenciado no model Competitor |

#### Exemplo de Preenchimento

```yaml
Posicionamento da Marca: |
  FEMME é o centro de diagnóstico que une tecnologia de ponta com 
  atendimento humanizado. Somos a escolha de quem busca exames precisos 
  sem abrir mão do acolhimento e da agilidade.

Principais Diferenciais:
  - "Equipamentos de última geração"
  - "Resultados em até 24 horas"
  - "Atendimento humanizado e acolhedor"
  - "Equipe técnica altamente qualificada"
  - "Ambiente confortável e moderno"
  - "Localização de fácil acesso"
  - "Parceria com principais convênios"
```

#### Concorrentes (Model Separado)

Gerenciados via Admin Django no model `Competitor`:

| Campo | Descrição |
|-------|-----------|
| Nome | Nome do concorrente |
| URL | Site do concorrente |
| Descrição | Breve descrição |
| Scraping Ativo | Se deve fazer scraping automático |
| Análise IA | Análise automática de posicionamento, diferenciais, tom de voz |

**Scraping Automático:**
- Frequência: Semanal (domingos à noite)
- O que extrai: Estrutura do site, serviços oferecidos, tom de voz
- IA analisa e salva insights
- Botão manual "Analisar Agora" disponível

---

### BLOCO 4: TOM DE VOZ E LINGUAGEM

**Objetivo:** Definir como a marca se comunica (linguagem, tom, palavras).

#### Campos

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| **Tom de Voz Externo** | Texto longo | ✅ | Como falar com público externo |
| **Palavras Recomendadas** | Lista (Array) | ✅ | Termos preferidos |
| **Tom de Voz Interno** | Texto longo | ✅ | Como comunicar com colaboradores |
| **Palavras a Evitar** | Lista (Array) | ✅ | Termos proibidos/desencorajados |

#### Exemplo de Preenchimento

```yaml
Tom de Voz Externo: |
  Acolhedor, confiável e acessível. Usamos linguagem clara e direta, 
  sem jargões médicos excessivos. Transmitimos segurança técnica sem 
  perder a empatia. Tom positivo e encorajador sobre prevenção.

Palavras Recomendadas:
  - "cuidar"
  - "prevenir"
  - "saúde"
  - "bem-estar"
  - "acolhimento"
  - "precisão"
  - "confiança"
  - "qualidade de vida"

Tom de Voz Interno: |
  Motivacional, respeitoso e colaborativo. Valorizamos o trabalho em 
  equipe e o desenvolvimento profissional. Linguagem técnica quando 
  necessário, mas sempre clara.

Palavras a Evitar:
  - "barato"
  - "promoção"
  - "desconto imperdível"
  - "milagre"
  - "garantido"
  - jargões excessivamente técnicos sem explicação
```

**Uso IA:** Toda geração de texto verifica palavras recomendadas/evitar automaticamente.

---

### BLOCO 5: IDENTIDADE VISUAL

**Objetivo:** Definir cores, tipografia e elementos visuais da marca.

#### 5.1 Paleta de Cores (Model ColorPalette)

Gerenciada via relacionamento com model `ColorPalette`:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| Nome | Texto | "Roxo Primário", "Rosa Acento" |
| Código HEX | Texto | "#6B2C91" |
| Tipo | Seleção | Primária / Secundária / Acento |
| Ordem | Número | Ordem de exibição |

**Interface:**
- Color picker visual
- Preview das cores em cards
- Mínimo 2 cores, máximo 10
- IA usa essas cores na geração de imagens

**Exemplo:**
```yaml
Cores:
  - Nome: "Roxo FEMME"
    HEX: "#6B2C91"
    Tipo: Primária
  
  - Nome: "Rosa Vibrante"
    HEX: "#E91E63"
    Tipo: Acento
  
  - Nome: "Azul Confiança"
    HEX: "#2196F3"
    Tipo: Secundária
```

#### 5.2 Tipografia (Model CustomFont)

Duas opções de fonte:

**A) Google Fonts:**
```yaml
Tipo: Google Fonts
Nome: "Montserrat"
URL: "https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700"
Principal: true
```

**B) Upload OTF/TTF:**
```yaml
Tipo: Upload
Nome: "FEMMECustom"
Arquivo: upload para S3
Principal: false
```

**Limites:**
- Máximo 5 fontes no total
- Apenas 1 pode ser "principal"

#### 5.3 Logotipo

| Campo | Tipo | Descrição |
|-------|------|-----------|
| Upload | Arquivo | SVG ou PNG (preferir SVG) |
| URL S3 | Auto | Gerada automaticamente após upload |

**Processo:**
1. Upload via interface
2. Arquivo salvo temporariamente
3. Movido para S3 bucket `iamkt-logos/`
4. URL salva no campo `logotipo_s3_url`

#### 5.4 Imagens de Referência (Model ReferenceImage)

Imagens que definem o estilo visual da marca.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| Descrição | Texto | "Foto de ambiente acolhedor" |
| Categoria | Seleção | campanha / institucional / produto / evento / geral |
| Tags | Array | ['acolhedor', 'azul', 'profissional'] |
| Upload | Arquivo | JPG/PNG |
| URL S3 | Auto | Gerada após upload |
| Relacionado Campanha | FK | Opcional: vincular a projeto |
| Análise IA | JSON | Auto: IA extrai características |

**Sistema Anti-Repetição:**
- IA analisa cada imagem enviada
- Extrai: estilo, cores, elementos, composição, mood
- Calcula hash perceptual
- Ao gerar nova imagem, compara com referências já usadas
- Evita criar imagens muito similares

**Exemplo Análise IA:**
```json
{
  "estilo": "minimalista",
  "cores_predominantes": ["#6B2C91", "#FFFFFF", "#2196F3"],
  "elementos_visuais": ["pessoa sorrindo", "equipamento médico"],
  "composicao": "centralizada",
  "mood": "profissional e acolhedor",
  "hash_perceptual": "a1b2c3d4..."
}
```

---

### BLOCO 6: SITES E REDES SOCIAIS

**Objetivo:** Centralizar URLs e perfis das redes sociais.

#### 6.1 Site Institucional

| Campo | Tipo | Obrigatório |
|-------|------|-------------|
| URL | URL | ✅ |

```yaml
Site Institucional: "https://femme.com.br"
```

#### 6.2 Redes Sociais (Model SocialNetwork)

**Gerenciável via Admin Django** - Permite adicionar/remover redes sem código.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| Nome | Texto | Nome da rede |
| Tipo | Seleção | Instagram / Facebook / LinkedIn / YouTube / TikTok / Twitter / Outro |
| URL | URL | Link da página/perfil |
| Username | Texto | @username ou handle |
| Ativa | Boolean | Se está ativa (aparece nas opções) |
| Ordem | Número | Ordem de exibição |

**Exemplo:**
```yaml
Redes Sociais:
  - Tipo: Instagram
    URL: "https://instagram.com/femmediagnostico"
    Username: "@femmediagnostico"
    Ativa: true
  
  - Tipo: LinkedIn
    URL: "https://linkedin.com/company/femme"
    Username: "FEMME Diagnóstico"
    Ativa: true
  
  - Tipo: YouTube
    URL: "https://youtube.com/@femmesaude"
    Username: "@femmesaude"
    Ativa: true
  
  - Tipo: Facebook
    URL: "https://facebook.com/femmediagnostico"
    Username: "FEMME Diagnóstico"
    Ativa: false
```

**Templates por Rede (Model SocialNetworkTemplate):**

Também gerenciável via Admin:

| Campo | Tipo |
|-------|------|
| Rede Social | FK para SocialNetwork |
| Nome | "Feed 1:1", "Stories", "Carrossel" |
| Largura (px) | 1080 |
| Altura (px) | 1080 |
| Aspect Ratio | "1:1" |
| Limite Caracteres | 2200 (Instagram) |
| Limite Hashtags | 30 |
| Ativo | true/false |

**Benefício:** Adicionar nova rede ou template sem mexer em código!

---

### BLOCO 7: DADOS E INSIGHTS

**Objetivo:** Definir fontes de dados e integrações para insights.

#### 7.1 Fontes de Pesquisa (URLs Confiáveis)

Lista de URLs pré-aprovadas para pesquisa de pautas:

```yaml
Fontes de Pesquisa:
  - "https://www.saude.gov.br"
  - "https://portal.fiocruz.br"
  - "https://www.who.int/pt"
  - "https://drauziovarella.uol.com.br"
  - "https://www.sbpc.org.br"
```

**Uso:** Quando gerar pautas, sistema faz scraping dessas URLs primeiro.

#### 7.2 Canais de Monitoramento de Trends

Além das fontes pré-configuradas, permite adicionar customizadas:

```json
[
  {
    "nome": "Blog Saúde em Foco",
    "tipo": "rss",
    "url": "https://saudeemfoco.com.br/feed",
    "ativo": true
  },
  {
    "nome": "Canal Saúde & Ciência",
    "tipo": "youtube",
    "channel_id": "UCxxxxxxxxxxxxx",
    "ativo": true
  },
  {
    "nome": "Portal de Notícias Médicas",
    "tipo": "scraping",
    "url": "https://noticiasmedicasbrasil.com.br",
    "ativo": true
  }
]
```

#### 7.3 Integração AWS Athena (Fase 2)

Conexão com banco de dados analítico:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| Habilitado | Boolean | Se integração está ativa |
| Endpoint | URL | Endpoint do Athena |
| Database | Texto | Nome do database |
| Credenciais | JSON (encriptado) | Access key, secret key, region |

**Queries Pré-Definidas:**
```json
[
  {
    "nome": "Top 10 Exames do Mês",
    "sql": "SELECT exame, COUNT(*) as total FROM exames WHERE mes = :mes GROUP BY exame ORDER BY total DESC LIMIT 10",
    "descricao": "Exames mais realizados no mês",
    "parametros": ["mes"]
  },
  {
    "nome": "Exames em Declínio",
    "sql": "SELECT exame, COUNT(*) as total FROM exames WHERE mes = :mes GROUP BY exame HAVING total < (SELECT AVG(total) FROM ...)",
    "descricao": "Exames com queda de demanda",
    "parametros": ["mes"]
  }
]
```

**Regras de Interpretação:**
```yaml
Regras de Interpretação: |
  - Exames em declínio: Criar campanha educativa sobre importância
  - Picos em horários específicos: Sugerir agendamento em horários alternativos
  - Perfil demográfico: Segmentar campanhas por faixa etária
```

---

## 🎨 INTERFACE DE EDIÇÃO

### Layout Sanfona (Accordion)

```
┌─────────────────────────────────────────────────┐
│  📚 Base de Conhecimento FEMME                  │
│                                                  │
│  Status: ██████████░░ 85% Completo              │
│  Última atualização: 10/01/2026 por João Silva  │
│                                                  │
├─────────────────────────────────────────────────┤
│                                                  │
│  ▼ 1. Identidade Institucional         ✅ 100% │
│    ┌──────────────────────────────────────────┐ │
│    │ Nome da Empresa: [FEMME - Diagnóstico..] │ │
│    │ Descrição: [Centro de diagnóstico que..]│ │
│    │ ...                                      │ │
│    │ [ Salvar Bloco 1 ]                       │ │
│    └──────────────────────────────────────────┘ │
│                                                  │
│  ▼ 2. Público e Segmentos              ✅ 100% │
│    (expandir para editar)                       │
│                                                  │
│  ▼ 3. Posicionamento e Diferenciais    ⚠️  70% │
│    (falta adicionar concorrentes)               │
│                                                  │
│  ▼ 4. Tom de Voz                       ✅ 100% │
│                                                  │
│  ▼ 5. Identidade Visual                ⚠️  60% │
│    (falta adicionar imagens referência)         │
│                                                  │
│  ▼ 6. Sites e Redes Sociais            ✅ 100% │
│                                                  │
│  ▼ 7. Dados e Insights                 ❌  20% │
│    (configuração pendente)                      │
│                                                  │
│  [ Salvar Tudo ] [ Cancelar ] [ Visualizar ]   │
└─────────────────────────────────────────────────┘
```

### Funcionalidades

- **Salvamento Individual:** Botão em cada bloco
- **Salvamento Geral:** Salva todos os blocos de uma vez
- **Indicador Visual:** ✅ Completo / ⚠️ Parcial / ❌ Vazio
- **Percentual Global:** Barra de progresso
- **Validação:** Campos obrigatórios destacados em vermelho
- **Preview:** Visualizar como IA "vê" a base

---

## 📊 HISTÓRICO DE ALTERAÇÕES

Toda alteração é registrada no model `ChangeLog`:

```
┌─────────────────────────────────────────────────┐
│  📜 Histórico de Alterações                     │
├─────────────────────────────────────────────────┤
│                                                  │
│  12/01/2026 15:30 - João Silva (Gestor)        │
│  Bloco: Tom de Voz                              │
│  Campo: palavras_recomendadas                   │
│  Anterior: [..., "qualidade"]                   │
│  Novo: [..., "qualidade", "excelência"]        │
│                                                  │
│  10/01/2026 10:15 - Maria Santos (Admin)       │
│  Bloco: Identidade Visual                      │
│  Ação: Upload de nova imagem de referência     │
│                                                  │
│  ...                                             │
└─────────────────────────────────────────────────┘
```

---

## 🔍 COMO A IA USA A BASE

### 1. Geração de Pautas
```python
# Busca da base
base = KnowledgeBase.objects.first()

# Monta contexto
contexto = f"""
Identidade: {base.nome_empresa} - {base.missao}
Público: {base.publico_alvo_externo}
Tom: {base.tom_voz_externo}
Palavras usar: {', '.join(base.palavras_recomendadas)}
Palavras evitar: {', '.join(base.palavras_evitar)}
"""

# Prompt para IA
prompt = f"""
{contexto}

Gere 10 pautas sobre: {tema}
Para público: {publico}
Objetivo: {objetivo}
"""
```

### 2. Geração de Imagens
```python
# Busca cores
cores = base.cores.all()
cores_hex = [cor.hex_code for cor in cores]

# Busca imagens referência (menos usadas)
refs = base.imagens_referencia.order_by('vezes_usada_como_referencia')[:3]

# Monta prompt
prompt_imagem = f"""
Style: {refs[0].analise_ia['estilo']}
Colors: {', '.join(cores_hex)}
Mood: {refs[0].analise_ia['mood']}
Subject: {tema}
"""
```

### 3. Análise de Concorrentes
```python
# Scraping semanal
for concorrente in Competitor.objects.filter(scraping_ativo=True):
    conteudo = scrape_site(concorrente.url)
    analise = ia_analisa(conteudo, base_femme=base)
    
    concorrente.analise_posicionamento = analise['posicionamento']
    concorrente.analise_diferenciais = analise['diferenciais']
    concorrente.analise_tom_voz = analise['tom_voz']
    concorrente.save()
```

---

## ✅ CHECKLIST DE COMPLETUDE

Para Base considerada **completa (100%)**:

- [x] Bloco 1: Todos campos preenchidos
- [x] Bloco 2: Público externo E interno definidos
- [x] Bloco 3: Posicionamento + mín. 3 diferenciais + mín. 2 concorrentes
- [x] Bloco 4: Tom externo E interno + mín. 5 palavras recomendadas
- [x] Bloco 5: Mín. 2 cores + 1 fonte + logotipo + mín. 3 imagens referência
- [x] Bloco 6: Site + mín. 2 redes sociais ativas
- [x] Bloco 7: Mín. 3 fontes de pesquisa

**Mínimo para usar sistema (70%):**
- Blocos 1, 2, 4 completos
- Bloco 3 com posicionamento
- Bloco 5 com mín. 2 cores

---

**Próximo documento:** [06_IAMKT_Usuarios_Permissoes.md](06_IAMKT_Usuarios_Permissoes.md)
