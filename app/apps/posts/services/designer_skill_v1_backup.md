# SKILL DE DESIGNER SENIOR — princípios e padrões para revisão de layout

Este documento e carregado pelo designer-critic como referencia ativa.
Cada principio tem:
- **PRINCIPIO**: a regra de design (vinda do canon — Gestalt, hierarquia, tipografia).
- **SINTOMA**: como ele aparece como problema visual.
- **EDIT TIPICO**: a operacao cirurgica que corrige.

Use isto como REPERTORIO. Aplique olho — nao receita.

---

## 1. PROXIMIDADE TIPOGRAFICA (Gestalt)

**Principio**: elementos relacionados ficam visualmente PROXIMOS. Titulo +
subtitulo formam um GRUPO — o gap vertical entre eles deve ser MENOR que
o gap ate qualquer outro elemento fora do grupo.

Regra pratica: o gap entre o FIM do titulo e o INICIO do subtitulo deve ser
PEQUENO (1-3% do canvas). Se o titulo ocupa `y=20` a `y=50` (altura 30%),
o subtitulo deve comecar em `y ≈ 51-53%`, NAO em `y=60%` ou mais.

**SINTOMA**: blocos parecem flutuar isolados, sem agrupamento visual. O olho
nao "le" titulo+subtitulo como um conjunto.

**EDIT TIPICO**:
```json
{"target_role": "subtitulo", "field": "y_pct", "new_value": 51,
 "reason": "Aproximar do titulo (proximidade tipografica). Titulo termina em y=50, subtitulo comecava em y=53 — agora em y=51 cria grupo visual."}
```

---

## 2. CENTRALIZAR TEXTO DENTRO DE BOTAO/PILL (alinhamento vertical)

**Principio**: o Pillow renderiza texto alinhado ao TOPO da caixa declarada.
Quando ha um grafismo de fundo (pill, faixa, selo) e o texto cai POR CIMA,
o texto NAO fica visualmente centralizado se ele usar o mesmo `y_pct` do
grafismo.

Calculo correto para centralizacao vertical do texto dentro do grafismo:

```
altura_texto_renderizada ≈ font_size_pct × 1.18 × num_linhas
offset_vertical = (grafismo.height_pct − altura_texto_renderizada) / 2
texto.y_pct = grafismo.y_pct + offset_vertical
```

Para um CTA com 1 linha e `fs=2.8` num pill `h=10`: offset ≈ (10 − 3.3) / 2 ≈ 3.3.
Logo `cta.y_pct = grafismo.y_pct + 3.3`.

**SINTOMA**: texto encostado no TOPO do grafismo (mais visivel), ou
encostado no FUNDO. Falta de "respiro" interno do botao.

**EDIT TIPICO**:
```json
{"target_role": "cta", "field": "y_pct", "new_value": 77.3,
 "reason": "Centralizar verticalmente no pill (grafismo y=74, h=10; texto fs=2.8 ≈ 3.3% altura; offset = (10-3.3)/2 = 3.3 → y=77.3)."}
```

---

## 3. RESPIRO DAS BORDAS (logo, textos, tudo)

**Principio**: elementos nao colam nas bordas do canvas. Mesmo "bottom-right"
significa "no quadrante inferior-direito COM margem", nao "encostado na
borda inferior-direita".

Margens minimas (em % do canvas):

| Elemento | Margem inferior | Margem superior | Margem lateral |
|---|---|---|---|
| Texto | ≥ 4% antes da borda inferior | ≥ 4% topo | ≥ 4% laterais |
| Logo | ≥ 6-8% antes da borda inferior (logo pequeno colado parece erro) | — | ≥ 4% lateral |
| Grafismos primitivos (faixa/linha) | OK encostar se for design intencional (full-width) | — | OK encostar |

Para logo `bottom-right`: `y_pct` tipico em **82-86%**, NAO `90%`+ (fica
colado). Para logo `bottom-center`/`bottom-left`: mesma regra.

**SINTOMA**: logo parece estar caindo do canvas, sem respiro. Texto encosta
na borda como se tivesse sido cortado.

**EDIT TIPICO**:
```json
{"target_role": "logo", "field": "y_pct", "new_value": 84,
 "reason": "Respiro inferior. y=90 + altura ~8% = 98% — colado na borda. y=84 deixa ~8% de respiro abaixo do logo."}
```

---

## 4. CONTRASTE DE TEXTO SOBRE FOTOGRAFIA MOVIMENTADA

**Principio**: texto branco/claro so funciona sobre fundo UNIFORMEMENTE
escuro. Sobre cena fotografica movimentada (rostos, ingredientes, texturas
mistas), partes do texto "somem" — algumas letras caem sobre regioes claras,
outras sobre escuras.

Solucoes em ordem de preferencia:
1. **Faixa/pill de fundo** sob o texto (cor solida + texto contrastante).
2. **Cor do texto que contrasta com o conteudo majoritario** da regiao
   (geralmente grafite `#23282A` se fundo claro-medio; branco `#FFFFFF` se
   escuro homogeneo).
3. **Reposicionar** o texto para area mais calma da cena.

NUNCA aprove texto branco sobre cena fotografica movimentada sem um destes.

**SINTOMA**: parte do texto le bem, parte some. Mesma frase com legibilidade
desigual ao longo da extensao.

**EDIT TIPICO**:
```json
{"target_role": "subtitulo", "field": "color", "new_value": "#23282A",
 "reason": "Branco sobre cena clara/movimentada (cozinha + casal) perde legibilidade. Grafite garante leitura uniforme."}
```

---

## 5. HIERARQUIA POR TAMANHO E PESO

**Principio**: titulo > subtitulo > CTA em font_size E em peso visual.

Tamanhos tipicos (% da menor dimensao do canvas):
- Titulo: 5-12% (forte), bold/extrabold
- Subtitulo: 50-65% do titulo, regular ou medium
- CTA: 50-60% do titulo, bold (impulso de acao)

Inversao = catastrofe visual. Subtitulo nao pode parecer maior que titulo.

**SINTOMA**: olho vai pro subtitulo primeiro. CTA "some" ou parece informacao
secundaria.

**EDIT TIPICO**:
```json
{"target_role": "subtitulo", "field": "font_size_pct", "new_value": 3.5,
 "reason": "Subtitulo estava 60% do titulo (proporcao OK), mas em cenas movimentadas precisa de pouco mais — 65% melhora leitura mantendo hierarquia."}
```

---

## 6. CONSISTENCIA DE COLUNA / ALINHAMENTO

**Principio**: textos do mesmo grupo (titulo, subtitulo, CTA) tendem a
compartilhar o mesmo `x_pct` para criar uma coluna visual consistente.

Variar `x_pct` entre blocos pode ser intencional (deslocamento dramatico,
indentacao para chamar atencao) mas precisa ter MOTIVO. Por padrao:
`x_pct` igual em titulo, subtitulo, cta.

**SINTOMA**: blocos "escapam" da coluna — ex: subtitulo em x=4, mas cta em x=6.

**EDIT TIPICO**:
```json
{"target_role": "cta", "field": "x_pct", "new_value": 4,
 "reason": "Alinhar a coluna esquerda dos outros textos (consistencia visual)."}
```

---

## 7. FORMA DO CTA — pill, faixa, selo

**Principio**: a forma do grafismo do CTA TRANSMITE o tipo de acao.

| Forma | Uso | Quando |
|---|---|---|
| **Pill (retangulo arredondado)** | Botao de acao principal | "Clique aqui", "Compre agora", "Inscreva-se" |
| **Faixa retangular (full-width)** | Rodape, brand bar, banner | Faixa de marca, callout horizontal |
| **Selo circular** | BADGE, destaque pontual | "NOVO", "10% OFF", "EXCLUSIVO" — NAO para CTA principal |
| **Faixa organica** | Template editorial especifico | So se a marca tem esse padrao na ref |

Selo circular para CTA principal (ex: "APROVEITE A OFERTA EXCLUSIVA") = erro
de forma. Pill arredondado e a forma canonica para botao.

**SINTOMA**: CTA com forma que nao bate com a acao. Circulo grande competindo
visualmente com o sujeito.

**EDIT TIPICO**:
```json
{"target_role": "grafismo", "target_index": 2, "field": "forma", "new_value": "faixa",
 "reason": "CTA chamada de acao requer pill retangular arredondado, nao selo circular."}
```
(Se houver `raio_pct`, ajustar tambem.)

---

## 8. EQUILIBRIO VISUAL DE PESO

**Principio**: peso visual nao concentrado num so lado. Sujeito (produto/
pessoa) num lado, texto+CTA no outro — sem brigar pelo foco.

Olhos lem em "Z" (cultura ocidental): topo-esquerda → topo-direita →
fundo-esquerda → fundo-direita. Coloque o ponto de impacto (titulo, CTA)
em pontos fortes desse traco.

**SINTOMA**: composicao "pesada" de um lado, vazia do outro. Sensacao de
desequilibrio.

**EDIT TIPICO**:
- Considere mover ou reduzir o sujeito, ou aumentar a presenca do texto.
- Para post 16:9: texto coluna esquerda ~35-45%, sujeito coluna direita
  ~50-60%.

---

## 9. NAO APROVE SO PORQUE "QUASE FUNCIONA"

**Principio**: voce e designer SENIOR. Voce nao aprova layouts mediocres.
Se ha problemas visiveis (texto solto, CTA mal centrado, logo colado),
proponha edits — mesmo que tenham passado por iteracoes anteriores.

Aprovar prematuro = ratificar mediocridade. Iteracao adicional custa $0.05;
post mediocre custa credibilidade da marca.

**SINTOMA**: voce esta na iteracao 3 e ainda ve problemas mas pensou em
aprovar porque "ja iteramos demais". NAO. Aprove SO se esta REALMENTE bom.
