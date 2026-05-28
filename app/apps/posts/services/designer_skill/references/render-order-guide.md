# Guia de Render Order e Z-Index

A ordem de renderização determina o que fica "na frente" e o que fica "atrás".
Em Pillow, cada elemento é composto sobre o anterior — o último renderizado fica no topo.

---

## Ordem padrão (base → topo)

```
Layer 1 — Fundo (background)
  └── cor sólida, gradiente, ou imagem Gemini de fundo

Layer 2 — Elementos de profundidade
  └── texturas, padrões geométricos, elementos decorativos de fundo

Layer 3 — Overlay / Scrim
  ├── overlay escuro ou claro sobre a imagem de fundo
  └── gradiente direcional para área de texto

Layer 4 — Imagem de suporte
  ├── produto, pessoa ou elemento visual que não é o fundo
  └── (se for foto diferente do bg principal)

Layer 5 — Elementos gráficos
  ├── shapes de botão, badges, tags, barras de urgência
  └── divisores, linhas, formas geométricas decorativas

Layer 6 — Texto principal
  ├── headline, subtítulo, body
  └── (renderizar na ordem: body → subtítulo → headline)

Layer 7 — Texto de ação
  └── texto do CTA (sempre sobre o shape do botão)

Layer 8 — Marca
  └── logo (sempre o último — nunca coberto por outro elemento)
```

---

## Regras absolutas de ordem

| Regra | Motivo |
|---|---|
| Logo sempre no layer mais alto | Nunca pode ser coberto por overlay ou elemento |
| Shape do CTA antes do texto do CTA | Texto precisa aparecer sobre o botão |
| Overlay antes de qualquer texto | Texto precisa ser legível sobre o fundo |
| Imagem de produto antes de textos | Produto pode ter texto sobreposto |
| Background sempre layer 1 | Tudo é composto sobre ele |

---

## Casos especiais

### Texto com sombra
Se o texto tiver sombra (drop shadow), a sombra é parte do mesmo elemento —
Pillow renderiza junto com `ImageFilter.GaussianBlur` ou `ImageDraw` offset.
Não criar elemento separado para sombra.

### Badge sobre produto
Se há um badge (ex: "40% OFF") que precisa aparecer sobre a foto do produto:
- Foto: layer 4
- Badge shape: layer 5
- Badge text: layer 6

### Antes/depois (split layout)
```
Layer 1: bg_left (metade esquerda — cor ou foto "antes")
Layer 1: bg_right (metade direita — cor ou foto "depois")
Layer 2: divider_line (linha vertical central)
Layer 3: label_antes (texto "Antes" sobre bg_left)
Layer 3: label_depois (texto "Depois" sobre bg_right)
Layer 4: headline (sobre ambos os lados)
Layer 5: cta_shape
Layer 6: cta_text
Layer 7: logo
```

### Carrossel
Cada slide é um canvas independente com sua própria render_order.
O wireframe_plan deve ter um array `slides[]` no lugar de `elements[]`:

```json
{
  "layout_type": "carousel",
  "slides": [
    {
      "slide_number": 1,
      "role": "hook",
      "render_order": [...],
      "elements": [...]
    },
    {
      "slide_number": 2,
      "role": "valor_1",
      "render_order": [...],
      "elements": [...]
    }
  ]
}
```

---

## Checklist de render_order

Antes de emitir o wireframe, verificar:

- [ ] `render_order` tem exatamente os mesmos IDs que o array `elements`
- [ ] Nenhum ID aparece duas vezes no render_order
- [ ] `logo` é sempre o último ID no render_order
- [ ] `overlay` aparece antes de qualquer elemento `text`
- [ ] Todo shape de botão aparece antes do texto correspondente do CTA
- [ ] `background` é sempre o primeiro ID

---

## Referência rápida de layers por tipo

| Tipo de elemento | Layer típico |
|---|---|
| `background` (sólido ou imagem de fundo) | 1 |
| Textura / padrão decorativo | 2 |
| `overlay` / scrim | 3 |
| Imagem de produto ou pessoa | 4 |
| Shape de botão / badge | 5 |
| Texto de body / subtítulo | 6 |
| Texto de headline | 7 |
| Texto de CTA | 8 |
| `logo` | 9 (sempre o mais alto) |
