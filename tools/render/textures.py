#!/usr/bin/env python3
"""Gerbers → texturas realistas (topo/base) para README e para o modelo 3D.

1. gerbonara renderiza os Gerbers em SVG (cobre, máscara, serigrafia, furos)
2. rsvg-convert rasteriza em alta resolução (px/mm configurável)
3. pós-processamento: pads em ouro (ENIG), furos e exterior transparentes,
   contorno recortado exatamente no retângulo de cantos arredondados.

Uso: python3 textures.py <dir_gerbers> <largura_mm> <altura_mm> <raio_mm> <saida_prefixo> [px_por_mm]
"""
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

SUBSTRATE = np.array([28, 92, 58])     # verde da máscara sobre o laminado


def render_side(gerbers: Path, side: str, w, h, r, ppm) -> Image.Image:
    with tempfile.TemporaryDirectory() as td:
        svg = Path(td) / f"{side}.svg"
        png = Path(td) / f"{side}.png"
        subprocess.run(["gerbonara", "render", "--warnings", "ignore", f"--{side}", str(gerbers), str(svg)],
                       check=True, capture_output=True)
        # o SVG inclui 0,05 mm de margem em cada lado (contorno de 0,1 mm)
        W = int(round((w + 0.1) * ppm))
        subprocess.run(["rsvg-convert", "-w", str(W), str(svg), "-o", str(png)], check=True)
        im = Image.open(png).convert("RGBA")
    m = int(round(0.05 * ppm))
    im = im.crop((m, m, m + int(w * ppm), m + int(h * ppm)))
    return im


def grade(im: Image.Image, w, h, r, ppm) -> Image.Image:
    a = np.asarray(im).astype(np.float32)
    rgb, alpha = a[..., :3], a[..., 3]
    mx, mn = rgb.max(-1), rgb.min(-1)
    sat = mx - mn
    v = rgb.mean(-1)

    # máscara do contorno (retângulo arredondado exato)
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, im.size[0] - 1, im.size[1] - 1], radius=r * ppm, fill=255)
    inside = np.asarray(mask) > 127

    out = rgb.copy()
    # substrato: tom de verde mais profundo
    sub = (np.abs(rgb - [51, 99, 51]).sum(-1) < 18)
    out[sub] = SUBSTRATE
    # cobre sob máscara (overlay verde translúcido do gerbonara) → verde levemente mais claro
    cu = (alpha < 250) & (alpha > 150) & (rgb[..., 1] > rgb[..., 0] + 30)
    out[cu] = SUBSTRATE * 1.22
    # pads (cinza HASL) → ouro ENIG
    #   153 = pads SMD (pasta), 204 = cobre exposto (THT, vias, pontos de teste)
    pad = (sat < 14) & (v > 110) & (v < 214)
    k = (0.92 + 0.12 * (v[pad] - 153.0) / 51.0)[:, None]
    out[pad] = np.clip(np.array([214, 172, 72]) * k, 0, 255)
    # serigrafia (224) → branco quente
    silk = (sat < 14) & (v >= 214) & (v < 250)
    out[silk] = [240, 240, 232]
    # furos → transparentes
    hole = (sat < 10) & (v > 35) & (v < 70)
    # canto mal reconstruído pelo renderizador: branco dentro do contorno → substrato
    white = (v >= 250) & inside
    out[white] = SUBSTRATE

    A = np.where(inside & ~hole, 255, 0).astype(np.uint8)
    res = np.dstack([np.clip(out, 0, 255).astype(np.uint8), A])
    return Image.fromarray(res, "RGBA")


def main():
    gerbers, w, h, r, prefix = Path(sys.argv[1]), *map(float, sys.argv[2:5]), sys.argv[5]
    ppm = float(sys.argv[6]) if len(sys.argv) > 6 else 40
    for side in ("top", "bottom"):
        im = grade(render_side(gerbers, side, w, h, r, ppm), w, h, r, ppm)
        out = f"{prefix}-{side}.png"
        im.save(out, optimize=True)
        print("✓", out, im.size)


if __name__ == "__main__":
    main()
