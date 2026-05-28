# Escala Tipográfica por Formato — Referência

Tamanhos mínimos e ideais para cada elemento textual, em pixels, por formato de arte.
Todos os valores assumem a dimensão padrão do formato. Para imagens em resolução diferente,
escale proporcionalmente: `font_px_ajustado = font_px_referencia * (largura_real / largura_referencia)`.

---

## Feed Quadrado — 1080×1080px

| Elemento | Mínimo | Ideal | Máximo |
|---|---|---|---|
| Título (headline) | 60px | 80–100px | 140px |
| Subtítulo | 36px | 44–52px | 64px |
| Corpo / descrição | 28px | 32–36px | 44px |
| Label do CTA | 32px | 38–44px | 52px |
| Microcopy (ex: *condições aplicáveis*) | 20px | 24px | 28px |

**Leading ideal**: 130% do font-size  
**Tracking**: neutro a levemente aberto (+10 a +30 em unidades de design)

---

## Feed Retrato — 1080×1350px

| Elemento | Mínimo | Ideal |
|---|---|---|
| Título | 60px | 80–110px |
| Subtítulo | 36px | 44–56px |
| Corpo | 28px | 32–38px |
| CTA label | 32px | 40–46px |

---

## Stories / Reels — 1080×1920px

| Elemento | Mínimo | Ideal | Observação |
|---|---|---|---|
| Título | 72px | 96–120px | Consumido em velocidade — deve ser maior |
| Subtítulo | 44px | 52–64px | |
| Corpo | 36px | 40–48px | Máx 3 linhas por tela |
| CTA label | 40px | 48–56px | |

**Zona segura**: topo 250px reservado (UI do perfil), base 400px (barra de interação)

---

## Banner LinkedIn — 1584×396px

| Elemento | Mínimo | Ideal |
|---|---|---|
| Título | 36px | 48–60px |
| Subtítulo | 24px | 30–36px |
| CTA label | 28px | 32–38px |

**Atenção**: Banner é exibido em múltiplos tamanhos. Manter todos os elementos na faixa central (400–1184px horizontalmente).

---

## Anúncio Meta Horizontal — 1200×628px

| Elemento | Mínimo | Ideal |
|---|---|---|
| Título | 48px | 64–80px |
| Subtítulo | 28px | 36–44px |
| CTA label | 32px | 38–44px |

**Regra de texto**: texto não deve ultrapassar 20% da área total (240.256px² para 1200×628)

---

## Escala de Hierarquia Visual

Para qualquer formato, a razão de tamanho entre níveis deve ser:

```
título : subtítulo : corpo : microcopy
  1.0  :   0.6    :  0.45  :   0.3
```

Exemplo para feed 1080 com título em 90px:
- Subtítulo: 54px
- Corpo: 40px
- Microcopy: 27px — arredondar para 28px

---

## Contraste Mínimo por Uso

| Uso | Ratio mínimo | Standard |
|---|---|---|
| Texto normal (corpo, legenda) | 4.5:1 | WCAG AA |
| Texto grande (título ≥ 24px bold ou ≥ 32px regular) | 3.0:1 | WCAG AA Large |
| Elementos de UI (botões, bordas) | 3.0:1 | WCAG AA UI |
| Decorativo (não carrega informação) | sem mínimo | — |

### Como estimar contraste sem ferramenta

Luminância relativa de uma cor `#RRGGBB`:
```
R_lin = (R/255)^2.2
G_lin = (G/255)^2.2
B_lin = (B/255)^2.2
L = 0.2126 * R_lin + 0.7152 * G_lin + 0.0722 * B_lin
ratio = (L_claro + 0.05) / (L_escuro + 0.05)
```

Referências rápidas comuns:
- Preto `#000` sobre branco `#FFF` → 21:1 ✓
- `#767676` sobre `#FFF` → 4.54:1 ✓ (mínimo AA)
- `#8A8A8A` sobre `#FFF` → 3.1:1 ✗
- Branco `#FFF` sobre azul `#1F4E79` → 7.2:1 ✓
- Amarelo `#FFFF00` sobre branco → 1.07:1 ✗ (ilegível)
