#!/usr/bin/env python3
"""Exporta os arquivos de fabricação e documentação via kicad-cli (KiCad ≥ 7).

Saída por placa em hardware/<placa>/fab/:
    gerbers/ + <placa>-gerbers.zip   Gerber X2 + Excellon (pronto p/ JLCPCB/PCBWay)
    <placa>-pos.csv                  pick-and-place (face superior)
    <placa>-bom.csv                  lista de materiais agrupada
    <placa>.step                     modelo 3D completo (placa + componentes)
    <placa>-schematic.pdf            esquemático
    <placa>-assembly.pdf             desenho de montagem (F.Fab)
"""
from __future__ import annotations

import csv
import os
import shutil
import subprocess
import sys
import zipfile
from collections import OrderedDict
from pathlib import Path

from designs import CARD_PARTS, JIG_PARTS

ROOT = Path(__file__).resolve().parents[2]
ENV = dict(os.environ,
           KICAD6_3DMODEL_DIR=os.environ.get("KICAD6_3DMODEL_DIR", "/usr/share/kicad/3dmodels"),
           KICAD7_3DMODEL_DIR=os.environ.get("KICAD7_3DMODEL_DIR", "/usr/share/kicad/3dmodels"),
           KICAD7_FOOTPRINT_DIR=os.environ.get("KICAD7_FOOTPRINT_DIR", "/usr/share/kicad/footprints"))
LAYERS = "F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"


def cli(*args):
    r = subprocess.run(["kicad-cli", *args], env=ENV, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout, r.stderr)
        raise SystemExit(f"kicad-cli falhou: {' '.join(args[:3])}")


def generic(p):
    fp = p.fp.split(":")[1]
    size = fp.split("_")[1] if "_" in fp else fp
    if p.lib == "Device:R":
        return f"Resistor SMD {size} 1 %" + (" 200 V" if size == "1206" else "")
    if p.lib == "Device:C":
        return f"Capacitor cerâmico SMD {size} " + ("C0G" if p.value.endswith("p") or p.ref == "C20" else "X7R")
    if p.lib == "Device:C_Polarized":
        return f"Capacitor eletrolítico SMD {fp.replace('CP_Elec_', '')} mm"
    return p.desc


def bom(parts, path: Path):
    """BOM de compra: agrupada por valor + footprint."""
    groups: "OrderedDict[tuple, list]" = OrderedDict()
    prio = {"U": 0, "Q": 1, "D": 2, "R": 4, "C": 5, "J": 6, "T": 7, "H": 8}
    key_ref = lambda p: (prio.get(p.ref[0], 3), p.lib, p.fp, p.value)
    for p in sorted(parts, key=key_ref):
        val = "—" if p.lib in ("Connector:TestPoint", "Mechanical:MountingHole_Pad") else p.value
        groups.setdefault((val, p.fp.split(":")[1], generic(p), p.mpn), []).append(p)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Item", "Qtd", "Referências", "Valor", "Footprint", "Descrição", "MPN", "Nota"])
        for i, ((val, fp, desc, mpn), ps) in enumerate(groups.items(), 1):
            refs = sorted((p.ref for p in ps), key=lambda r: (r.rstrip("0123456789"), int("".join(c for c in r if c.isdigit()) or 0)))
            notes = sorted({p.note for p in ps if p.note})
            w.writerow([i, len(ps), " ".join(refs), val, fp, desc, mpn, " / ".join(notes)])
    # Tabela detalhada (função de cada referência)
    with path.with_name(path.stem.replace("-bom", "-parts") + ".csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Referência", "Valor", "Footprint", "Função", "Redes (pino:rede)", "Nota"])
        for p in sorted(parts, key=lambda p: (p.ref.rstrip("0123456789"), int("".join(c for c in p.ref if c.isdigit()) or 0))):
            w.writerow([p.ref, p.value, p.fp.split(":")[1], p.desc,
                        " ".join(f"{k}:{v or 'NC'}" for k, v in p.pins.items()), p.note])
    return len(groups), len(parts)


def export(name: str, parts):
    hw = ROOT / "hardware" / name
    pcb, sch = hw / f"{name}.kicad_pcb", hw / f"{name}.kicad_sch"
    fab = hw / "fab"
    if fab.exists():
        shutil.rmtree(fab)
    g = fab / "gerbers"
    g.mkdir(parents=True)

    cli("pcb", "export", "gerbers", "--layers", LAYERS, "--subtract-soldermask", "-o", f"{g}/", str(pcb))
    cli("pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th", "--generate-map",
        "--map-format", "pdf", "-o", f"{g}/", str(pcb))
    with zipfile.ZipFile(fab / f"{name}-gerbers.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(g.iterdir()):
            z.write(f, f.name)
    cli("pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "front",
        "-o", str(fab / f"{name}-pos.csv"), str(pcb))
    cli("pcb", "export", "step", "--force", "--user-origin", "100x100mm", "-o", str(fab / f"{name}.step"), str(pcb))
    cli("sch", "export", "pdf", "-o", str(fab / f"{name}-schematic.pdf"), str(sch))
    cli("pcb", "export", "pdf", "--layers", "F.Fab,Edge.Cuts", "--include-border-title",
        "-o", str(fab / f"{name}-assembly.pdf"), str(pcb))
    n_lines, n_parts = bom(parts, fab / f"{name}-bom.csv")
    print(f"✓ {name}: {len(list(g.iterdir()))} arquivos Gerber/drill, BOM {n_lines} linhas / {n_parts} itens, STEP, PDFs")


if __name__ == "__main__":
    which = sys.argv[1:] or ["card", "jig"]
    if "card" in which:
        export("psh-card1", CARD_PARTS)
    if "jig" in which:
        export("psh-jig1", JIG_PARTS)
