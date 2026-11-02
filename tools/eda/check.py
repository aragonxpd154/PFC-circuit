#!/usr/bin/env python3
"""Verificação rápida (sem rotear de novo) — usada no `make check` e no CI.

  1. esquemático → netlist (kicad-cli) == designs.py
  2. DRC das placas: 0 violações e 0 conexões pendentes
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EDA = Path(__file__).resolve().parent
os.environ.setdefault("KICAD7_FOOTPRINT_DIR", "/usr/share/kicad/footprints")
os.environ.setdefault("KICAD6_3DMODEL_DIR", "/usr/share/kicad/3dmodels")


def main():
    import pcbnew
    ok = True
    with tempfile.TemporaryDirectory() as td:
        for key, name in (("card", "psh-card1"), ("jig", "psh-jig1")):
            hw = ROOT / "hardware" / name
            net = Path(td) / f"{name}.net"
            subprocess.run(["kicad-cli", "sch", "export", "netlist", "-o", str(net), str(hw / f"{name}.kicad_sch")],
                           check=True, capture_output=True)
            r = subprocess.run([sys.executable, str(EDA / "verify_netlist.py"), str(net), key], cwd=EDA)
            ok &= r.returncode == 0
            board = pcbnew.LoadBoard(str(hw / f"{name}.kicad_pcb"))
            rpt = Path(td) / f"{name}.rpt"
            pcbnew.WriteDRCReport(board, str(rpt), pcbnew.EDA_UNITS_MILLIMETRES, True)
            t = rpt.read_text()
            v = int(re.search(r"Found (\d+) DRC violations", t).group(1))
            u = int(re.search(r"Found (\d+) unconnected pads", t).group(1))
            mark = "✓" if v == 0 and u == 0 else "✗"
            print(f"{mark} {name}.kicad_pcb: DRC {v} violações, {u} não conectados")
            ok &= v == 0 and u == 0
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
