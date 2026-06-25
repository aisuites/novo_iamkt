# TODXS — Especificação de marca

Fonte: *Manual da Marca TODXS* (Colletivo Design) + *Apresentação Completa 2023*.
Use este arquivo como verdade absoluta sobre cor, tipografia, grafismo e foto.
A estética geral é **editorial**, inspirada no jornal LGBTQIA+ *Lampião da Esquina*
(anos 70): tipografia protagonista, contraste de peso/escala, chamadas fortes,
releitura contemporânea e sistematizada.

---

## 1. Paleta de cores

São as cores oficiais — releitura da bandeira LGBTQIA+. As cores principais
**compartilham protagonismo** (nenhuma é "a cor da marca"). O off-white é cor de
**apoio**, usada para texto e áreas de respiro.

| Cor | HEX | RGB | CMYK | Pantone |
|-----|-----|-----|------|---------|
| Vermelho | `#ED2E26` | 237 / 46 / 38 | 0 / 95 / 95 / 0 | 3556 C |
| Laranja | `#FF6B06` | 255 / 97 / 6 | 0 / 72 / 98 / 0 | 1505 C |
| Amarelo | `#F5D938` | 245 / 217 / 56 | 5 / 10 / 90 / 0 | 7404 C |
| Verde | `#35D386` | 53 / 211 / 134 | 57 / 0 / 61 / 0 | 7479 C |
| Azul | `#0E82E9` | 14 / 130 / 233 | 75 / 35 / 0 / 0 | 2382 C |
| Roxo | `#8B11EA` | 139 / 17 / 234 | 64 / 82 / 0 / 0 | 266 C |
| Rosa | `#F2A8FD` | 242 / 168 / 253 | 5 / 35 / 0 / 0 | 243 C |
| Marrom | `#83501D` | 131 / 80 / 29 | 35 / 65 / 100 / 30 | 6013 C |
| Preto | `#000000` | 0 / 0 / 0 | 40 / 30 / 30 / 100 | Black 6 C |
| Off-white (apoio) | `#F4F1D9` | 244 / 241 / 217 | 4 / 2 / 16 / 0 | White |

### Regras de uso da cor (rígidas)
- **Sempre combinar com o preto.** O preto garante contraste e unidade. Em cada
  peça use, em geral, **uma cor principal + preto + off-white** (texto/respiro).
- O **preto pode ser fundo**, criando campos de respiro que valorizam as cores;
  nesse caso o **off-white é o texto**.
- **NUNCA** usar gradiente (em nenhuma cor, prevista ou não).
- **NUNCA** usar branco puro (`#FFFFFF`) como fundo — o "claro" da marca é o off-white.
- **NUNCA** usar cores fora desta paleta.
- **NUNCA** modificar a hierarquia (não inventar "cor dominante").
- Combinações válidas: cor chapada + tipografia preta; preto + texto off-white;
  cor chapada + texto off-white; foto duotone numa cor da paleta + preto.

---

## 2. Tipografia

Duas famílias. A hierarquia tipográfica é **o principal elemento de construção
visual** da marca — a informação é a protagonista.

### Ana Banana (Motora, 2021) — títulos e destaques
Tipografia variável, 9 pesos. Personalidade marcante. Características:
**inktraps profundos**, **terminações em "boca de sino"**, **counters
"sorridentes"** (contraformas arredondadas e simpáticas). Pesos leves dão
legibilidade; pesos pesados (Black) dão impacto.

### Vinila (Flora de Carvalho) — corpo e subtítulos
Grotesca contemporânea. 4 larguras (Comprimida → Condensada → Regular →
Expandida), 6 pesos + oblíquas. Desenho dinâmico, inspirado em ritmo e música.

### Mapa de hierarquia (use sempre assim)
| Papel | Fonte | Peso/largura | Caixa |
|-------|-------|--------------|-------|
| Manchete / título principal | **Ana Banana** | Black | ALTA |
| Subtítulo | **Vinila** | Compressed Regular | ALTA |
| Pequeno destaque / label / seção (eyebrow) | **Vinila** | Condensed Light | ALTA |
| Texto médio (destaque secundário) | **Ana Banana** | Regular | normal |
| Bloco de texto extenso / corpo | **Vinila** | Regular | normal |

> Em geração single-shot, o modelo **não terá as fontes reais**. Descreva o
> *estilo* (ver `prompt-templates.md` → "Descrevendo a tipografia sem a fonte").
> Se a fidelidade tipográfica for crítica, esse é o gatilho para migrar para o
> fluxo de compositing (fundo gerado + texto via Pillow).

---

## 3. Grafismo do "X"

O "X" do logotipo (formado por **quatro pétalas/folhas arredondadas que se
encontram no centro**, como um cata-vento/borboleta de 4 lobos) se desdobra em
elemento gráfico da identidade:

- **Uso principal: máscara para fotografia.** Recorta a foto em forma de X/pétala,
  reforçando a presença da marca e criando uma linguagem proprietária.
- **Blobs orgânicos:** as pétalas ampliadas viram formas/manchas chapadas que
  invadem o layout (vistas como blobs nos stories).
- **Selo X:** círculo **preto** com o X colorido dentro — marcador no topo dos posts.
- **Marcação sutil** em layouts e, em peças promocionais, em **escala ampliada com
  enquadramento extrapolado** (ousado, saindo da margem).
- **Rotação:** sempre em múltiplos de **45°**, em qualquer direção.

---

## 4. Direcionamento fotográfico

- **Quem:** pessoas LGBTQIA+ **diversas** (raça, corpo, idade, expressão de gênero).
  Protagonismo e representatividade reais.
- **Contextos:** dia a dia, trabalho, e **história** (fotos históricas da comunidade,
  conectando passado e presente).
- **Enquadramento:** planos mais fechados — **plano americano**, retrato — valorizando
  presença e expressão.
- **Tratamentos** (escolher conforme intenção da peça):
  1. **Colorida** — reforça o aspecto vibrante.
  2. **Preto e branco** — composições sóbrias e atemporais.
  3. **P&B + cor chapada por cima (duotone / multiply)** — usa **uma cor da paleta**
     sobre a foto P&B; adiciona camada gráfica mantendo a leitura original. É o
     tratamento mais "de marca" e o preferido para fundos full-bleed.

---

## 5. Don'ts do logo
Não distorcer · não aplicar contornos · não reposicionar elementos · não usar
outras cores · não mudar o desenho do "X" · **não rotacionar o logotipo** (só o
grafismo solto pode girar, em 45°) · não aplicar sobre imagens com muita informação
· não aplicar sobre fundos de baixo contraste · não adicionar novos elementos.

Área de proteção = largura do "X". Redução mínima da assinatura: 200 px (digital).
