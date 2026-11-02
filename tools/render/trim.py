#!/usr/bin/env python3
"""Recorta margens transparentes de PNGs (mantém um respiro) — uso: trim.py img.png [...]"""
import sys
from PIL import Image
PAD = 24
for f in sys.argv[1:]:
    im = Image.open(f).convert("RGBA")
    box = im.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    if box:
        l, t, r, b = box
        im = im.crop((max(0, l - PAD), max(0, t - PAD), min(im.width, r + PAD), min(im.height, b + PAD)))
        im.save(f, optimize=True)
        print("✓", f, im.size)
