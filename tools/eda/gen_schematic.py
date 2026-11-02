"""Gera .kicad_sch (KiCad 7) a partir de designs.py.

Estilo: cada pino recebe um pequeno fio + rótulo de rede (ou símbolo de
alimentação), e os componentes são agrupados em blocos funcionais com
moldura e legenda técnica. O resultado é um esquemático limpo e 100%
rastreável ao netlist.
"""
from __future__ import annotations

import math
from pathlib import Path

from sexpr import det_uuid, library_symbol_text, symbol_pins

ROOT = Path(__file__).resolve().parents[2]
CUSTOM = {"PFC": ROOT / "hardware" / "lib" / "PFC.kicad_sym"}
FONT = "(effects (font (size 1.27 1.27)))"
FONT_H = "(effects (font (size 1.27 1.27)) hide)"
STUB = 2.54
COLW = 50.8
ROWH = 10.16


def g(v: float) -> float:
    """Arredonda para a grade de 1,27 mm (conexões válidas no KiCad)."""
    return round(round(v / 1.27) * 1.27, 4)


def transform(px, py, sx, sy, rot):
    """Coordenada do símbolo (Y p/ cima) -> folha (Y p/ baixo), rotação CCW."""
    u, v = px, -py
    a = math.radians(rot)
    x = u * math.cos(a) + v * math.sin(a)
    y = -u * math.sin(a) + v * math.cos(a)
    return round(sx + x, 4), round(sy + y, 4)


def outward(angle, rot):
    """Direção para fora do corpo (oposta ao ângulo do pino), já rotacionada."""
    a = math.radians(angle)
    dx, dy = -math.cos(a), -math.sin(a)          # coords do símbolo
    x, y = transform(dx, dy, 0, 0, rot)
    return round(x), round(y)


class Sheet:
    def __init__(self, project: str, title: str, comments: list[str]):
        self.project = project
        self.root = det_uuid(project, "root")
        self.items: list[str] = []
        self.libs: dict[str, str] = {}
        self.pwr = 0
        self.title = title
        self.comments = comments

    # ------------------------------------------------------------ primitives
    def uid(self, *k):
        return det_uuid(self.project, *map(str, k))

    def lib(self, lib_id):
        if lib_id not in self.libs:
            self.libs[lib_id] = library_symbol_text(lib_id, CUSTOM)

    def wire(self, x1, y1, x2, y2):
        self.items.append(
            f'  (wire (pts (xy {x1} {y1}) (xy {x2} {y2})) (stroke (width 0) (type default))'
            f' (uuid {self.uid("w", x1, y1, x2, y2)}))')

    def label(self, name, x, y, d):
        ang = {(1, 0): 0, (-1, 0): 180, (0, -1): 90, (0, 1): 270}[d]
        just = "left bottom" if ang in (0, 90) else "right bottom"
        self.items.append(
            f'  (label "{name}" (at {x} {y} {ang}) (fields_autoplaced)'
            f' (effects (font (size 1.27 1.27)) (justify {just})) (uuid {self.uid("l", name, x, y)}))')

    def noconnect(self, x, y):
        self.items.append(f'  (no_connect (at {x} {y}) (uuid {self.uid("nc", x, y)}))')

    def text(self, s, x, y, size=1.27, bold=False, italic=False):
        style = (" bold" if bold else "") + (" italic" if italic else "")
        th = f" (thickness {round(size * 0.2, 3)})" if bold else ""
        s = s.replace('"', "'")
        self.items.append(
            f'  (text "{s}" (at {x} {y} 0) (effects (font (size {size} {size}){th}{style})'
            f' (justify left bottom)) (uuid {self.uid("t", s, x, y)}))')

    def rect(self, x1, y1, x2, y2):
        self.items.append(
            f'  (rectangle (start {x1} {y1}) (end {x2} {y2}) (stroke (width 0.254) (type dash))'
            f' (fill (type none)) (uuid {self.uid("r", x1, y1)}))')

    def symbol(self, lib_id, ref, value, x, y, rot=0, fp="", fields=None, hide_ref=False,
               hide_val=False, ref_xy=None, val_xy=None, dnp=False, in_bom=True):
        self.lib(lib_id)
        pins = symbol_pins(lib_id, CUSTOM)
        rx, ry = ref_xy or (x, y - 2.54)
        vx, vy = val_xy or (x, y + 2.54)
        out = [f'  (symbol (lib_id "{lib_id}") (at {x} {y} {rot}) (unit 1)',
               f'    (in_bom {"yes" if in_bom else "no"}) (on_board yes) (dnp {"yes" if dnp else "no"})',
               f'    (uuid {self.uid("s", ref)})',
               f'    (property "Reference" "{ref}" (at {rx} {ry} {rot}) {FONT_H if hide_ref else FONT})',
               f'    (property "Value" "{value}" (at {vx} {vy} {rot}) {FONT_H if hide_val else FONT})',
               f'    (property "Footprint" "{fp}" (at {x} {y} 0) {FONT_H})',
               f'    (property "Datasheet" "~" (at {x} {y} 0) {FONT_H})']
        for k, v in (fields or {}).items():
            if v:
                out.append(f'    (property "{k}" "{v}" (at {x} {y} 0) {FONT_H})')
        for p in pins:
            out.append(f'    (pin "{p}" (uuid {self.uid("p", ref, p)}))')
        out.append(f'    (instances (project "{self.project}"'
                   f' (path "/{self.root}" (reference "{ref}") (unit 1))))')
        out.append("  )")
        self.items.append("\n".join(out))
        return pins

    def power(self, kind, x, y):
        self.pwr += 1
        ref = f"#PWR{self.pwr:03d}"
        lib_id = f"power:{kind}"
        if kind == "GND":
            val_xy = (x, y + 3.81)
        elif kind == "PWR_FLAG":
            val_xy = (x, y - 3.81)
        else:
            val_xy = (x, y - 3.81)
        if kind == "PWR_FLAG":
            ref = f"#FLG{self.pwr:03d}"
        self.symbol(lib_id, ref, kind, x, y, 0, hide_ref=True, val_xy=val_xy, in_bom=False)

    # ------------------------------------------------------- high-level part
    def place(self, part, x, y, rot=0, ref_xy=None, val_xy=None, hide_val=False):
        x, y = g(x), g(y)
        fields = {"Descrição": part.desc, "MPN": part.mpn, "Nota": part.note}
        pins = self.symbol(part.lib, part.ref, part.value, x, y, rot, part.fp, fields,
                           ref_xy=ref_xy, val_xy=val_xy, dnp=part.dnp, hide_val=hide_val)
        for num, (px, py, pa) in pins.items():
            net = part.pins.get(num)
            sx, sy = transform(px, py, x, y, rot)
            d = outward(pa, rot)
            if net is None:
                self.noconnect(sx, sy)
                continue
            long = net in ("GND", "VCC") and (part.lib.startswith("PFC:") or part.lib.startswith("Connector_Generic:"))
            L = (17.78 if part.lib.startswith("Connector_Generic:") else 12.7) if long else STUB
            ex, ey = round(sx + d[0] * L, 4), round(sy + d[1] * L, 4)
            self.wire(sx, sy, ex, ey)
            if net in ("GND", "VCC"):
                self.power(net, ex, ey)
            else:
                self.label(net, ex, ey, d)

    def flag(self, net, x, y):
        x, y = g(x), g(y)
        self.power("PWR_FLAG", x, y)
        self.wire(x, y, x, y + STUB)
        if net in ("GND", "VCC"):
            self.power(net, x, y + STUB)
        else:
            self.label(net, x, y + STUB, (0, 1))

    def block(self, title, x, y, w, h, notes=()):
        x, y = g(x), g(y)
        self.rect(x, y, g(x + w), g(y + h))
        self.text(title, x + 2.54, y + 5.08, 1.8, bold=True)
        for i, n in enumerate(notes):
            self.text(n, x + 2.54, y + h - 2.0 - 2.4 * (len(notes) - 1 - i), 1.27, italic=True)
        return x, y

    def column_parts(self, parts_by_ref, refs_cols, bx, by, top=15.24, colw=COLW, x0=25.4):
        for c, col in enumerate(refs_cols):
            for r, ref in enumerate(col):
                p = parts_by_ref[ref]
                rot = 90 if p.lib in ("Device:R", "Device:C", "Device:C_Polarized") else 0
                px, py = g(bx + x0 + c * colw), g(by + top + r * ROWH)
                off = 3.81 if p.lib in ("Device:C", "Device:C_Polarized") else 2.54
                self.place(p, px, py, rot, ref_xy=(px, g(py - off)), val_xy=(px, g(py + off)))

    # ----------------------------------------------------------------- write
    def write(self, path: Path, rev="1.0", date="2026-11-02", company=""):
        head = [f'(kicad_sch (version 20230121) (generator eeschema)\n',
                f'  (uuid {self.root})\n',
                '  (paper "A3")\n',
                '  (title_block\n',
                f'    (title "{self.title}")\n    (date "{date}")\n    (rev "{rev}")\n',
                f'    (company "{company}")\n']
        for i, c in enumerate(self.comments, 1):
            head.append(f'    (comment {i} "{c}")\n')
        head.append('  )\n  (lib_symbols\n')
        for blk in self.libs.values():
            head.append("    " + blk.replace("\n", "\n    ") + "\n")
        head.append("  )\n")
        body = "\n".join(self.items)
        tail = '\n  (sheet_instances (path "/" (page "1")))\n)\n'
        path.write_text("".join(head) + body + tail, encoding="utf-8")
