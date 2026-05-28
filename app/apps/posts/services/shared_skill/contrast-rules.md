# Regras de Contraste e Acessibilidade Visual

Referência rápida para o agente validar contraste e visibilidade em artes de redes sociais.

---

## Padrões de Contraste (WCAG 2.1)

| Situação | Ratio mínimo | Grau |
|---|---|---|
| Corpo de texto (< 24px ou < 18.67px bold) | **4.5:1** | AA |
| Texto grande (≥ 24px regular ou ≥ 18.67px bold) | **3.0:1** | AA |
| Elementos de UI (ícones, bordas de botão) | **3.0:1** | AA |
| Texto decorativo, logotipo | sem mínimo | — |
| Padrão ouro (qualquer texto) | **7.0:1** | AAA |

---

## Overlay em Texto Sobre Foto

Quando texto é colocado diretamente sobre uma fotografia, é preciso garantir legibilidade.

### Regras práticas:

| Tipo de overlay | Opacidade mínima | Resultado esperado |
|---|---|---|
| Overlay escuro (`#000000`) | 40% | Texto branco legível sobre foto clara |
| Overlay escuro (`#000000`) | 60% | Texto branco confortável, foto ainda visível |
| Overlay claro (`#FFFFFF`) | 50% | Texto escuro legível |
| Gradiente (transparente → sólido) | 70% na área de texto | Preferível esteticamente |

### Como detectar falta de overlay:

Se texto branco aparece sobre área com tom médio (luminância > 0.4), há risco de ilegibilidade.
Se texto escuro aparece sobre área escura (luminância < 0.2), há risco de ilegibilidade.

Gere um fix `add_overlay` sempre que identificar texto sobre foto sem escurecimento/clareamento suficiente.

---

## Combinações de Cor — Alerta Rápido

### Combinações que sempre falham (evitar)

| Texto | Fundo | Problema |
|---|---|---|
| Amarelo `#FFD700` | Branco `#FFFFFF` | Contraste 1.2:1 — invisível |
| Verde claro `#90EE90` | Branco | Contraste 1.5:1 |
| Cinza médio `#888` | Branco | Contraste 3.5:1 — reprovado AA normal |
| Vermelho puro `#FF0000` | Verde `#00FF00` | Problema para daltônicos |
| Azul `#0000FF` | Roxo `#800080` | Difícil distinção |

### Combinações que sempre funcionam

| Texto | Fundo | Ratio |
|---|---|---|
| Preto `#000000` | Branco `#FFFFFF` | 21:1 |
| Branco `#FFFFFF` | Preto `#000000` | 21:1 |
| Branco `#FFFFFF` | Azul escuro `#003366` | 12.6:1 |
| Preto `#000000` | Amarelo `#FFFF00` | 19.6:1 |
| Branco `#FFFFFF` | Vermelho escuro `#CC0000` | 5.9:1 |

---

## Poluição Visual — Regra das 4 Cores

Uma peça de social media bem executada usa no máximo **4 cores dominantes**:
1. Cor de fundo principal
2. Cor de acento / destaque
3. Cor do texto principal
4. Cor secundária / suporte

Se identificar mais de 4 cores dominantes distintas, gere fix de categoria `color` com:
- `problem`: "Excesso de cores dominantes reduz coesão visual"
- `action`: `recolor` para harmonizar elementos secundários com a paleta existente

---

## Botão CTA — Checklist de Contraste

Um botão CTA precisa passar em **todos** estes critérios:

1. **Fundo do botão vs. fundo da peça**: diferença de luminância ≥ 0.25 (escala 0–1)
2. **Texto do CTA vs. fundo do botão**: ratio ≥ 4.5:1
3. **Borda do botão** (se existir): ratio vs. fundo da peça ≥ 3.0:1

Se o botão "some" no fundo, gere fix `recolor` no botão E possivelmente `add_overlay` na região ao redor.

---

## Detectando Problemas de Imagem (sem acesso a pixels exatos)

Como o agente trabalha com análise visual, use estas heurísticas:

| Sintoma visual | Diagnóstico provável | Fix sugerido |
|---|---|---|
| Texto com bordas serrilhadas | Fonte renderizada em baixa resolução | `rescale_font` para tamanho maior |
| Imagem com "quadradinhos" visíveis | Imagem fonte em baixa resolução / muito ampliada | Reportar como `major` — Pillow não pode corrigir (precisa de nova asset) |
| Elementos levemente tortos | Rotação não-múltipla de 90° acidental | `reposition` com ângulo corrigido |
| Sombra cortada na borda | Elemento muito perto da borda | `reposition` para dentro da safe zone |
| Imagem esticada horizontalmente | Aspect ratio incorreto no resize | `crop` + `resize` mantendo ratio original |
