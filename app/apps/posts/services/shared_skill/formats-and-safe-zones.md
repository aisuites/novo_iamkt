# Formatos, Dimensões e Áreas Seguras

Referência compartilhada entre designer (criador) e crítico (revisor).
Todos os agentes que trabalham com layouts de social media devem consultar
este arquivo para identificar formato, calcular safe zones e converter
pixels para o sistema de coordenadas do iamkt (%_pct).

---

## ⚠️ Nota de integração no iamkt

O iamkt usa **percentuais (`%_pct`)** relativos ao canvas, NÃO pixels. Toda
referência em pixels deste skill (vinda das tabelas de design padrão) deve
ser convertida ao emitir edits.

### Fórmula de conversão

```
pct = (valor_px / dim_referencia_px) * 100
```

| Campo | `dim_referencia_px` |
|---|---|
| `x_pct`, `width_pct` | largura do canvas |
| `y_pct`, `height_pct` | altura do canvas |
| `font_size_pct` | **menor dimensão** (`min(W, H)`) |
| `padding_pct`, `raio_pct` | largura do canvas |

### Conversão pronta dos tamanhos mais usados

| Formato | Dim ref (para fs) | Título mín → %_pct | Título ideal | Subtítulo ideal | CTA ideal |
|---|---|---|---|---|---|
| Feed 1080×1080 (1:1) | 1080 | 60px → **5.5%** | 80–100px → **7.4–9.3%** | 44–52px → **4.1–4.8%** | 38–44px → **3.5–4.1%** |
| Feed 1080×1350 (4:5) | 1080 | 60px → **5.5%** | 80–110px → **7.4–10.2%** | 44–56px → **4.1–5.2%** | 40–46px → **3.7–4.3%** |
| Stories 1080×1920 (9:16) | 1080 | 72px → **6.7%** | 96–120px → **8.9–11.1%** | 52–64px → **4.8–5.9%** | 48–56px → **4.4–5.2%** |
| Banner LinkedIn 1584×396 | 396 | 36px → **9.1%** | 48–60px → **12.1–15.2%** | 30–36px → **7.6–9.1%** | 32–38px → **8.1–9.6%** |
| Ad Meta 1200×628 (16:9) | 628 | 48px → **7.6%** | 64–80px → **10.2–12.7%** | 36–44px → **5.7–7.0%** | 38–44px → **6.1–7.0%** |

Para escala completa por formato (corpo, microcopy, leading), ver
`shared_skill/typography-scale.md`.

---

## Tabela de formatos e áreas seguras

Identificar o formato é o primeiro passo de qualquer análise/criação.
Se não conseguir inferir, use `format = "unknown"` e `safe_inset = 80px`.

| Formato | Dimensões | Aspect ratio | Safe zone (inset) | Plataformas |
|---|---|---|---|---|
| Feed quadrado | 1080×1080 | 1:1 | 80px (≈7.4%) | Instagram, Facebook |
| Feed retrato | 1080×1350 | 4:5 | 80px topo/base, 80px lados | Instagram, Facebook |
| Stories / Reels | 1080×1920 | 9:16 | **250px topo (UI perfil), 400px base (UI interação), 80px lados** | Instagram, Facebook, TikTok |
| Banner LinkedIn | 1584×396 | ≈4:1 | 60px todas as bordas; zona central 400–1184px horizontalmente | LinkedIn |
| Banner YouTube | 2560×1440 | 16:9 | zona central 1546×423 (segura em qualquer tela) | YouTube |
| Anúncio Meta horizontal | 1200×628 | ≈16:9 (1.91:1) | 80px todas as bordas | Facebook Ads, Instagram Ads |
| Anúncio Google Display | variado | variado | 40px todas as bordas | Google Display Network |

### Convertendo safe zones para %_pct

| Formato | Safe inset px | Safe inset %_pct |
|---|---|---|
| Feed 1080×1080 | 80 | **~7.4%** todos lados |
| Stories 1080×1920 | topo 250, base 400, lados 80 | topo **13%**, base **20.8%**, lados **7.4%** |
| Banner LinkedIn 1584×396 | 60 | **3.8%** lados, **15.2%** topo/base |
| Ad Meta 1200×628 | 80 | **6.7%** lados, **12.7%** topo/base |

---

## Margens e respiros

### Margens mínimas para legibilidade

Independente do safe zone formal da plataforma, designers devem respeitar:

| Elemento | Margem inferior | Margem superior | Margem lateral |
|---|---|---|---|
| Texto (corpo/legenda) | ≥ 4% antes da borda inferior | ≥ 4% topo | ≥ 4% laterais |
| Título | ≥ 5% antes da borda inferior | ≥ 4% topo | ≥ 4% laterais |
| Logo | **≥ 6–8% antes da borda inferior** (logo colado na borda parece erro de produção) | ≥ 4% | ≥ 4% lateral |
| CTA / botão | ≥ 5% antes da borda inferior | — | ≥ 4% lateral |

### Para logo `bottom-right` em 1:1 (1080×1080):
- `y_pct` típico em **82–86%**, NÃO `90%`+ (fica colado na borda).
- `x_pct + width_pct ≤ 96%` (deixa 4%+ de respiro à direita).

### Regras de safe zone por plataforma

**Stories/Reels**: NUNCA colocar elementos na zona do perfil (topo 250px = 13%) ou
zona de interação (base 400px = 20.8%). Esses retângulos têm UI da plataforma
sobreposta — qualquer elemento ali será coberto.

**Anúncios Meta**: texto não deve cobrir mais de **20% da área total** da imagem
— regra do algoritmo, ultrapassar pode reduzir alcance pago.

**Banners LinkedIn/YouTube**: o banner é cortado/escalado em telas diferentes.
Manter elementos críticos na **faixa central horizontal** (400–1184px no LinkedIn,
1546×423 central no YouTube).

---

## Aspect ratio e composição

A regra clássica de composição varia por aspect ratio:

| AR | Sujeito típico vai em | Texto típico vai em |
|---|---|---|
| 9:16 (vertical) | CENTRO-BAIXO | TOPO |
| 4:5 (vertical leve) | CENTRO-BAIXO | TOPO |
| 1:1 (quadrado) | CENTRO ou CENTRO-BAIXO | TOPO ou LATERAL |
| 16:9 (horizontal) | CENTRO-DIREITA | LATERAL ESQUERDA (terço esquerdo) |
| ≈4:1 (banner extra-wide) | LADO DIREITO ou CENTRO | LADO ESQUERDO |

Use essa regra como ponto de partida; pode ser quebrada com intenção (e.g.,
storytelling com sujeito à esquerda em 16:9 acompanhado de texto à direita).
