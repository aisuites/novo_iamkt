# Wireframes dos posts — especificação por layout

Coordenadas em **px no canvas real** (feed 1080×1350 · story 1080×1920), prontas
para alimentar o `compose_post.py` (Pillow lê as coordenadas; não 'encaixa no olho').
O documento visual equivalente é `Wireframes_VB_Gastronomia.pdf`.

Margem segura: **90px (feed) / 70px (story)** — nada de texto/logo fora dela.

## 01 · FEED · SOLID — Hook sobre cor sólida
- **Canvas:** 1080×1350 px · fundo `oliva`
- **Uso:** Frase de identificação + convite, sobre fundo chapado, com grafismo de comida no terço inferior.
- **Zonas (px):**
  - `BG` Background — cor sólida oliva #666651 (full bleed)
  - `2` **Título / pergunta** · x=90 y=150 770×250 — Acumin Cond. Light · 84px · creme · caixa baixa · alinhado à esq · entrelinha 1.05
  - `3` **Texto de apoio / CTA** · x=90 y=470 770×150 — Acumin Cond. SemiBold · 62px · branco/creme · 2 linhas · gap 70px do título
  - `4` **Asset de comida (grafismo composto: peixe)** · x=40 y=760 1000×520 — faca terracota (corpo) + triângulo branco (cauda) + semicírculo amarelo + ponto branco (olho)
  - `5` **Logo VB Gastronomia (recomendado)** · x=90 y=1240 360×70 — assinatura horizontal · creme · largura 360px · canto inferior-esquerdo

## 02 · FEED · PHOTO — Foto protagonista + assinatura
- **Canvas:** 1080×1350 px · fundo `branco`
- **Uso:** A comida ocupa todo o quadro; grafismos no canto e logo VB sobre área clara.
- **Zonas (px):**
  - `BG` Foto — full bleed (comida, luz natural, fundo neutro)
  - `2` **Cluster de grafismos** · x=40 y=150 250×300 — garfo (4 pinceladas) + semicírculo + círculo, todos terracota · canto sup-esq
  - `3` **Logo VB (símbolo)** · x=760 y=820 190×150 — símbolo VB · preto (foto clara) · ~150px de largura · centro-direita sobre área lisa

## 03 · FEED · PHOTO+TEXT — Informativo (texto + foto emoldurada)
- **Canvas:** 1080×1350 px · fundo `creme`
- **Uso:** Dica/bastidor: título destacado, foto emoldurada à esquerda e texto vertical de apoio.
- **Zonas (px):**
  - `BG` Background — creme #EAE0D3
  - `2` **Título destacado** · x=90 y=110 620×190 — Acumin Cond. Medium · 76px · vinho #71140D · caixa baixa · 2 linhas
  - `3` **Foto emoldurada (retângulo)** · x=90 y=370 560×760 — recorte vertical · alinhada à margem esq · ~52% da largura
  - `4` **Texto de apoio — vertical** · x=690 y=360 70×760 — Acumin Cond. Light · 40px · oliva · rotacionado 90° · à direita da foto
  - `5` **Grafismo de acento** · x=770 y=1150 250×150 — garfo (4 pinceladas) laranja · canto inferior-direito

## 04 · STORY · SOLID — Institucional sobre cor + padrão
- **Canvas:** 1080×1920 px · fundo `terracota`
- **Uso:** Mensagem institucional + CTA sobre terracota, rematada por faixa de grafismos no rodapé.
- **Zonas (px):**
  - `BG` Background — terracota #C68B71
  - `2` **Header — réguas + logo VB + @handle** · x=70 y=70 940×130 — 3 réguas finas no topo · símbolo VB ~120px · 'vb_gastronomia' Acumin Cond. Medium 40px branco
  - `3` **Título institucional** · x=430 y=290 580×380 — Acumin Cond. Light · 70px · creme · caixa baixa · alinhado à direita · 5 linhas
  - `4` **CTA** · x=430 y=720 580×150 — Acumin Cond. Light · 60px · creme claro · 2 linhas
  - `5` **Logo VB Gastronomia (grande)** · x=70 y=980 440×110 — assinatura horizontal · creme · ~440px · meio-esquerda
  - `6` **Faixa de grafismos (padrão)** · x=0 y=1160 1080×660 — padrão denso multi-linha: pinceladas, círculos cheios pretos, anéis vinho, semicírculos, triângulo vinho, oval amarelo contornado

## 05 · STORY · PHOTO — Cardápio / mesa posta
- **Canvas:** 1080×1920 px · fundo `branco`
- **Uso:** Mesa posta vista de cima ocupa o quadro; marca no topo e grafismos no rodapé.
- **Zonas (px):**
  - `BG` Foto — full bleed (flat lay, mesa posta)
  - `2` **Header — réguas + logo VB + @handle** · x=70 y=70 520×120 — símbolo VB ~110px (branco) + handle · canto sup-esq sobre a foto
  - `3` **Logo VB Gastronomia (grande)** · x=640 y=230 370×150 — assinatura vertical · preto · sup-direita sobre área lisa da foto
  - `4` **Grafismos de rodapé** · x=70 y=1650 940×220 — garfo (triângulos) preto + círculo laranja + faca preto · linha inferior

## 06 · STORY · PHOTO+TEXT — Manifesto + prato
- **Canvas:** 1080×1920 px · fundo `creme`
- **Uso:** Texto-manifesto no topo, prato emoldurado embaixo e grafismos soltos à direita.
- **Zonas (px):**
  - `BG` Background — creme #EAE0D3
  - `2` **Header — réguas + logo VB + @handle** · x=70 y=70 520×120 — símbolo VB ~110px (preto) + 'vb_gastronomia' 40px
  - `3` **Texto-manifesto** · x=70 y=330 640×420 — Acumin Cond. Medium · 64px · preto · caixa baixa · alinhado à esq · 6 linhas
  - `4` **Foto emoldurada (prato)** · x=300 y=880 560×620 — recorte retangular · centro-baixo · bowl de ramen
  - `5` **Grafismos soltos (acento)** · x=850 y=520 230×420 — faca laranja + anel oliva (cheio) + anel contornado · lado direito
  - `6` **Logo VB (símbolo)** · x=70 y=1560 150×140 — símbolo VB · preto · canto inferior-esquerdo
