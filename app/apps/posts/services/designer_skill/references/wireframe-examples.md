# Exemplos de Wireframe Plan

---

## Exemplo 1 — Feed quadrado 1080×1080, framework PAS, tom jovem

**Inputs resumidos:**
- copy: "Cansado de grumos no seu shake?" / body 4 parágrafos / CTA "Garanta o seu com frete grátis"
- strategy: intenção promocional, B2C fitness masculino, Instagram
- kb: marca jovem/urgente, paleta preto + laranja + branco, sans-serif bold
- design_hints: ["headline em destaque máximo", "CTA em botão de alto contraste", "produto em destaque"]

```json
{
  "designer_meta": {
    "format": "feed_square",
    "dimensions_px": { "width": 1080, "height": 1080 },
    "safe_zone_inset_px": { "top": 80, "right": 80, "bottom": 80, "left": 80 },
    "framework_used": "PAS",
    "priority_chain_applied": {
      "user_explicit": ["headline em destaque máximo", "CTA em botão de alto contraste"],
      "ref_visual": [],
      "kb": ["paleta preto + laranja + branco", "sans-serif bold", "tom jovem → high contrast"],
      "inferred": ["posição do produto à direita (PAS: solução no lado direito)", "overlay escuro para legibilidade"]
    }
  },
  "approval": {
    "status": "approved",
    "confidence": "high",
    "reason": "Todos os elementos de copy mapeados. Hierarquia respeita PAS. CTA tem shape container. Safe zone respeitada.",
    "iterate_on": []
  },
  "image_prompts": [
    {
      "id": "prompt_001",
      "element_id": "bg_lifestyle_image",
      "prompt": "Athletic male in gym environment holding protein shaker bottle, dynamic pose mid-motion, high-key bright studio lighting with dramatic side shadow, black and orange color palette, tight crop showing upper body and product, energetic and confident expression, commercial fitness photography style, high resolution sharp focus, no text no words no logos no brand marks",
      "aspect_ratio": "1:1",
      "style": "photorealistic"
    }
  ],
  "wireframe_plan": {
    "total_elements": 8,
    "render_order": [
      "bg_lifestyle_image",
      "overlay_dark",
      "headline_text",
      "body_text",
      "cta_button_shape",
      "cta_button_text",
      "product_badge",
      "logo"
    ],
    "elements": [
      {
        "id": "bg_lifestyle_image",
        "type": "image",
        "mechanism": "gemini",
        "layer": 1,
        "position": { "x_px": 0, "y_px": 0, "anchor": "topleft" },
        "size": { "width_px": 1080, "height_px": 1080 },
        "content": { "gemini_prompt_id": "prompt_001" },
        "style": {},
        "decision_source": "inferred",
        "gemini_prompt_id": "prompt_001"
      },
      {
        "id": "overlay_dark",
        "type": "overlay",
        "mechanism": "pillow",
        "layer": 2,
        "position": { "x_px": 0, "y_px": 0, "anchor": "topleft" },
        "size": { "width_px": 1080, "height_px": 1080 },
        "content": { "color_hex": "#000000", "opacity_0_to_1": 0.55 },
        "style": {},
        "decision_source": "inferred",
        "gemini_prompt_id": null
      },
      {
        "id": "headline_text",
        "type": "text",
        "mechanism": "pillow",
        "layer": 3,
        "position": { "x_px": 80, "y_px": 120, "anchor": "topleft" },
        "size": { "width_px": 860, "height_px": null },
        "content": {
          "text": "Cansado de grumos no seu shake?",
          "font_family": "Inter",
          "font_size_px": 88,
          "font_weight": "bold",
          "color_hex": "#FFFFFF",
          "align": "left",
          "max_width_px": 860,
          "line_spacing": 1.15
        },
        "style": {},
        "decision_source": "user_explicit",
        "gemini_prompt_id": null
      },
      {
        "id": "body_text",
        "type": "text",
        "mechanism": "pillow",
        "layer": 3,
        "position": { "x_px": 80, "y_px": 420, "anchor": "topleft" },
        "size": { "width_px": 780, "height_px": null },
        "content": {
          "text": "Você mistura, mistura e ainda tem aquela pelota no fundo.\n\nNão é falta de técnica — é o produto errado.\n\nO Whey X dissolve em 10 segundos, sem grumos.",
          "font_family": "Inter",
          "font_size_px": 34,
          "font_weight": "regular",
          "color_hex": "#E0E0E0",
          "align": "left",
          "max_width_px": 780,
          "line_spacing": 1.4
        },
        "style": {},
        "decision_source": "kb",
        "gemini_prompt_id": null
      },
      {
        "id": "cta_button_shape",
        "type": "shape",
        "mechanism": "pillow",
        "layer": 4,
        "position": { "x_px": 80, "y_px": 890, "anchor": "topleft" },
        "size": { "width_px": 580, "height_px": 72 },
        "content": {
          "shape_type": "rounded_rect",
          "color_hex": "#FF6B00",
          "border_radius_px": 8
        },
        "style": {},
        "decision_source": "user_explicit",
        "gemini_prompt_id": null
      },
      {
        "id": "cta_button_text",
        "type": "text",
        "mechanism": "pillow",
        "layer": 5,
        "position": { "x_px": 370, "y_px": 926, "anchor": "center" },
        "size": { "width_px": 540, "height_px": null },
        "content": {
          "text": "Garanta o seu com frete grátis hoje",
          "font_family": "Inter",
          "font_size_px": 36,
          "font_weight": "bold",
          "color_hex": "#FFFFFF",
          "align": "center",
          "max_width_px": 540,
          "line_spacing": 1.0
        },
        "style": {},
        "decision_source": "user_explicit",
        "gemini_prompt_id": null
      },
      {
        "id": "product_badge",
        "type": "shape",
        "mechanism": "pillow",
        "layer": 4,
        "position": { "x_px": 820, "y_px": 80, "anchor": "topleft" },
        "size": { "width_px": 180, "height_px": 180 },
        "content": {
          "shape_type": "ellipse",
          "color_hex": "#FF6B00",
          "border_radius_px": 90
        },
        "style": {},
        "decision_source": "strategy",
        "gemini_prompt_id": null
      },
      {
        "id": "logo",
        "type": "logo",
        "mechanism": "pillow",
        "layer": 6,
        "position": { "x_px": 80, "y_px": 80, "anchor": "topleft" },
        "size": { "width_px": 160, "height_px": 48 },
        "content": {
          "asset_path": "assets/logo_white.png",
          "preserve_colors": false
        },
        "style": {},
        "decision_source": "kb",
        "gemini_prompt_id": null
      }
    ]
  },
  "flags": []
}
```

---

## Exemplo 2 — Stories 1080×1920, framework Hook+Valor+CTA, tom inspiracional

**Inputs resumidos:**
- copy: "O verão não espera você estar pronta" / body 3 linhas / CTA "Descubra a coleção completa"
- strategy: awareness, moda feminina B2C, tom inspiracional
- kb: tons terrosos, foto de pessoa real, sans-serif clean
- design_hints: ["headline pode ser sobreposta na foto", "CTA na metade inferior, fora zona de perfil"]

```json
{
  "designer_meta": {
    "format": "stories",
    "dimensions_px": { "width": 1080, "height": 1920 },
    "safe_zone_inset_px": { "top": 250, "right": 80, "bottom": 400, "left": 80 },
    "framework_used": "Hook+Valor+CTA",
    "priority_chain_applied": {
      "user_explicit": ["CTA na metade inferior, fora zona de perfil"],
      "ref_visual": [],
      "kb": ["tons terrosos", "foto de pessoa real", "tom inspiracional → golden hour lighting"],
      "inferred": ["overlay gradiente para legibilidade do texto", "headline no terço superior com muito espaço"]
    }
  },
  "approval": {
    "status": "approved",
    "confidence": "high",
    "reason": "Hierarquia Hook+Valor+CTA respeitada. CTA posicionado em y:1440, acima da safe zone base (1520). Texto não ultrapassa safe zone lateral.",
    "iterate_on": []
  },
  "image_prompts": [
    {
      "id": "prompt_001",
      "element_id": "bg_lifestyle_photo",
      "prompt": "Young Brazilian woman in summer dress walking on sunlit cobblestone street, natural movement candid style, golden afternoon warm light, earth tones palette with terracotta and sage green accents, shallow depth of field blurred background, rule of thirds composition subject left-of-center, lifestyle photography authentic unposed, vertical 9:16 format, high resolution sharp focus, no text no words no logos no brand marks",
      "aspect_ratio": "9:16",
      "style": "photorealistic"
    }
  ],
  "wireframe_plan": {
    "total_elements": 6,
    "render_order": [
      "bg_lifestyle_photo",
      "overlay_gradient",
      "headline_text",
      "body_text",
      "cta_button_shape",
      "cta_button_text"
    ],
    "elements": [
      {
        "id": "bg_lifestyle_photo",
        "type": "image",
        "mechanism": "gemini",
        "layer": 1,
        "position": { "x_px": 0, "y_px": 0, "anchor": "topleft" },
        "size": { "width_px": 1080, "height_px": 1920 },
        "content": { "gemini_prompt_id": "prompt_001" },
        "style": {},
        "decision_source": "kb",
        "gemini_prompt_id": "prompt_001"
      },
      {
        "id": "overlay_gradient",
        "type": "overlay",
        "mechanism": "pillow",
        "layer": 2,
        "position": { "x_px": 0, "y_px": 900, "anchor": "topleft" },
        "size": { "width_px": 1080, "height_px": 1020 },
        "content": { "color_hex": "#1A0A00", "opacity_0_to_1": 0.65 },
        "style": {},
        "decision_source": "inferred",
        "gemini_prompt_id": null
      },
      {
        "id": "headline_text",
        "type": "text",
        "mechanism": "pillow",
        "layer": 3,
        "position": { "x_px": 80, "y_px": 980, "anchor": "topleft" },
        "size": { "width_px": 920, "height_px": null },
        "content": {
          "text": "O verão não espera você estar pronta",
          "font_family": "Lora",
          "font_size_px": 92,
          "font_weight": "bold",
          "color_hex": "#FFFFFF",
          "align": "left",
          "max_width_px": 920,
          "line_spacing": 1.2
        },
        "style": {},
        "decision_source": "user_explicit",
        "gemini_prompt_id": null
      },
      {
        "id": "body_text",
        "type": "text",
        "mechanism": "pillow",
        "layer": 3,
        "position": { "x_px": 80, "y_px": 1270, "anchor": "topleft" },
        "size": { "width_px": 860, "height_px": null },
        "content": {
          "text": "Peças leves que não grudam, cores que não desbotam, preços que não assustam.",
          "font_family": "Inter",
          "font_size_px": 44,
          "font_weight": "regular",
          "color_hex": "#F0E6D3",
          "align": "left",
          "max_width_px": 860,
          "line_spacing": 1.35
        },
        "style": {},
        "decision_source": "kb",
        "gemini_prompt_id": null
      },
      {
        "id": "cta_button_shape",
        "type": "shape",
        "mechanism": "pillow",
        "layer": 4,
        "position": { "x_px": 80, "y_px": 1440, "anchor": "topleft" },
        "size": { "width_px": 680, "height_px": 76 },
        "content": {
          "shape_type": "rounded_rect",
          "color_hex": "#C97D4E",
          "border_radius_px": 38
        },
        "style": {},
        "decision_source": "user_explicit",
        "gemini_prompt_id": null
      },
      {
        "id": "cta_button_text",
        "type": "text",
        "mechanism": "pillow",
        "layer": 5,
        "position": { "x_px": 420, "y_px": 1478, "anchor": "center" },
        "size": { "width_px": 620, "height_px": null },
        "content": {
          "text": "Descubra a coleção completa",
          "font_family": "Inter",
          "font_size_px": 38,
          "font_weight": "semibold",
          "color_hex": "#FFFFFF",
          "align": "center",
          "max_width_px": 620,
          "line_spacing": 1.0
        },
        "style": {},
        "decision_source": "kb",
        "gemini_prompt_id": null
      }
    ]
  },
  "flags": [
    {
      "type": "warning",
      "message": "Logo não presente no wireframe — briefing não forneceu asset de logo",
      "affects": "pillow",
      "recommendation": "Solicitar asset de logo ao cliente antes de finalizar. Posição sugerida: x:80, y:270 (logo acima da safe_zone topo)"
    }
  ]
}
```

---

## Exemplo 3 — Status `iterate` (plano com problema detectado)

**Cenário**: CTA sem shape container, elemento de texto sem `max_width_px`.

```json
{
  "approval": {
    "status": "iterate",
    "confidence": "medium",
    "reason": "CTA não possui shape container (botão sem fundo). Elemento 'body_text' sem max_width_px — risco de overflow na safe zone.",
    "iterate_on": [
      "Adicionar elemento shape 'cta_button_shape' como layer abaixo do 'cta_button_text'",
      "Definir max_width_px: 860 para 'body_text' com base na safe zone (1080 - 80 - 80 - 60)"
    ]
  }
}
```
