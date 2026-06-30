# VB Gastronomia — Wireframes de Post (6 arquétipos + sistema)

> Fonte: `Wireframes_VB_Gastronomia.pdf` (8 págs). Zonas e cotas em PIXEL sobre o
> canvas. Base para construir os PostArchetype (spec data-driven) da VB, no mesmo
> motor determinístico Pillow da TODXS. Texto é renderizado no Pillow (NUNCA pelo
> modelo de imagem). Canvas: feed 1080×1350 (4:5), story 1080×1920 (9:16).

## Sistema (pág. 07)
**Paleta:** Oliva #666651 · Laranja #F95B00 · Terracota #C68B71 · Cinza #CCCCCC ·
Vinho #71140D · Creme #EAE0D3 · Preto #000000 · Amarelo #FFF15F.

**Escala tipográfica (Acumin Cond. → stand-in Barlow Cond.):**
| Uso | Peso | Tamanho / regra |
|---|---|---|
| Título / headline | Medium 500 | 64–92px · caixa baixa · esq |
| Texto de apoio / CTA | SemiBold 600 | 56–64px |
| Corpo / manifesto | Light 300 | 46–50px · entrelinha 1.18 |
| Kicker / label | SemiBold 600 | 32–36px · CAIXA ALTA · tracking +2 |
| @handle | Medium 500 | 40px |
| Logo 'VB' | serifa display (asset PNG) | nunca recriar à mão |

**Grafismos (sistema oficial, recoloríveis):** faca, garfo, colher, anel, oval/ovo,
círculo, triângulos (garfo), semicírculo (×3). *(São os 10 PNGs pretos já na KB.)*

**Regras de construção:**
- Margem segura: 90px (feed) / 70px (story). Nada fora dela.
- Contraste obrigatório (texto claro sobre escuro e vice-versa).
- Um foco por arte: ou a frase, ou a foto — nunca os dois competindo.
- Grafismo é tempero: 1 acento por arte (exceto faixa-padrão de story), no canto, sem cobrir texto/comida.
- Foto: luz natural, fundo neutro, comida protagonista. Texto entra no Pillow.
- Logo: usar PNG oficiais; recolorir pela paleta; nunca distorcer/girar/sombrear.

---

## 01 — FEED · SOLID · "Hook sobre cor sólida" (1080×1350, fundo Oliva)
Frase de identificação + convite sobre fundo chapado, grafismo de comida no terço inferior.
- **BG:** sólido oliva #666651 (full bleed).
- **2. Título/pergunta:** Acumin Cond Light 84px · creme · caixa baixa · esq · entrelinha 1.05 · **x90 y150 · 770×250**.
- **3. Apoio/CTA:** Acumin Cond SemiBold 62px · branco/creme · 2 linhas · gap 70px do título · **x90 y470 · 770×150**.
- **4. Asset de comida (peixe composto):** faca terracota (corpo) + triângulo branco (cauda) + semicírculo amarelo + ponto branco (olho) · **x40 y760 · 1000×520**.
- **5. Logo VB horizontal:** creme · largura 360px · canto inf-esq · **x90 y1240 · 360×70**.

## 02 — FEED · PHOTO · "Foto protagonista + assinatura" (1080×1350, fundo Branco/foto)
A comida ocupa todo o quadro; grafismos no canto e logo VB sobre área clara.
- **BG:** foto full bleed (comida, luz natural, fundo neutro).
- **2. Cluster de grafismos:** garfo (4 pinceladas) + semicírculo + círculo · terracota · canto sup-esq · **x40 y150 · 250×300**.
- **3. Logo VB (símbolo):** símbolo VB · preto (foto clara) · ~150px largura · centro-direita sobre área lisa · **x760 y820 · 190×150**.

## 03 — FEED · PHOTO+TEXT · "Informativo (texto + foto emoldurada)" (1080×1350, fundo Creme)
Título destacado, foto emoldurada à esquerda e texto vertical de apoio.
- **BG:** creme #EAE0D3.
- **2. Título destacado:** Acumin Cond Medium 76px · vinho #71140D · caixa baixa · 2 linhas · **x90 y110 · 620×190**.
- **3. Foto emoldurada (retângulo):** recorte vertical · alinhada à margem esq · ~52% largura · **x90 y370 · 560×760**.
- **4. Texto de apoio vertical:** Acumin Cond Light 40px · oliva · rotacionado 90° · à direita da foto · **x690 y360 · 70×760**.
- **5. Grafismo de acento:** garfo (4 pinceladas) laranja · canto inf-direito · **x770 y1150 · 250×150**.

## 04 — STORY · SOLID · "Institucional sobre cor + padrão" (1080×1920, fundo Terracota)
Mensagem institucional + CTA sobre terracota, rematada por faixa de grafismos no rodapé.
- **BG:** terracota #C68B71.
- **2. Header (réguas + logo + handle):** 3 réguas finas no topo · símbolo VB ~120px · 'vb_gastronomia' Acumin Cond Medium 40px branco · **x70 y70 · 940×130**.
- **3. Título institucional:** Acumin Cond Light 70px · creme · caixa baixa · alinhado à direita · 5 linhas · **x430 y290 · 580×380**.
- **4. CTA:** Acumin Cond Light 60px · creme claro · 2 linhas · **x430 y720 · 580×150**.
- **5. Logo VB grande (horizontal):** creme · ~440px · meio-esquerda · **x70 y980 · 440×110**.
- **6. Faixa de grafismos (padrão):** padrão denso multi-linha (pinceladas, círculos cheios pretos, anéis vinho, semicírculos, triângulo vinho, oval amarelo contornado) · **x0 y1160 · 1080×660**.

## 05 — STORY · PHOTO · "Cardápio / mesa posta" (1080×1920, fundo Branco/foto)
Mesa posta vista de cima ocupa o quadro; marca no topo e grafismos no rodapé.
- **BG:** foto full bleed (flat lay, mesa posta).
- **2. Header:** símbolo VB ~110px (branco) + handle · canto sup-esq sobre a foto · **x70 y70 · 520×120**.
- **3. Logo VB grande (vertical):** preto · sup-direita sobre área lisa da foto · **x640 y230 · 370×150**.
- **4. Grafismos rodapé:** garfo (triângulos) preto + círculo laranja + faca preto · linha inferior · **x70 y1650 · 940×220**.

## 06 — STORY · PHOTO+TEXT · "Manifesto + prato" (1080×1920, fundo Creme)
Texto-manifesto no topo, prato emoldurado embaixo e grafismos soltos à direita.
- **BG:** creme #EAE0D3.
- **2. Header:** símbolo VB ~110px (preto) + 'vb_gastronomia' 40px · **x70 y70 · 520×120**.
- **3. Texto-manifesto:** Acumin Cond Medium 64px · preto · caixa baixa · esq · 6 linhas · **x70 y330 · 640×420**.
- **4. Foto emoldurada (prato):** recorte retangular · centro-baixo · bowl de ramen · **x300 y880 · 560×620**.
- **5. Grafismos soltos (acento):** faca laranja + anel oliva (cheio) + anel contornado · lado direito · **x850 y520 · 230×420**.
- **6. Logo VB (símbolo):** preto · canto inf-esq · **x70 y1560 · 150×140**.

---

## Mapa arquétipo → referência (já na KB)
01→VB Feed Tipográfico+peixe · 02→VB Feed Foto+grafismos · 03→VB Feed Foto emoldurada+título ·
04→VB Story Tipográfico+grafismos · 05→VB Story Foto full-bleed · 06→VB Story Texto+foto emoldurada.

## Capacidades NOVAS que o motor precisa (vs TODXS)
1. **Grafismos compostos/cluster** com cor por peça (ex.: peixe = faca terracota + triângulo branco + semicírculo amarelo + ponto; cluster garfo+semicírculo+círculo).
2. **Recolor por peça** a partir dos 10 grafismos PNG pretos (multiply/tint pela paleta).
3. **Faixa de grafismos (padrão)** denso multi-linha (story 04).
4. **Texto rotacionado 90°** (feed 03).
5. **Símbolo "VB" (monograma)** como asset — NÃO está na pasta de logos (lá só há lockups Horizontal/Vertical). Precisa do PNG do símbolo isolado.
6. **Renderizador org-agnóstico**: hoje é TODXS-specific (fontes/assets fixos). Generalizar p/ ler fontes/logo/grafismo da KB da org + spec do PostArchetype.
