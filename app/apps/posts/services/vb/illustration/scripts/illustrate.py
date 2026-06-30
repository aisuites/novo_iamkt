#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
illustrate.py — Compositor de ILUSTRAÇÕES da VB Gastronomia.

Monta figuras (peixe, tomate, folha, ovo…) recombinando o vocabulário gráfico da
marca: grafismos-carimbo (faca, garfo, colher, anel, oval…) + primitivas
geométricas (triângulo, círculo, semicírculo, oval, retângulo). Tudo flat, cores
chapadas da paleta, sem sombra nem gradiente — o "traço gráfico" da marca.

Cada peça é um dicionário com z-order = ordem na lista (primeira = mais ao fundo).
A saída é um PNG com fundo transparente (ou cor), pronto para entrar num post.

Uso:
    python illustrate.py figura.json -o peixe.png

Esquema de peça:
  asset:       {"tipo":"asset","nome":"faca","cor":"terracota","cx":,"cy":,
                "escala":1.0,"rot":0,"flip_h":false,"flip_v":false}
  triângulo:   {"tipo":"triangulo","cor":"amarelo","cx":,"cy":,"base":,"altura":,
                "rot":0,"aponta":"right"}   # aponta: right|left|up|down (açúcar p/ rot)
  círculo:     {"tipo":"circulo","cor":"branco","cx":,"cy":,"r":}
  semicírculo: {"tipo":"semicirculo","cor":"terracota","cx":,"cy":,"r":,"rot":0}
  oval:        {"tipo":"oval","cor":"preto","cx":,"cy":,"rx":,"ry":,"rot":0,
                "vazado":false,"espessura":40}
  retângulo:   {"tipo":"retangulo","cor":"oliva","cx":,"cy":,"w":,"h":,"rot":0}
"""
from __future__ import annotations
import argparse, json, math, os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GRAFS = os.path.join(ROOT, "assets", "grafismos")
SS = 4  # supersampling p/ bordas limpas

PALETTE = {
    "oliva":"#666651","laranja":"#F95B00","terracota":"#C68B71","cinza":"#CCCCCC",
    "vinho":"#71140D","creme":"#EAE0D3","preto":"#111111","amarelo":"#FFF15F",
    "branco":"#FFFFFF","transparent":None,
}
APONTA = {"right":0, "up":90, "left":180, "down":270}


def hex2rgb(c):
    if isinstance(c,(list,tuple)): return tuple(c[:3])
    c = PALETTE.get(c, c)
    if c is None: return None
    c = c.lstrip("#")
    return tuple(int(c[i:i+2],16) for i in (0,2,4))


def recolor(img, color):
    rgb = hex2rgb(color)
    img = img.convert("RGBA"); a = img.split()[3]
    solid = Image.new("RGBA", img.size, rgb+(255,)); solid.putalpha(a)
    return solid


def _tile(w, h):
    return Image.new("RGBA", (max(1,int(w)), max(1,int(h))), (0,0,0,0))


def _rotate_paste(base, tile, cx, cy, rot):
    if rot:
        tile = tile.rotate(rot, expand=True, resample=Image.BICUBIC)
    base.alpha_composite(tile, (int(cx*SS - tile.width/2), int(cy*SS - tile.height/2)))


def draw_asset(base, p):
    fn = p["nome"] if p["nome"].startswith("graf_") else f"graf_{p['nome']}.png"
    img = Image.open(os.path.join(GRAFS, fn)).convert("RGBA")
    img = recolor(img, p.get("cor","preto"))
    if p.get("flip_h"): img = img.transpose(Image.FLIP_LEFT_RIGHT)
    if p.get("flip_v"): img = img.transpose(Image.FLIP_TOP_BOTTOM)
    esc = p.get("escala",1.0) * SS
    img = img.resize((max(1,int(img.width*esc)), max(1,int(img.height*esc))), Image.LANCZOS)
    _rotate_paste(base, img, p["cx"], p["cy"], p.get("rot",0))


def draw_triangulo(base, p):
    b, h = p["base"]*SS, p["altura"]*SS
    tile = _tile(h+2, b+2)               # aponta p/ direita: comprimento=h, base=b
    d = ImageDraw.Draw(tile)
    d.polygon([(0,0),(0,b),(h,b/2)], fill=hex2rgb(p["cor"])+(255,))
    rot = p.get("rot", APONTA.get(p.get("aponta","right"),0))
    _rotate_paste(base, tile, p["cx"], p["cy"], rot)


def draw_circulo(base, p):
    r = p["r"]*SS
    tile = _tile(2*r+2, 2*r+2); d = ImageDraw.Draw(tile)
    d.ellipse([1,1,2*r,2*r], fill=hex2rgb(p["cor"])+(255,))
    _rotate_paste(base, tile, p["cx"], p["cy"], p.get("rot",0))


def draw_semicirculo(base, p):
    r = p["r"]*SS
    tile = _tile(2*r+2, 2*r+2); d = ImageDraw.Draw(tile)
    # meia-lua com lado reto à direita (igual grafismo oficial)
    d.pieslice([1,1,2*r,2*r], 90, 270, fill=hex2rgb(p["cor"])+(255,))
    _rotate_paste(base, tile, p["cx"], p["cy"], p.get("rot",0))


def draw_oval(base, p):
    rx, ry = p["rx"]*SS, p["ry"]*SS
    tile = _tile(2*rx+2, 2*ry+2); d = ImageDraw.Draw(tile)
    col = hex2rgb(p["cor"])+(255,)
    if p.get("vazado"):
        w = int(p.get("espessura",40)*SS)
        d.ellipse([1,1,2*rx,2*ry], fill=col)
        d.ellipse([1+w,1+w,2*rx-w,2*ry-w], fill=(0,0,0,0))
    else:
        d.ellipse([1,1,2*rx,2*ry], fill=col)
    _rotate_paste(base, tile, p["cx"], p["cy"], p.get("rot",0))


def draw_retangulo(base, p):
    w, h = p["w"]*SS, p["h"]*SS
    tile = _tile(w+2, h+2); d = ImageDraw.Draw(tile)
    d.rectangle([1,1,w,h], fill=hex2rgb(p["cor"])+(255,))
    _rotate_paste(base, tile, p["cx"], p["cy"], p.get("rot",0))


DRAW = {"asset":draw_asset, "triangulo":draw_triangulo, "circulo":draw_circulo,
        "semicirculo":draw_semicirculo, "oval":draw_oval, "retangulo":draw_retangulo}


def render(cfg, out=None):
    W, H = cfg.get("canvas", [1080,1080])
    base = Image.new("RGBA", (W*SS, H*SS), (0,0,0,0))
    bgc = cfg.get("bg")
    if bgc and bgc != "transparent":
        base = Image.new("RGBA", (W*SS, H*SS), hex2rgb(bgc)+(255,))
    for p in cfg["pecas"]:
        DRAW[p["tipo"]](base, p)
    base = base.resize((W, H), Image.LANCZOS)
    out = out or cfg.get("output","ilustracao.png")
    base.save(out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("-o","--output", default=None)
    a = ap.parse_args()
    cfg = json.load(open(a.config, encoding="utf-8"))
    print("✔", render(cfg, a.output))


if __name__ == "__main__":
    main()
