---
name: todxs-social-posts
description: >-
  Gera posts de redes sociais da marca TODXS (ONG LGBTQIA+) — do conteúdo à ARTE
  FINAL com texto embutido. Produz a copy no tom da marca e um PROMPT de geração de
  imagem single-shot, agnóstico (funciona em Gemini/Nano Banana e GPT Image), com
  cores, tipografia, grafismo do "X" e tratamento fotográfico da identidade visual.
  Use SEMPRE que a pessoa pedir post, arte, criativo, story, feed, carrossel,
  card, peça ou campanha "da TODXS" / "pra TODXS" / "no estilo TODXS", ou quando
  ela colar um tema/pauta e pedir a arte final para postar — mesmo sem dizer
  "prompt" ou "imagem" explicitamente. Cobre feed 1:1, story 9:16 e carrossel.
---

# Gerador de posts TODXS

Transforma um tema/briefing em **(1) conteúdo travado no tom da marca** e **(2) um
prompt de imagem single-shot** que gera a **arte final já com o texto aplicado** —
pronta para postar. O prompt é **agnóstico**: serve para Gemini (Nano Banana) e GPT
Image. A pessoa escolhe o **formato** (feed 1:1, story 9:16 ou carrossel) na hora.

A TODXS é uma ONG de empoderamento da comunidade LGBTI+/LGBTQIA+, com estética
**editorial** (releitura do *Lampião da Esquina*): tipografia protagonista, cores da
bandeira LGBTQIA+ e o "X" como elemento central.

## Arquivos de referência (leia conforme a etapa)
- `references/brand-spec.md` — cores (hex/rgb/cmyk/pantone), tipografia, grafismo do
  "X", foto, don'ts. **Leia antes de montar o prompt visual.**
- `references/tone-of-voice.md` — voz, vocabulário, pilares de conteúdo, padrões de
  manchete. **Leia no Content Lock.**
- `references/prompt-templates.md` — regras do single-shot e **6 arquétipos de layout**
  prontos. **Leia na seleção de layout e na construção do prompt.**

---

## Fluxo de trabalho

A lógica é **Content Lock → Visual Lock → prompt**: trave o que vai ser dito antes de
desenhar onde fica. Isso evita prompt bonito com texto vazio.

### 0. Entender o briefing
Capte: **tema/pauta**, **pilar** (Notícia, Educativo/Cuidado, Impacto, História),
**objetivo** e **formato**. Se a pessoa não disse o formato, **pergunte** (feed 1:1 /
story 9:16 / carrossel) — é a escolha dela. Se o briefing estiver vago demais para
travar uma manchete (ex.: "faz um post sobre diversidade"), **pare e faça 1–2 perguntas
objetivas** (qual ângulo? tem dado/foto? é pauta ou institucional?) antes de seguir.
Não invente fatos nem números — use só o que for fornecido (ver regra de dados em
`tone-of-voice.md`).

### 1. CONTENT LOCK — travar o texto
Lendo `tone-of-voice.md`, defina e **fixe as strings exatas**:
- **eyebrow/label** (ex.: `NOTÍCIA`, `IMPACTO E DIVERSIDADE`),
- **manchete** em CAIXA ALTA, curta e com peso (**≤ 6–8 palavras** — texto longo
  renderiza com erro no single-shot),
- **corpo/subtítulo** curto, só se o arquétipo pedir,
- **footer/assinatura** (ex.: `TODXS`).

Mostre esse bloco travado para a pessoa. Esse é o texto que vai **literalmente** para
dentro da imagem — capriche na ortografia e acentuação.

### 2. VISUAL LOCK — escolher layout e cor
Lendo `prompt-templates.md`, escolha:
- **Arquétipo** pelo pilar/conteúdo (menu abaixo).
- **Cor de destaque** da paleta (uma só + preto + off-white). Em série/carrossel,
  **alterne a cor** a cada peça — a marca quer protagonismo compartilhado, nunca uma
  "cor dominante" e **nunca gradiente nem fundo branco puro**.
- **Tratamento de foto** se houver (colorida / P&B / duotone multiply numa cor da paleta).

Menu de arquétipos (detalhe e template completo em `prompt-templates.md`):
- **A** Manchete sobre cor chapada — pauta/frase de impacto, sem foto.
- **B** Foto duotone full-bleed + manchete — tema-reflexão, campanha.
- **C** Retrato editorial + grafismo ondulado — apresentar uma pessoa/voz.
- **D** Split foto em cima / bloco de cor + texto — impacto com 1 parágrafo.
- **E** Tipográfico puro empilhado — manifesto, eixos, lista.
- **F** Capa de story duotone com wordmark — abertura de série/campanha (9:16).

Diga em 1 linha **por que** esse arquétipo e essa cor servem ao conteúdo.

### 3. Construir o PROMPT (single-shot, agnóstico)
Preencha o template do arquétipo com as strings travadas, seguindo as **Regras de ouro
do single-shot** de `prompt-templates.md`: strings exatas entre aspas, instrução de
português com acentos, **zonas de texto** (wireframe), descrição do **estilo** da
tipografia (as fontes Ana Banana/Vinila não existem no modelo), paleta restrita e
**negativos**. Respeite o **orçamento de texto** do formato.

Para **carrossel**: gere um prompt por slide — capa num arquétipo de manchete e cada
slide interno com **uma ideia**, alternando a cor.

### 4. Entregar
Responda com, nesta ordem:
1. **Conteúdo travado** (eyebrow / manchete / corpo / footer).
2. **Layout + cor escolhidos** e o porquê (1 linha).
3. **PROMPT final** num bloco de código copiável (um por peça/slide), pronto para colar
   no Gemini ou no GPT Image.
4. **Notas**: ratio do formato + **dica de verificação** (conferir o texto renderizado;
   se algum acento sair errado, regenerar enfatizando a palavra ou corrigir por edição;
   se for corpo longo demais, migrar a peça para o fluxo de compositing com Pillow).

---

## Princípios que não se quebram
- **Português com acento, string exata.** O texto da arte é citado, não parafraseado.
- **Uma cor + preto + off-white.** Sem gradiente, sem branco puro de fundo, sem cor
  fora da paleta, sem mexer na hierarquia (ver `brand-spec.md`).
- **Tipografia é protagonista.** Manchete pesada em caixa alta domina a peça.
- **Representatividade real.** Fotos de pessoas LGBTQIA+ diversas, plano americano/retrato.
- **O "X" é da marca.** Selo, máscara ou blob; grafismo solto gira em 45°, mas o
  logotipo nunca é rotacionado nem distorcido.
- **Single-shot tem limite de texto.** Quando o texto for muito ou a fidelidade
  tipográfica for crítica, o caminho certo é o compositing (fundo gerado + texto via
  Pillow), não espremer tudo no prompt.
