#!/usr/bin/env python3
"""Gera hardware/lib/PFC.kicad_sym com o símbolo do CM6800G (PDIP-16 / SOP-16).

Pinagem conforme o datasheet Champion CM6800 (compatível pino a pino com
ML4800 / FAN4800).
"""
from pathlib import Path

PINS_LEFT = [  # (número, nome, tipo elétrico)
    ("1", "IEAO", "output"),
    ("2", "IAC", "input"),
    ("3", "ISENSE", "input"),
    ("4", "VRMS", "input"),
    ("5", "SS", "passive"),
    ("6", "VDC", "input"),
    ("7", "RAMP1", "passive"),
    ("8", "RAMP2", "input"),
]
PINS_RIGHT = [
    ("16", "VEAO", "output"),
    ("15", "VFB", "input"),
    ("14", "VREF", "power_out"),
    ("13", "VCC", "power_in"),
    ("12", "PFC_OUT", "output"),
    ("11", "PWM_OUT", "output"),
    ("10", "GND", "power_in"),
    ("9", "DC_ILIMIT", "input"),
]

F = "(effects (font (size 1.27 1.27)))"
FH = "(effects (font (size 1.27 1.27)) hide)"


def pin(kind, x, y, ang, name, num):
    return (f'      (pin {kind} line (at {x} {y} {ang}) (length 5.08)\n'
            f'        (name "{name}" {F})\n        (number "{num}" {F}))\n')


def build() -> str:
    out = ['(kicad_symbol_lib (version 20220914) (generator pfc_circuit_tools)\n',
           '  (symbol "CM6800G" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)\n',
           f'    (property "Reference" "U" (at 0 13.97 0) {F})\n',
           f'    (property "Value" "CM6800G" (at 0 -13.97 0) {F})\n',
           f'    (property "Footprint" "Package_DIP:DIP-16_W7.62mm_Socket" (at 0 -16.51 0) {FH})\n',
           f'    (property "Datasheet" "~" (at 0 0 0) {FH})\n',
           f'    (property "ki_keywords" "PFC PWM combo controller ML4800 FAN4800 CM6800" (at 0 0 0) {FH})\n',
           f'    (property "ki_description" "Controlador combo PFC (corrente média, borda de subida) + PWM (borda de descida), Champion CM6800G, DIP-16" (at 0 0 0) {FH})\n',
           '    (symbol "CM6800G_0_1"\n',
           '      (rectangle (start -12.7 11.43) (end 12.7 -11.43) (stroke (width 0.254) (type default)) (fill (type background)))\n',
           '    )\n',
           '    (symbol "CM6800G_1_1"\n']
    for i, (n, name, kind) in enumerate(PINS_LEFT):
        out.append(pin(kind, -17.78, round(8.89 - 2.54 * i, 2), 0, name, n))
    for i, (n, name, kind) in enumerate(PINS_RIGHT):
        out.append(pin(kind, 17.78, round(8.89 - 2.54 * i, 2), 180, name, n))
    out.append('    )\n  )\n)\n')
    return "".join(out)


if __name__ == "__main__":
    dst = Path(__file__).resolve().parents[2] / "hardware" / "lib" / "PFC.kicad_sym"
    dst.write_text(build(), encoding="utf-8")
    print("escrito", dst)
