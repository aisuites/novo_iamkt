# Vocabulário de peças e esquema do JSON

Uma ilustração é um JSON com `canvas`, `bg` opcional e uma lista `pecas`. A
**ordem na lista é o z-order**: a primeira peça fica mais ao fundo, a última por
cima. Renderize com `python scripts/illustrate.py figura.json -o saida.png`.

```json
{
  "canvas": [1080, 760],
  "bg": "transparent",
  "output": "peixe.png",
  "pecas": [ /* ... */ ]
}
```

`bg`: `"transparent"` (padrão) ou um nome/hex da paleta para fundo chapado.
Coordenadas em px no `canvas`. `cx`,`cy` é sempre o **centro** da peça.

## Assets (formas de carimbo — textura da marca)

Vêm de `assets/grafismos/` (masters em alpha preto, recoloríveis).

```json
{"tipo":"asset","nome":"faca","cor":"terracota","cx":690,"cy":300,
 "escala":1.15,"rot":118,"flip_h":false,"flip_v":false}
```

| `nome` | forma | costuma virar |
|--------|-------|---------------|
| `faca` | pincelada texturizada, afina numa ponta | corpo, lâmina, folha longa, pétala |
| `garfo` | 4 pinceladas paralelas | cauda, raios, grama, cabelo, cílios |
| `garfo_s` | 4 triângulos finos | folhas, espinhos, coroa, raios limpos |
| `colher` | oval vazado (contorno carimbo) | corpo arredondado vazado, aro orgânico |
| `anel` | círculo vazado | olho, bolha, aro, fruta em corte |
| `circulo` | círculo cheio | fruto, prato, bolha (versão carimbo) |
| `ovo` | oval/gota cheia | corpo, grão, semente, gota |
| `meia_dir` / `meia_esq` | semicírculo (carimbo) | escama, concha, fatia, sol |

`escala` 1.0 = tamanho original do asset. `rot` em graus (anti-horário).
`flip_h`/`flip_v` espelham antes de girar.

## Primitivas (formas geométricas limpas)

Desenhadas com bordas exatas (anti-aliased). `rot` em graus, anti-horário.

```json
{"tipo":"triangulo","cor":"amarelo","cx":295,"cy":545,"base":66,"altura":225,"rot":237}
```
- **triangulo** — isósceles. `base` (lado largo) × `altura` (comprimento da ponta).
  Por padrão aponta para a direita; use `rot` ou `"aponta":"right|left|up|down"`.
- **circulo** — `r`.
- **semicirculo** — `r`; lado reto à direita por padrão, gire com `rot`.
- **oval** — `rx`, `ry`; `"vazado":true` + `"espessura":40` faz um aro.
- **retangulo** — `w`, `h`.

Exemplos:
```json
{"tipo":"circulo","cor":"branco","cx":858,"cy":206,"r":24}
{"tipo":"oval","cor":"branco","cx":300,"cy":320,"rx":175,"ry":150,"rot":-12}
{"tipo":"oval","cor":"oliva","cx":860,"cy":520,"rx":90,"ry":90,"vazado":true,"espessura":34}
{"tipo":"semicirculo","cor":"terracota","cx":400,"cy":300,"r":120,"rot":180}
{"tipo":"retangulo","cor":"oliva","cx":300,"cy":480,"w":24,"h":160,"rot":0}
```

## Orientação (dica prática de `rot`)

`rot` é anti-horário. Para um asset "em pé" (eixo vertical, ponta para cima):
o eixo visual resultante ≈ `90 − rot`. Ex.: para a faca apontar para cima-direita
(≈ −28°), use `rot ≈ 118`. Quando em dúvida, renderize, olhe e ajuste em passos
de ~15°.

## Cores

Qualquer `cor` aceita nome da paleta (`"terracota"`) ou hex (`"#C68B71"`).
Assets são recoloridos a partir do alpha; primitivas são preenchidas direto.
