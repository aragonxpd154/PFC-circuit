#!/usr/bin/env python3
"""Calculadora de projeto da PSH-CARD1 (CM6800G).

Recalcula todos os pontos de operação a partir dos valores de componentes
da placa: oscilador, feed-forward de linha, malhas de compensação,
soft-start, proteções e drivers de gate.

Uso:
    python3 tools/pfc_calc.py                    # valores padrão da placa
    python3 tools/pfc_calc.py --vbus 390 --rsense-pfc 0.05 --vac 90 115 230 264
    python3 tools/pfc_calc.py --json             # saída para scripts

Somente biblioteca padrão — roda em qualquer Python ≥ 3.8.
"""
from __future__ import annotations

import argparse
import json
import math
import sys

# ----------------------------------------------------------------- constantes
# Datasheet Champion CM6800/CM6800A (pino a pino com ML4800/FAN4800)
VREF = 7.5           # V  — referência interna
VFB_REG = 2.5        # V  — regulação do barramento
VFB_OVP = 2.75       # V  — sobretensão do PFC
VIN_OK = 2.45        # V  — libera soft-start do PWM
ILIMIT_TH = 1.0      # V  — limite ciclo-a-ciclo do PWM (DC ILIMIT)
ISENSE_LIM = -1.0    # V  — limite de pico do PFC (ISENSE)
I_SS = 20e-6         # A  — corrente de carga do soft-start
V_SS_START = 0.7     # V  — PWM começa a chavear
K_DEADTIME = 943.0   # Ω  — tDEADTIME = 943·CT  (CM6800A; ML4800 ≈ 490 Ω)
LN_RAMP = math.log((VREF - 1.25) / (VREF - 3.75))  # ≈ 0,51
VCC_OVP = 17.9       # V

# Valores da placa (REV 0.5 legíveis + sugeridos no REV 1.0)
BOARD = {
    "R26": 21.5e3, "C20": 1e-9,                     # oscilador
    "R32": 470e3, "R23": 470e3,                     # IAC
    "R19": 470e3, "R22": 470e3, "R31": 100e3, "R45": 13e3, "C10": 470e-9, "C17": 2.2e-6,
    "R27": 10e3, "C5": 470e-12, "C6": 10e-9,        # malha de corrente
    "R44": 430e3, "C22": 100e-9, "C23": 10e-9,      # malha de tensão
    "R47": 5.1e3,                                   # base do divisor VFB
    "C14": 33e-6,                                   # soft-start
    "R25": 10e3, "R46": 15e3, "R43": 820, "C18": 100e-9, "C19": 1e-9,
    "R18": 100, "C13": 1e-9, "R29": 1e3, "C21": 470e-12,
    "R35": 22e3, "C15": 1e-9, "R36": 1e3, "R40": 22e3,
    "R28": 30, "R137": 30,
}


def par(*r):
    return 1.0 / sum(1.0 / x for x in r)


def eng(v, unit="", digits=3):
    if v == 0 or not math.isfinite(v):
        return f"{v} {unit}".strip()
    exp = int(math.floor(math.log10(abs(v)) / 3) * 3)
    exp = max(-15, min(12, exp))
    pref = {-15: "f", -12: "p", -9: "n", -6: "µ", -3: "m", 0: "", 3: "k", 6: "M", 9: "G", 12: "T"}[exp]
    return f"{v / 10 ** exp:.{digits}g} {pref}{unit}".replace(".", ",")


def compute(a) -> dict:
    b = BOARD
    r = {}

    # --- Oscilador (RAMP1) ---------------------------------------------------
    t_ramp = LN_RAMP * b["R26"] * b["C20"]
    t_dt = K_DEADTIME * b["C20"]
    f = 1 / (t_ramp + t_dt)
    r["oscilador"] = {
        "t_ramp_s": t_ramp, "t_deadtime_s": t_dt, "f_osc_Hz": f,
        "f_osc_ML4800_Hz": 1 / (t_ramp + 490 * b["C20"]),
        "D_max_PWM": 0.5 - t_dt * f / 2,
    }

    # --- Feed-forward de linha ----------------------------------------------
    r_iac = b["R32"] + b["R23"]
    k_vrms = b["R45"] / (b["R19"] + b["R22"] + b["R31"] + b["R45"])
    rows = []
    for vac in a.vac:
        vpk = vac * math.sqrt(2)
        rows.append({"Vac": vac, "Vpk": vpk, "IAC_pk_uA": vpk / r_iac * 1e6,
                     "VRMS_V": 0.9 * vac * k_vrms})
    r["linha"] = {"R_IAC": r_iac, "k_VRMS": k_vrms, "tabela": rows,
                  "f_p1_Hz": 1 / (2 * math.pi * par(b["R19"] + b["R22"], b["R31"] + b["R45"]) * b["C10"]),
                  "f_p2_Hz": 1 / (2 * math.pi * par(b["R31"], b["R45"]) * b["C17"])}

    # --- Barramento e proteções ---------------------------------------------
    r_top = b["R47"] * (a.vbus / VFB_REG - 1)
    r["barramento"] = {
        "Vbus_V": a.vbus, "R_topo_necessario": r_top,
        "Vbus_OVP_V": a.vbus * VFB_OVP / VFB_REG,
        "Vbus_PWM_on_V": a.vbus * VIN_OK / VFB_REG,
        "I_divisor_uA": a.vbus / (r_top + b["R47"]) * 1e6,
    }

    # --- Malhas de compensação ----------------------------------------------
    c_ser = b["C5"] * b["C6"] / (b["C5"] + b["C6"])
    c_ser_v = b["C22"] * b["C23"] / (b["C22"] + b["C23"])
    r["compensacao"] = {
        "IEAO_fz_Hz": 1 / (2 * math.pi * b["R27"] * b["C6"]),
        "IEAO_fp_Hz": 1 / (2 * math.pi * b["R27"] * c_ser),
        "VEAO_fz_Hz": 1 / (2 * math.pi * b["R44"] * b["C22"]),
        "VEAO_fp_Hz": 1 / (2 * math.pi * b["R44"] * c_ser_v),
        "VDC_fz_Hz": 1 / (2 * math.pi * b["R43"] * b["C18"]),
    }

    # --- Seção PWM -----------------------------------------------------------
    vdc_open = VREF * par(b["R46"], b["R43"] + 1e12) / (b["R25"] + b["R46"])
    r["pwm"] = {
        "t_softstart_s": b["C14"] * V_SS_START / I_SS,
        "VDC_aberto_V": vdc_open,
        "I_opto_max_mA": VREF / b["R25"] * 1e3,
        "ILIMIT_fc_Hz": 1 / (2 * math.pi * b["R29"] * b["C21"]),
        "I_pk_PWM_A": ILIMIT_TH / a.rsense_pwm if a.rsense_pwm else None,
    }

    # --- Compensação de rampa -----------------------------------------------
    vcc = a.vcc
    tau = b["R35"] * b["C15"]
    t_on = a.duty / f
    vf = 0.6
    v_floor = vf + (vcc - vf) * b["R36"] / (b["R35"] + b["R36"])  # equilíbrio no toff (R35 × R36)
    v_peak = v_floor + (vcc - v_floor) * (1 - math.exp(-t_on / tau))   # base de Q4 no fim do ton
    k_cs = b["R40"] / (b["R29"] + b["R40"])
    k_inj = b["R29"] / (b["R29"] + b["R40"])
    v_e = max(0.0, v_peak - 0.65)
    ilim_pk = a.vcs_pk * k_cs + v_e * k_inj
    r["rampa"] = {
        "tau_s": tau, "dVdt_inicial_V_per_us": (vcc - v_floor) / tau * 1e-6,
        "V_rampa_piso_V": v_floor, "V_rampa_pico_V": v_peak,
        "ILIMIT_pico_V": ilim_pk, "acrescimo_ILIMIT_V": ilim_pk - a.vcs_pk,
        "t_reset_s": b["R36"] * b["C15"] * 3,
    }

    # --- Sensor PFC e drivers -----------------------------------------------
    r["pfc"] = {
        "ISENSE_fc_Hz": 1 / (2 * math.pi * b["R18"] * b["C13"]),
        "I_pk_limite_A": abs(ISENSE_LIM) / a.rsense_pfc if a.rsense_pfc else None,
    }
    r["gate"] = {
        "Ig_on_pk_A": vcc / (b["R28"] + a.rg_int),
        "tau_on_ns": (b["R28"] + a.rg_int) * a.ciss * 1e9,
        "Ciss_F": a.ciss,
    }
    r["vcc"] = {"VCC_V": vcc, "margem_OVP_V": VCC_OVP - vcc}
    return r


def report(r, a):
    o, l, bb, c, p, ra, pf, g = (r[k] for k in ("oscilador", "linha", "barramento", "compensacao",
                                                "pwm", "rampa", "pfc", "gate"))
    W = 72
    line = "─" * W

    def h(t):
        bold = ("\033[1m", "\033[0m") if sys.stdout.isatty() else ("", "")
        print(f"\n{bold[0]}{t}{bold[1]}\n{line}")

    def kv(k, v, note=""):
        print(f"  {k:<42}{v:<20}{note}")

    print("═" * W)
    print("  PSH-CARD1 · CM6800G — calculadora de projeto".center(W))
    print("═" * W)

    h("1 · Oscilador (RAMP1: RT = R26, CT = C20)")
    kv("t_RAMP = 0,51·RT·CT", eng(o["t_ramp_s"], "s"))
    kv("t_DEADTIME = 943 Ω·CT", eng(o["t_deadtime_s"], "s"))
    kv("f_osc (PFC = PWM)", eng(o["f_osc_Hz"], "Hz"), f"(ML4800: {eng(o['f_osc_ML4800_Hz'], 'Hz')})")
    kv("D_max do PWM (estimativa, limite < 50 %)", f"{o['D_max_PWM'] * 100:.1f} %".replace(".", ","))

    h("2 · Feed-forward de linha (IAC / VRMS)")
    kv("R_IAC = R32 + R23", eng(l["R_IAC"], "Ω"))
    kv("Ganho do divisor VRMS", f"{l['k_VRMS']:.5f}".replace(".", ","))
    kv("Polos do filtro VRMS", f"{l['f_p1_Hz']:.2f} Hz / {l['f_p2_Hz']:.2f} Hz".replace(".", ","))
    print(f"\n  {'Vac':>6} {'Vpico':>9} {'IAC pico':>11} {'VRMS':>9}")
    for t in l["tabela"]:
        print(f"  {t['Vac']:>4.0f} V {t['Vpk']:>7.1f} V {t['IAC_pk_uA']:>8.1f} µA {t['VRMS_V']:>7.3f} V"
              .replace(".", ","))

    h(f"3 · Barramento PFC (Vbus = {a.vbus:.0f} V, base do divisor R47 = 5k1)")
    kv("Resistor de topo necessário (placa-mãe)", eng(bb["R_topo_necessario"], "Ω"))
    kv("OVP do PFC dispara em", f"{bb['Vbus_OVP_V']:.0f} V")
    kv("PWM liberado (VIN-OK) em", f"{bb['Vbus_PWM_on_V']:.0f} V")
    kv("Corrente no divisor", f"{bb['I_divisor_uA']:.0f} µA")

    h("4 · Malhas de compensação")
    kv("Corrente (IEAO): zero / polo", f"{eng(c['IEAO_fz_Hz'], 'Hz')} / {eng(c['IEAO_fp_Hz'], 'Hz')}")
    kv("Tensão (VEAO): zero / polo", f"{eng(c['VEAO_fz_Hz'], 'Hz')} / {eng(c['VEAO_fp_Hz'], 'Hz')}")
    kv("VDC: zero R43·C18", eng(c["VDC_fz_Hz"], "Hz"))

    h("5 · Seção PWM")
    kv("Soft-start (C14 até 0,7 V)", eng(p["t_softstart_s"], "s"))
    kv("VDC com opto cortado", f"{p['VDC_aberto_V']:.2f} V".replace(".", ","))
    kv("Corrente máx. do opto (VDC = 0)", f"{p['I_opto_max_mA']:.2f} mA".replace(".", ","))
    kv("Filtro ILIMIT (R29·C21)", eng(p["ILIMIT_fc_Hz"], "Hz"))
    if p["I_pk_PWM_A"]:
        kv(f"Pico de corrente PWM (Rs = {str(a.rsense_pwm).replace('.', ',')} Ω)", f"{p['I_pk_PWM_A']:.2f} A".replace(".", ","))

    h("6 · Compensação de rampa (Q4 · R35 · C15 · R36 · D2 · R40)")
    kv("τ = R35·C15", eng(ra["tau_s"], "s"))
    kv("dV/dt inicial na base de Q4", f"{ra['dVdt_inicial_V_per_us']:.3f} V/µs".replace(".", ","))
    kv("Piso / pico da rampa na base de Q4", f"{ra['V_rampa_piso_V']:.2f} / {ra['V_rampa_pico_V']:.2f} V".replace(".", ","),
       f"(D = {a.duty * 100:.0f} %)")
    kv(f"ILIMIT no pico (PWM_CS = {a.vcs_pk:g} V)".replace(".", ","), f"{ra['ILIMIT_pico_V']:.3f} V".replace(".", ","),
       f"(+{ra['acrescimo_ILIMIT_V'] * 1e3:.0f} mV de rampa)")

    h("7 · Sensor PFC e drivers de gate")
    kv("Filtro ISENSE (R18·C13)", eng(pf["ISENSE_fc_Hz"], "Hz"))
    if pf["I_pk_limite_A"]:
        kv(f"Limite de pico PFC (Rs = {str(a.rsense_pfc).replace('.', ',')} Ω)", f"{pf['I_pk_limite_A']:.1f} A".replace(".", ","))
    kv("Pico de corrente de gate (turn-on)", f"{g['Ig_on_pk_A']:.2f} A".replace(".", ","),
       f"(Rg_int = {a.rg_int:g} Ω)")
    kv("τ de carga do gate (30 Ω + Rg)·Ciss", eng(g["tau_on_ns"] * 1e-9, "s"), f"(Ciss = {eng(a.ciss, 'F')})")
    kv("Margem até a OVP de VCC (17,9 V)", f"{r['vcc']['margem_OVP_V']:.1f} V".replace(".", ","))
    print("═" * W)


def defaults():
    """Namespace com os valores padrão (para uso como biblioteca)."""
    return build_parser().parse_args([])


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vbus", type=float, default=380, help="tensão do barramento PFC [V] (380)")
    ap.add_argument("--vac", type=float, nargs="+", default=[90, 115, 230, 264], help="tensões de linha [Vrms]")
    ap.add_argument("--vcc", type=float, default=15, help="VCC do CI [V] (15)")
    ap.add_argument("--rsense-pfc", type=float, default=0.1, help="shunt do PFC na placa-mãe [Ω]")
    ap.add_argument("--rsense-pwm", type=float, default=0.47, help="shunt do conversor DC-DC [Ω]")
    ap.add_argument("--ciss", type=float, default=2.2e-9, help="Ciss do MOSFET [F]")
    ap.add_argument("--rg-int", type=float, default=2.0, help="Rg interna do MOSFET [Ω]")
    ap.add_argument("--duty", type=float, default=0.40, help="razão cíclica do PWM p/ a rampa (0,40)")
    ap.add_argument("--vcs-pk", type=float, default=0.65, help="pico de PWM_CS no fim do ton [V] (0,65)")
    ap.add_argument("--json", action="store_true", help="saída JSON")
    return ap


def main():
    a = build_parser().parse_args()
    r = compute(a)
    if a.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        report(r, a)


if __name__ == "__main__":
    main()
