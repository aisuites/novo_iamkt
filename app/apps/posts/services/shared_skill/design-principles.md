# Princípios de Design — Base Compartilhada

Princípios fundamentais aplicados tanto pelo agente designer (na criação) quanto
pelo crítico (na revisão). Quem cria os usa para planejar; quem revisa os usa
para diagnosticar.

---

## 1. Hierarquia visual

O olho do leitor segue uma hierarquia de impacto. Sem hierarquia clara, o leitor
não sabe **por onde começar**.

### Regra de ouro
```
título > subtítulo > corpo > CTA  (em tamanho/peso visual)
```

NUNCA inverter. Subtítulo igual ou maior que título = catástrofe visual.

### Em font_size_pct (proporcional à menor dim do canvas)
- Título: **5–14%** (forte; varia por formato — ver `typography-scale.md`)
- Subtítulo: **45–65%** do tamanho do título (regular ou medium)
- Corpo: **30–50%** do tamanho do título
- CTA: **50–60%** do tamanho do título (bold; impulso de ação)

### Em peso visual
- Título: bold/extrabold
- Subtítulo: regular ou medium
- CTA: bold (mesmo se menor — peso vence)

### Sintomas de hierarquia quebrada
- Olho vai para subtítulo antes do título
- CTA "some" no layout
- Tudo parece ter o mesmo peso (peça monótona)

---

## 2. Proximidade tipográfica (Gestalt)

Elementos relacionados ficam visualmente PRÓXIMOS. Título + subtítulo formam
um GRUPO — o gap entre eles deve ser MENOR que o gap até qualquer outro
elemento fora do grupo.

### Regra prática
O gap vertical entre o FIM do título e o INÍCIO do subtítulo deve ser
**1–3% do canvas**. Se o título termina em `y=50%`, o subtítulo começa em
`y ≈ 51–53%`, NÃO em `y=60%`.

### Sintoma
Blocos parecem flutuar isolados, sem agrupamento visual. O olho não "lê"
título+subtítulo como conjunto.

### Edit típico
```json
{"target_role": "subtitulo", "field": "y_pct", "new_value": 51,
 "reason": "Proximidade tipográfica — título termina em y=50%, subtítulo movido pra y=51% cria grupo visual."}
```

---

## 3. Alinhamento e consistência de coluna

Textos do mesmo grupo (título, subtítulo, CTA) tendem a compartilhar o mesmo
`x_pct` para criar coluna visual consistente.

Variar `x_pct` entre blocos pode ser intencional (deslocamento dramático,
indentação para chamar atenção) mas precisa ter MOTIVO. Por padrão: `x_pct`
igual em título, subtítulo, CTA.

### Sintoma
Blocos "escapam" da coluna — ex: subtítulo em x=4%, mas CTA em x=6%.

### Edit típico
```json
{"target_role": "cta", "field": "x_pct", "new_value": 4,
 "reason": "Alinhar à coluna esquerda dos outros textos (consistência visual)."}
```

---

## 4. Centralização de texto em botão/pill (alinhamento vertical)

Quando texto cai SOBRE um grafismo (pill, faixa, selo), o texto NÃO fica
visualmente centralizado se ele usar o mesmo `y_pct` do grafismo. O Pillow
renderiza texto alinhado ao TOPO da caixa declarada.

### Cálculo
```
altura_texto_renderizada ≈ font_size_pct × 1.18 × num_linhas
offset_vertical = (grafismo.height_pct − altura_texto_renderizada) / 2
texto.y_pct = grafismo.y_pct + offset_vertical
```

### Exemplo
CTA com 1 linha, `fs=2.8`, num pill `h=10`:
- altura texto ≈ 2.8 × 1.18 ≈ 3.3%
- offset ≈ (10 − 3.3) / 2 ≈ 3.4%
- Logo `cta.y_pct = grafismo.y_pct + 3.4`

### Sintoma
Texto encostado no topo do grafismo (mais visível), ou encostado no fundo.
Falta de "respiro" interno do botão.

---

## 5. Equilíbrio visual de peso

Peso visual não pode concentrar num só lado. Sujeito (produto/pessoa) num
lado, texto+CTA no outro — sem brigar pelo foco.

### Z-pattern (cultura ocidental)
Olhos lêem em "Z": topo-esquerda → topo-direita → fundo-esquerda → fundo-direita.
Coloque o ponto de impacto (título, CTA) em pontos fortes desse traço.

### Para 16:9
- Texto: coluna esquerda ~35–45%
- Sujeito: coluna direita ~50–60%

### Sintoma
Composição "pesada" de um lado, vazia do outro. Sensação de desequilíbrio.

---

## 6. Respiro / margens / espaço negativo

Elementos nunca colam nas bordas. Espaço negativo é parte do design — não é
"vazio" a ser preenchido.

Para margens específicas por elemento, ver `formats-and-safe-zones.md`.

### Princípio geral
Se a peça parece "cheia demais", reduza ou recue elementos. Se parece "vazia",
talvez precise de elemento secundário (não obrigatoriamente texto/cor).

---

## 7. Regra dos terços e pontos de tensão

Divida o canvas em uma grade 3×3. Os **4 pontos de cruzamento** das linhas
internas são pontos de máxima tensão visual.

Posicione elementos de maior importância (produto principal, face do sujeito,
título) em um desses pontos sempre que possível.

### Aplicação
- Produto principal num dos 4 pontos = olhar vai direto
- Texto pode ocupar 1 dos 4 terços (topo, baixo, esquerda, direita)
- Vazios estratégicos nos terços não ocupados = respiro

---

## 8. Forma do CTA — a forma comunica a ação

| Forma | Uso | Quando |
|---|---|---|
| **Pill (retângulo arredondado)** | Botão de ação principal | "Clique aqui", "Compre agora", "Inscreva-se" |
| **Faixa retangular full-width** | Rodapé, brand bar, banner contínuo | Faixa de marca, callout horizontal |
| **Selo circular** | BADGE, destaque pontual | "NOVO", "10% OFF", "EXCLUSIVO" — NÃO para CTA principal |
| **Faixa orgânica (curva)** | Template editorial específico | Apenas se a marca tem esse padrão em ref visual |

### Pill arredondado canônico
`raio_pct` deve ser **~50% da altura do grafismo** para criar pill verdadeiro.
Ex: `grafismo.height_pct=10` → `grafismo.raio_pct=5`.

### Sintoma
- Selo circular grande competindo com o sujeito principal
- "Pill" que parece retângulo (raio muito pequeno)
- CTA sem forma de fundo (texto solto), perdendo impacto

---

## 9. Contraste e legibilidade

Texto precisa contrastar com o que está atrás. Sobre cena fotográfica
movimentada, texto branco/claro só funciona se o fundo daquela região for
uniformemente escuro.

Para regras detalhadas de contraste WCAG e combinações cor-a-cor, ver
`shared_skill/contrast-rules.md`.

### Princípios resumidos
1. Faixa/pill de cor sólida sob o texto resolve qualquer dúvida de contraste.
2. Cor de texto deve contrastar com o **conteúdo majoritário** da região
   onde cai (não com a cena inteira).
3. Sobre fotografia, evitar texto branco sobre regiões com variação tonal
   (algumas letras somem, outras destacam).

---

## 10. Quebra de texto (text wrapping)

Como o texto quebra entre linhas afeta diretamente a legibilidade e o
profissionalismo da peça.

### Problemas comuns
- **Órfã**: última linha com 1–2 palavras solitárias
- **Viúva**: primeira linha com 1–2 palavras antes da quebra
- **Linha muito longa**: > 85% da largura do canvas (cansativo)
- **Linha muito curta**: < 30% da largura (ritmo truncado)
- **Quebra de número/unidade**: `R$` / `49,90` em linhas separadas
- **Excesso de linhas por bloco**:
  - Título: máx 2 linhas
  - Subtítulo: máx 2 linhas (idealmente 1)
  - Corpo: máx 4 linhas (Stories: máx 3)
  - **CTA: SEMPRE 1 linha — nunca quebrar**

### Fix tipo
Ajustar `width_pct` da caixa de texto para forçar quebra mais natural.
Se nem assim couber, reduzir `font_size_pct` em 1–2 pontos.
