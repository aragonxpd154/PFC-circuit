#!/usr/bin/env python3
"""Confere o netlist exportado pelo KiCad contra designs.py.

Uso: python3 verify_netlist.py <arquivo.net> card|jig
Sai com código 1 se houver qualquer divergência.
"""
import sys

from designs import CARD_PARTS, JIG_PARTS, nets_of
from sexpr import find, find_all, parse


def kicad_nets(path):
    tree = parse(open(path, encoding="utf-8").read())
    out = {}
    for net in find_all(find(tree, "nets"), "net"):
        name = find(net, "name")[1].lstrip("/")
        nodes = sorted(f"{find(n, 'ref')[1]}.{find(n, 'pin')[1]}" for n in find_all(net, "node"))
        nodes = [n for n in nodes if not n.startswith("#")]
        if name.startswith("unconnected-") or not nodes:
            continue
        out[name] = nodes
    return out


def main():
    path, which = sys.argv[1], sys.argv[2]
    parts = CARD_PARTS if which == "card" else JIG_PARTS
    want = {k: sorted(v) for k, v in nets_of(parts).items()}
    got = kicad_nets(path)
    errors = 0
    for name in sorted(set(want) | set(got)):
        if want.get(name) != got.get(name):
            errors += 1
            print(f"✗ {name}\n   esperado: {want.get(name)}\n   kicad   : {got.get(name)}")
    n_pins = sum(len(v) for v in want.values())
    if errors:
        print(f"FALHA: {errors} redes divergentes")
        sys.exit(1)
    print(f"✓ {which}: {len(want)} redes / {n_pins} conexões idênticas ao designs.py")


if __name__ == "__main__":
    main()
