# Receitas e método de decomposição

## Método: como quebrar um objeto em peças da marca

Olhe a silhueta do objeto e separe em três camadas, nesta ordem:

1. **Corpo (1 peça de carimbo).** A massa principal. Escolha uma forma de carimbo
   que já tenha o formato aproximado — `faca` para corpos alongados (peixe,
   folha, pétala), `ovo`/`colher` para corpos arredondados, `circulo` para
   frutos. O carimbo dá textura e "vida" à figura.

2. **Apêndices (triângulos).** Tudo que se projeta: nadadeiras, folhas, bicos,
   raios, fatias. Triângulos limpos contrastam com a textura do corpo. Gire-os
   para criar movimento.

3. **Detalhes (círculos / semicírculos / anéis).** Olho, gema, reflexo, semente,
   escama. Poucos e pequenos — são o toque final.

Regras do método:
- **3 a 7 peças no total.** Se passou, simplifique.
- **Cor por função:** corpo numa cor; apêndices em 1–2 cores; um acento (amarelo/
  laranja) num detalhe. Sempre dentro da paleta.
- **z-order:** apêndices que saem por trás do corpo vêm **antes** dele na lista;
  detalhes sobre o corpo vêm **depois**.
- **Movimento:** posicione o corpo numa diagonal; alinhe os apêndices a ela.

---

## Peixe (referência) — `assets/exemplos/peixe.json`

Canvas 1080×760. O corpo "nada" na diagonal (cabeça em cima-direita).

| # | peça | papel | cor | nota |
|---|------|-------|-----|------|
| 1 | triangulo (base 118 × alt 290, rot 200) | nadadeira peitoral | terracota | sai por trás do corpo, aponta à esquerda |
| 2 | triangulo (alt 225, rot 237) | cauda ventral | amarelo | bifurcada (2 triângulos) |
| 3 | triangulo (alt 175, rot 252) | cauda ventral | amarelo | segundo da bifurcação |
| 4 | asset `faca` (escala 1.15, rot 118) | corpo | terracota | textura de carimbo = dorso |
| 5 | triangulo (base 104 × alt 180, rot 183) | nadadeira dorsal | creme | sobre o corpo |
| 6 | circulo (r 24) | olho | branco | na cabeça (cima-direita) |

Leitura do estilo: um corpo de carimbo + quatro triângulos + um círculo. Síntese
total, contraste carimbo/geometria, diagonal viva, paleta terracota+amarelo+creme.

## Ovo — `assets/exemplos/ovo.json`

Canvas 600×600. Duas peças: `oval` branco (clara, levemente inclinada) + `circulo`
amarelo (gema) deslocado do centro. Exemplo de figura mínima (2 peças).

## Tomate — `assets/exemplos/tomate.json`

Canvas 600×600. `circulo` terracota (fruto) + três `triangulo` oliva (folhas
apontando para fora, no topo) + um `circulo` laranja pequeno (reflexo). Mostra o
padrão corpo→apêndices→detalhe com cor por função.

---

## Ideias para novas figuras (mesma lógica)

- **Folha / erva:** `faca` verde-oliva como lâmina + `garfo_s` (triângulos) como nervuras/brotos.
- **Pão:** `meia_dir` (semicírculo) creme como corpo + pequenos `triangulo` para os cortes.
- **Limão:** `oval` amarelo + `triangulo` oliva (folha) + `anel` para o corte.
- **Talher decorativo:** `faca` + `garfo` lado a lado, em preto, como selo.
- **Sol / prato quente:** `circulo` laranja + `garfo_s`/triângulos ao redor como raios.

Em todos: comece pela receita mais próxima em `assets/exemplos/`, troque as peças
e ajuste `cor`, `cx`/`cy`, `rot` e escala. Renderize, compare com os princípios de
`estilo.md`, refine.
