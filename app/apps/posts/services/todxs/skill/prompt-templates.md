# TODXS — Templates de prompt (single-shot, agnóstico)

Geramos a **arte final com o texto já embutido**, num único prompt que funciona
tanto no **Gemini (Nano Banana / Gemini 2.5 Flash Image)** quanto no **GPT Image**.
Ambos aceitam prompt em prosa. As regras abaixo valem para os dois; onde há
diferença, está sinalizado.

---

## Regras de ouro do single-shot com texto

O ponto frágil dos dois modelos é **renderizar texto** — pioram com texto longo,
fonte pequena, muitos blocos e acentos. Por isso:

1. **Escreva a string EXATA entre aspas retas.** Ex.: a manchete é exatamente
   `"AMPLITUDE NOS PROJETOS SOCIAIS"`. Não descreva o texto — cite-o.
2. **Português do Brasil, acentos preservados.** Inclua sempre a instrução:
   *"All visible text is in Brazilian Portuguese, spelled exactly as written,
   preserving every accent (á é í ó ú â ê ô ã õ ç) and punctuation."*
3. **Respeite o orçamento de texto por formato** (abaixo). Menos texto = menos erro.
4. **Wireframe primeiro: declare as zonas de texto.** Diga onde cada bloco fica
   (ex.: "eyebrow no topo-esquerdo; manchete ocupando a metade inferior").
   Isso evita sobreposição e mantém a hierarquia.
5. **Uma cor de destaque + preto + off-white.** Sem gradiente. Sem fundo branco puro.
6. **Descreva o estilo da tipografia** (as fontes reais não existem no modelo — ver
   seção própria abaixo).
7. **Feche com negativos:** *"No gradients, no pure white background, no extra logos,
   no watermark, no lorem ipsum, no misspelled or garbled text, no colors outside
   the brand palette."*
8. **Verificação (loop):** depois de gerar, leia o texto renderizado. Se algum acento
   ou palavra saiu errado, regenere enfatizando a palavra problemática entre aspas,
   ou corrija por edição/inpainting. Se o texto for muito (corpo longo), considere
   migrar aquela peça para o fluxo de compositing (Pillow).

### Orçamento de texto (mire nisto)
| Formato | Ratio | Texto renderizável recomendado |
|---------|-------|--------------------------------|
| Feed | 1:1 (1080×1080) | 1 eyebrow (≤4 palavras) + 1 manchete (≤8 palavras) + footer opcional (≤4 palavras) |
| Story | 9:16 (1080×1920) | eyebrow + manchete + **ou** 1 bloco curto de corpo (≤25 palavras), não os dois cheios |
| Carrossel | 1:1 por slide | **Capa** = como feed. **Slides internos** = 1 ideia por slide (manchete curta + ≤30 palavras de apoio) |

### Descrevendo a tipografia sem a fonte
- **Manchete (papel da Ana Banana Black):** *"heavy grotesque display sans-serif,
  very bold, tight spacing, with deep ink-traps, flared bell-mouth terminals and
  rounded 'smiling' counters; editorial poster feel"*.
- **Corpo/subtítulo (papel da Vinila):** *"clean contemporary grotesque sans-serif,
  regular or condensed width, high legibility"*.
- Caixa **ALTA** em manchetes, eyebrows e selos.

---

## Como montar um prompt

Preencha esta espinha e ajuste pelos arquétipos:

```
[FORMATO/RATIO] editorial social media [post/story] for TODXS, a Brazilian
LGBTQIA+ NGO. Bold editorial poster style inspired by 1970s queer print press.

BACKGROUND: [cor chapada da paleta | foto duotone | foto + bloco de cor].
[se foto] PHOTO: [pessoa LGBTQIA+ diversa, plano americano/retrato, contexto],
treatment [color | black-and-white | black-and-white with a flat {{COR}} multiply
duotone].
GRAPHIC: [selo X preto com X em {{COR}} no topo | máscara/blob em forma de X,
rotacionado em múltiplos de 45° | nenhum].

TEXT ZONES (render exactly, do not paraphrase):
- eyebrow [posição]: "[STRING]"  — small condensed grotesque caps.
- headline [posição]: "[STRING]" — heavy grotesque display caps, dominant.
- [body/footer se houver] [posição]: "[STRING]" — clean grotesque.

All visible text in Brazilian Portuguese, spelled exactly as written, preserving
accents (á é í ó ú â ê ô ã õ ç). Palette: only {{COR}} + black #000000 + off-white
#F4F1D9.
AVOID: gradients, pure white background, extra logos, watermark, lorem ipsum,
garbled or misspelled text, any color outside the brand palette.
```

> Sempre devolva a string final **em inglês para a estrutura** mas com **o texto
> visível em português** entre aspas — os dois modelos seguem melhor instruções
> estruturais em inglês e renderizam o conteúdo citado como está.

---

## Arquétipos de layout

Escolha pelo pilar/objetivo. Cada um tem um exemplo preenchido — copie e troque
os `{{ }}`.

### A — Manchete sobre cor chapada
Fundo cor chapada, manchete gigante em preto, sem foto (ou com inset pequeno).
Bom para: pauta forte, frase de impacto, educativo sem imagem.
```
1:1 (1080x1080) editorial social post for TODXS, a Brazilian LGBTQIA+ NGO,
bold 1970s-queer-press poster style.
BACKGROUND: solid {{COR}} field, no gradient.
GRAPHIC: small black circular seal with a four-petal "X" mark in {{COR2}} at top-left.
TEXT ZONES (render exactly):
- eyebrow top-left: "{{EYEBROW}}" — small condensed grotesque, black, caps.
- headline center, occupying ~55% of canvas: "{{MANCHETE}}" — very heavy grotesque
  display sans, black, caps, tight, with ink-traps and rounded smiling counters.
- footer bottom-left: "{{FOOTER}}" — small condensed grotesque, black, caps.
All text in Brazilian Portuguese, exact spelling with accents. Palette: {{COR}} +
black #000000 + off-white #F4F1D9 only.
AVOID: gradients, white background, extra logos, watermark, garbled text, off-palette colors.
```

### B — Foto duotone full-bleed + manchete
Foto cobre tudo, com duotone numa cor da paleta; manchete em off-white embaixo.
Bom para: tema-reflexão, campanha, retrato com pauta.
```
1:1 (1080x1080) editorial social post for TODXS (Brazilian LGBTQIA+ NGO),
1970s queer-press poster style.
BACKGROUND: full-bleed photo of {{PESSOA: pessoa LGBTQIA+ diversa, ex. idosa trans}},
{{CONTEXTO}}, american/medium shot, expressive. Treatment: black-and-white with a
flat {{COR}} multiply duotone over the whole image.
GRAPHIC: small black-and-{{COR}} four-petal "X" seal at top-right.
TEXT ZONES (render exactly):
- eyebrow top-left: "{{EYEBROW}}" — condensed grotesque, off-white, caps.
- headline lower third: "{{MANCHETE}}" — heavy grotesque display, off-white #F4F1D9,
  caps, dominant.
All text Brazilian Portuguese, exact accents. Palette: {{COR}} + black + off-white only.
AVOID: gradients, white bg, extra logos, watermark, garbled text, off-palette colors.
```

### C — Retrato editorial + grafismo ondulado
Retrato (P&B ou cor) com o lettering `TODXS` no topo e um grafismo/onda da paleta
atrás; pouco texto. Bom para: apresentar uma pessoa/voz da comunidade.
```
1:1 (1080x1080) editorial portrait post for TODXS (Brazilian LGBTQIA+ NGO).
BACKGROUND: off-white #F4F1D9 field. Black-and-white american-shot portrait of
{{PESSOA}} placed right, with a {{COR}} wavy organic X-derived graphic shape sweeping
behind the subject (rotated in 45° increments).
TEXT ZONES (render exactly):
- wordmark top-left: "TODXS" — heavy grotesque caps, black, with a stylized four-petal
  "X" as the 4th letter.
- eyebrow under wordmark: "{{EYEBROW}}" — small condensed grotesque, black, caps.
All text Brazilian Portuguese, exact accents. Palette: {{COR}} + black + off-white only.
AVOID: gradients, white-as-pure-white, extra logos, watermark, garbled text.
```

### D — Split: foto em cima / bloco de cor + texto embaixo
Metade superior foto colorida; metade inferior bloco de cor chapada com manchete +
corpo curto + assinatura. Bom para: impacto/institucional com 1 parágrafo.
```
1:1 (1080x1080) editorial social post for TODXS (Brazilian LGBTQIA+ NGO).
LAYOUT: top half = color american-shot photo of {{PESSOA}}, {{CONTEXTO}}.
Bottom half = solid {{COR}} block.
GRAPHIC: small black-and-{{COR}} four-petal "X" seal at top-left over the photo.
TEXT ZONES (render exactly), all inside the bottom {{COR}} block:
- headline: "{{MANCHETE}}" — heavy grotesque display, black, caps, dominant.
- body: "{{CORPO ≤30 palavras}}" — clean grotesque, black, small.
- footer-left: "{{EYEBROW}}"  + footer-right wordmark "TODXS" — condensed caps, black.
All text Brazilian Portuguese, exact accents. Palette: {{COR}} + black + off-white only.
AVOID: gradients, white bg, extra logos, watermark, lorem ipsum, garbled text.
```

### E — Tipográfico puro (lista/manifesto)
Cor chapada, várias chamadas empilhadas em preto, sem foto. Bom para: eixos de um
projeto, manifesto, tópicos.
```
1:1 (1080x1080) typographic editorial post for TODXS (Brazilian LGBTQIA+ NGO).
BACKGROUND: solid {{COR}} field.
GRAPHIC: black circular seal with a four-petal "X" in off-white at top-left.
TEXT ZONES (render exactly), stacked, left-aligned, generous size:
- "{{LINHA 1}}"
- "{{LINHA 2}}"
- "{{LINHA 3}}"
all in heavy grotesque display sans, black, caps, with clear spacing between blocks.
- footer-left: "{{EYEBROW}}" — small condensed caps, black.
All text Brazilian Portuguese, exact accents. Palette: {{COR}} + black + off-white only.
AVOID: gradients, white bg, extra logos, watermark, garbled text, off-palette colors.
```

### F — Capa de story duotone com wordmark
Story full-bleed duotone, lettering `TODXS` central, blobs do X. Bom para: capa de
story/série, abertura de campanha.
```
9:16 (1080x1920) editorial story cover for TODXS (Brazilian LGBTQIA+ NGO).
BACKGROUND: full-bleed black-and-white photo of {{PESSOA}} with a flat {{COR}}
multiply duotone. Large {{COR}} organic X-petal blob shapes overlapping the edges,
rotated in 45° increments.
TEXT ZONES (render exactly):
- wordmark centered: "TODXS" — heavy grotesque caps with a four-petal "X", off-white.
- small X seal top-left.
{{se houver eyebrow}}: "{{EYEBROW}}" top, condensed caps, off-white.
All text Brazilian Portuguese, exact accents. Palette: {{COR}} + black + off-white only.
AVOID: gradients, white bg, extra logos, watermark, garbled text, off-palette colors.
```

---

## Variação 9:16 e carrossel
- **Story (9:16):** pegue o arquétipo e troque o ratio para `9:16 (1080x1920)`,
  empurrando manchete para o terço inferior e dando mais respiro vertical.
- **Carrossel:** capa num arquétipo de manchete (A/B/D); cada slide interno = **uma
  ideia** num arquétivo simples (A ou E), **alternando a cor de destaque** a cada
  slide para criar ritmo. Numere mentalmente, mas só renderize número se pedirem.

## Rotação de cor
Não repita a mesma cor de destaque em posts seguidos sem motivo — a marca quer
**protagonismo compartilhado**. Ao gerar uma série, percorra a paleta.
