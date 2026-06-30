---
name: vb-gastronomia-ilustracoes
description: >
  Cria ilustrações no traço gráfico da VB Gastronomia recombinando os assets da
  marca — grafismos-carimbo (faca, garfo, colher, anel, oval) + primitivas
  geométricas (triângulo, círculo, semicírculo, oval) — em figuras flat e
  sintéticas (peixe, ovo, tomate, folha, pão, talher…). Use SEMPRE que o pedido
  envolver "ilustração", "desenho", "figura", "ícone ilustrado", "grafismo
  composto", "traço gráfico" ou "bichinho/comida feita com as formas da marca"
  para a VB Gastronomia, inclusive quando a pessoa mostrar uma figura existente
  (como o peixe) e pedir "outra nesse estilo" ou "monta isso com os assets da
  marca". Não é para posts inteiros (use a skill de posts) nem para fotos — é
  para o desenho vetorial/flat em si, entregue como PNG transparente.
---

# VB Gastronomia — Ilustrações modulares

A marca tem um sistema de ilustração: figuras são **montadas a partir de poucas
peças** do vocabulário gráfico — formas de carimbo (orgânicas, texturizadas) +
primitivas geométricas (limpas) — sempre flat, em cores chapadas da paleta. O
peixe é o caso de referência: corpo = pincelada *faca* terracota, nadadeiras =
triângulos, olho = círculo. Esta skill ensina a decompor um objeto nessas peças
e a renderizar a ilustração de forma determinística.

## Pipeline

1. **Decompor o objeto em peças.** Olhe a silhueta e pergunte: qual o *corpo*
   (uma forma de carimbo dá textura e vida), quais os *apêndices* (triângulos),
   quais os *detalhes* (círculos, semicírculos). Mire em **3 a 7 peças** — a
   marca é síntese, não realismo. Método completo em `references/receitas.md`.

2. **Definir a paleta da figura.** 2 a 4 cores da marca, com um acento. Ver
   `references/estilo.md`.

3. **Montar a receita** (JSON com a lista de peças; a ordem é o z-order, primeira
   = mais ao fundo). Tipos e parâmetros em `references/vocabulario.md`.

4. **Renderizar:**
   ```bash
   python scripts/illustrate.py figura.json -o figura.png
   ```
   Saída: PNG transparente (ou com `bg`), pronto para entrar num post.

5. **Revisar** contra os princípios de estilo (flat, síntese, carimbo+geometria,
   composição diagonal, contraste de formas). Ajustar e re-renderizar.

## Vocabulário de peças (resumo)

| tipo | origem | costuma virar |
|------|--------|---------------|
| `asset` faca | grafismo-carimbo | corpo, folha, pétala, lâmina |
| `asset` garfo | grafismo-carimbo | cauda, raios, cabelo, grama |
| `asset` colher/oval | grafismo-carimbo | corpo arredondado, grão, semente |
| `asset` anel | grafismo-carimbo | olho, bolha, aro, fruta vazada |
| `triangulo` | primitiva | nadadeira, folha, bico, raio, fatia |
| `circulo` | primitiva | olho, fruto, gema, bolha, prato |
| `semicirculo` | primitiva | escama, concha, sol, fatia |
| `oval` | primitiva | corpo, ovo, grão (cheio ou vazado) |
| `retangulo` | primitiva | talo, mesa, faixa |

Toda peça aceita `cor` (paleta), `cx`/`cy`, escala/tamanho, `rot` e (assets)
`flip_h`/`flip_v`. Esquema detalhado: `references/vocabulario.md`.

## Exemplos prontos (em `assets/exemplos/`)

- `peixe.json` → `peixe.png` — caso de referência (corpo faca + 4 triângulos + olho).
- `ovo.json` → `ovo.png` — oval branco + círculo amarelo.
- `tomate.json` → `tomate.png` — círculo terracota + folhas (triângulos) + reflexo.

Comece copiando a receita mais próxima e ajustando as peças.

## Referências

- `references/estilo.md` — princípios do traço (flat, carimbo+geometria, paleta, composição, do/don't).
- `references/vocabulario.md` — catálogo de peças, parâmetros e esquema do JSON.
- `references/receitas.md` — figuras decompostas + método de decomposição passo a passo.

## Regras

- **Flat sempre:** sem sombra, sem gradiente, sem contorno — cores chapadas da paleta.
- **Síntese:** 3–7 peças. Se passou disso, está realista demais para a marca.
- **Carimbo + geometria:** misture ao menos uma forma de carimbo (textura) com
  primitivas limpas — é o contraste que dá o "traço VB".
- **Cor por função, não por realismo:** a paleta da marca vem antes da cor "real"
  do objeto (um tomate pode ser terracota; um peixe, terracota + amarelo).
- **Composição viva:** prefira eixos diagonais e contraste de tamanho entre as peças.
