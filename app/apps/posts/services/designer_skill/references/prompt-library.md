# Biblioteca de Image Prompts

Templates prontos por tom e segmento. Sempre adaptar os campos em `{}` antes de usar.
Nunca copiar sem adaptar — o prompt deve refletir o produto e a marca específicos.

---

## Por Tom Visual

### PREMIUM

**Produto de beleza/skincare:**
```
Subject: {nome_produto} glass bottle elegantly placed on {superfície} marble or brushed concrete surface
Environment: minimalist studio setting, single decorative element such as dried botanicals or clean linen
Lighting: soft diffused natural light from upper left, subtle long shadow to the right
Color palette: cream, off-white, muted {cor_acento_kb}, dusty rose or sage only as accent
Composition: centered with generous negative space, product occupying one third of frame
Style: high-end commercial product photography, editorial magazine quality
Technical: high resolution, sharp focus, 4k, professional retouching
Negative: avoid busy backgrounds, avoid saturated colors, avoid artificial harsh lighting, avoid plastic feel, no text no words no logos no brand marks
```

**Serviço financeiro/B2B:**
```
Subject: confident {gênero} professional in business casual attire
Action: reviewing documents or using laptop in modern office environment
Environment: clean modern office with large windows, city view or neutral wall background
Lighting: soft natural window light, cool temperature, no dramatic shadows
Color palette: cool blues, grays, white — {cor_primaria_kb} as subtle accent
Composition: rule of thirds, subject left or right, workspace visible
Style: corporate lifestyle photography, authentic professional setting
Technical: high resolution, shallow depth of field, sharp subject
Negative: avoid cheesy stock photo poses, avoid overly staged looks, avoid warm orange tones, no text no logos
```

---

### JOVEM / ENERGÉTICO

**Fitness/suplemento:**
```
Subject: athletic {gênero} person, 25-35 years old, fit physique
Action: {ação dinâmica: lifting weights / running / mid-jump / high-five after workout}
Environment: modern gym with equipment visible but blurred background, or urban outdoor setting
Lighting: high-key bright lighting, punchy contrast, slight rim light
Color palette: {cores_kb} saturated and bold, high contrast, black and vibrant accent
Composition: dynamic diagonal composition, tight crop on upper body, asymmetric
Style: commercial fitness photography, high energy, authentic effort
Technical: high resolution, motion-freeze or slight motion blur on non-subject elements, sharp focus on face and product
Negative: avoid stock photo feel, avoid overly posed looks, avoid muted tones, no text no words no logos
```

**Moda jovem/streetwear:**
```
Subject: young {gênero} person, 20-28 years old, wearing {descrição_peça}
Action: candid street moment, natural movement, confident
Environment: urban street, concrete wall, colorful mural, or rooftop
Lighting: bright natural daylight or golden hour, punchy and warm
Color palette: {cores_kb} + urban environment colors, saturated
Composition: close to medium shot, slight low angle, asymmetric
Style: street style editorial photography, authentic, raw energy
Technical: high resolution, slight grain acceptable for authenticity
Negative: avoid studio look, avoid obvious posing, avoid luxury hotel or mall backgrounds, no text no logos
```

---

### INSPIRACIONAL / WELLNESS

**Alimentação saudável:**
```
Subject: fresh {prato ou ingrediente} beautifully arranged
Environment: {superfície}: light wood, marble, or linen fabric with natural texture
Lighting: soft natural window light from side, warm temperature, gentle shadows
Color palette: earth tones, warm whites, fresh greens, {cor_acento_kb}
Composition: flat lay or slight overhead angle, organic arrangement, some intentional imperfection
Style: food styling editorial photography, appetizing, artisanal feel
Technical: high resolution, shallow depth of field for hero ingredient, sharp center
Negative: avoid dark dramatic backgrounds for hero shots, avoid plastic or artificial colors, no text no logos
```

**Bem-estar/lifestyle:**
```
Subject: {gênero} person, 28-40, relaxed and content expression
Action: {momento}: reading by window / morning coffee ritual / yoga on terrace / journaling
Environment: warm inviting home interior or nature setting (park, garden, beach)
Lighting: golden hour or soft morning window light, warm temperature, gentle bokeh
Color palette: warm whites, earth tones, sage, {cor_kb}
Composition: rule of thirds, subject occupies one third, environment tells story
Style: candid lifestyle photography, natural, unposed, authentic
Technical: shallow depth of field, bokeh background, high resolution
Negative: avoid clinical look, avoid overly perfect influencer aesthetic, avoid harsh lighting, no text no logos
```

---

### CONFIÁVEL / TÉCNICO

**Tecnologia/SaaS:**
```
Subject: clean laptop or device screen showing {tipo de interface: dashboard / charts / app}
Environment: modern minimalist desk, neutral background
Lighting: soft ambient light, no glare on screen, cool temperature
Color palette: {cor_kb}, white, light grays — professional and clean
Composition: slight angle shot of device, or flat lay from above
Style: technology product photography, clean and professional
Technical: high resolution, screen content visible but not detailed enough to read
Negative: avoid messy desk, avoid warm tones, avoid lifestyle clutter, no text visible on screen, no logos
```

**Consultoria/RH:**
```
Subject: diverse group of {2-3} professionals in collaborative setting
Action: engaged discussion, reviewing materials, collaborative energy
Environment: modern meeting room or collaborative workspace with glass walls
Lighting: bright professional lighting, cool and clean
Color palette: cool neutrals, white, {cor_kb} as accent in clothing or environment
Composition: medium group shot, eye contact and engagement between people
Style: corporate lifestyle photography, authentic collaboration
Technical: high resolution, sharp focus on faces
Negative: avoid overly staged meeting room photos, avoid all-white demographics, no text no logos
```

---

## Por Formato de Arte

### Para Stories 9:16 (1080×1920)

Toda foto deve ser **vertical e pensada para o espaço**:
- Sujeito principal no terço central da imagem (nem topo nem base)
- Área de baixa complexidade no topo (para overlay de headline) e na base (para CTA)
- Adicionar ao final do prompt: `vertical 9:16 portrait orientation, subject centered vertically, clean areas top and bottom for text overlay`

### Para Feed Quadrado 1:1 (1080×1080)

- Sujeito principal centralizado ou em composição equilibrada
- Adicionar ao final: `square 1:1 format, balanced composition, subject fits within square crop`

### Para Banner Landscape 16:9 ou 1.91:1

- Sujeito principal no lado direito ou esquerdo (deixar espaço para texto)
- Adicionar ao final: `horizontal landscape format, subject on right third leaving space for text on left, or vice versa`

---

## Erros comuns de prompt — e como corrigir

| ✗ Erro | ✓ Correção |
|---|---|
| "foto bonita de produto" | "close-up of {product} on marble surface, soft diffused lighting, muted palette" |
| "pessoa feliz" | "woman, early 30s, genuine warm smile, natural expression, looking slightly off-camera" |
| "fundo legal" | "light warm gray concrete texture background, subtle variation, no distracting elements" |
| "estilo moderno" | "contemporary minimalist aesthetic, clean lines, neutral palette with single bold accent" |
| "iluminação boa" | "soft diffused natural window light from upper left, gentle shadows, no harsh highlights" |
| "composição interessante" | "rule of thirds composition, subject in left third, negative space on right" |
| Esquecer o negative | Sempre terminar com: `no text, no words, no typography, no logos, no brand marks` |
