# Exemplos de Payloads — Social Media Design Critic

⚠️ **Nota iamkt**: estes exemplos usam o schema rico original do skill (com `analysis`,
`fixes`, `action`, `params`). No iamkt **traduzimos** para o schema simples
`{approved, rationale, edits[{target_role, field, new_value, reason}]}`. Use o
raciocínio destes exemplos mas emita no schema simplificado.

---

## Exemplo 1 — Story com CTA desalinhado e título pequeno

**Contexto**: Story 1080×1920, título "Promoção de Verão" com fonte estimada em 38px,
botão CTA com texto visualmente deslocado para cima dentro do shape.

### Raciocínio (skill original)

```json
{
  "analysis": {
    "format": "stories",
    "dimensions_px": { "width": 1080, "height": 1920 },
    "safe_zone_inset_px": { "top": 250, "right": 80, "bottom": 400, "left": 80 },
    "overall_score": 52,
    "score_breakdown": { "typography": 40, "layout": 70, "cta": 50, "color": 80, "image": 75 },
    "summary": "Peça com problemas críticos de tipografia e CTA que comprometem legibilidade e conversão."
  },
  "fixes": [
    {
      "id": "fix_001", "severity": "critical", "category": "typography",
      "element": "titulo_promocao_verao",
      "problem": "Fonte do título está em 38px, abaixo do mínimo de 60px para Stories 1080px.",
      "current_value": "38px", "target_value": "72px",
      "action": "rescale_font", "params": { "element_id": "titulo", "font_size_px": 72 }
    },
    {
      "id": "fix_002", "severity": "critical", "category": "cta",
      "element": "texto_cta_saiba_mais",
      "problem": "Texto 'Saiba Mais' está deslocado 18px acima do centro vertical do botão.",
      "action": "align", "params": { "element_id": "cta_text", "align_to": "center", "reference": "botao_cta" }
    }
  ]
}
```

### Output traduzido pro iamkt

```json
{
  "approved": false,
  "rationale": "Story com dois problemas críticos: título a 38px (sub-mínimo 60px → 6.7%_pct) compromete legibilidade em consumo mobile rápido; CTA com texto descentrado verticalmente dentro do pill (deslocado pra cima) parece erro de produção.",
  "edits": [
    {
      "target_role": "titulo",
      "field": "font_size_pct",
      "new_value": 8.5,
      "reason": "[critical/typography] Stories: mínimo 6.7% (72px/1080), ideal 8.9-11.1%. Atual ~3.5% abaixo do mínimo."
    },
    {
      "target_role": "cta",
      "field": "y_pct",
      "new_value": 73.4,
      "reason": "[critical/cta] Centralizar texto no pill (grafismo y=70, h=10, fs=2.8 → offset=3.4 → y=73.4)."
    }
  ]
}
```

---

## Exemplo 2 — Feed quadrado com excesso de texto

**Contexto**: Anúncio Meta 1200×628, texto cobre ~35% da imagem (limite 20%).

### Output iamkt

```json
{
  "approved": false,
  "rationale": "Anúncio Meta com texto cobrindo ~35% da área (limite 20%). Risco de redução de alcance pela plataforma. Recomendo reduzir caixa de texto ou dividir em múltiplas peças.",
  "edits": [
    {
      "target_role": "subtitulo",
      "field": "width_pct",
      "new_value": 50,
      "reason": "[critical/format_rule] Meta Ads exige texto ≤ 20% da área. Reduzir caixa de subtítulo + reescrever (flag para revisão manual)."
    }
  ]
}
```

---

## Exemplo 3 — Peça sem problemas graves (score alto)

```json
{
  "approved": true,
  "rationale": "Peça bem executada: hierarquia clara, contraste adequado, proporções dentro do padrão. Pequenos refinamentos possíveis (ícone WhatsApp 7px à direita do eixo central do CTA, leading do corpo levemente comprimido) mas não impactam a comunicação."
}
```

---

## Exemplo 4 — Feed com problemas de quebra de linha

**Contexto**: Feed quadrado 1080×1080. Título "Transforme sua rotina com nosso novo produto" quebra
em 3 linhas, última com apenas "produto" (órfã). Subtítulo com primeira linha muito longa.
CTA "Compre agora e ganhe frete grátis" quebrou em 2 linhas.

### Output iamkt

```json
{
  "approved": false,
  "rationale": "Três problemas de quebra de texto: (1) título quebra em 3 linhas com órfã 'produto' isolada na linha 3 — máximo aceitável é 2 linhas; (2) primeira linha do subtítulo ocupa 92% da largura, forçando varredura ocular excessiva; (3) CTA 'Compre agora e ganhe frete grátis' quebrou em 2 linhas — CTA nunca deve quebrar.",
  "edits": [
    {
      "target_role": "cta",
      "field": "width_pct",
      "new_value": 42,
      "reason": "[critical/typography] CTA quebrou em 2 linhas. Aumentar caixa para 42% ou reduzir font para couber em 1 linha. Se ainda não couber, sinalizar pra encurtar texto."
    },
    {
      "target_role": "titulo",
      "field": "width_pct",
      "new_value": 75,
      "reason": "[major/typography] Título com 3 linhas e órfã 'produto'. Aumentar largura puxa palavra pra linha 2."
    },
    {
      "target_role": "subtitulo",
      "field": "width_pct",
      "new_value": 76,
      "reason": "[major/typography] Primeira linha em 92% da largura. Reduzir caixa força quebra mais ergonômica."
    }
  ]
}
```

---

## Padrões úteis pra cobrar do crítico

1. **Sempre justificar com referência ao skill**: prefixar `reason` com `[severity/category]`.
2. **Edits ordenados**: critical primeiro, depois major, depois minor.
3. **Aprovação só com convicção**: dúvida = não aprovar e propor edit.
4. **Calcular conversões px↔%_pct**: usar tabela do SKILL.md.
5. **Quando proximidade tipográfica problemática**: ajustar `y_pct` do subtítulo (mover pra perto do título).
