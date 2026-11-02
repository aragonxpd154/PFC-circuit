#!/usr/bin/env python3
"""Roda todas as simulações ngspice da PSH-CARD1 e gera os gráficos + RESULTS.md.

Uso:  python3 simulation/run_sims.py          (a partir da raiz do repositório)
Requer: ngspice ≥ 36, numpy, matplotlib
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
IMG = ROOT / "docs" / "images"
OUT = HERE / "out"

# Paleta categórica validada (ordem fixa) + tinta neutra
S1, S2, S3, S4 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK, INK2, MUTED, GRID, SURF = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e0", "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "axes.titlecolor": INK,
    "axes.titlesize": 12.5, "axes.titleweight": "semibold", "axes.titlelocation": "left",
    "axes.labelsize": 10, "xtick.color": MUTED, "ytick.color": MUTED,
    "xtick.labelsize": 9, "ytick.labelsize": 9, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False,
    "lines.linewidth": 2.0, "legend.frameon": False, "legend.fontsize": 9.5,
    "font.family": "DejaVu Sans", "axes.formatter.use_locale": False,
})


def spice(cir: str) -> str:
    r = subprocess.run(["ngspice", "-b", cir], cwd=HERE, capture_output=True, text=True)
    return r.stdout + r.stderr


def meas(log: str, name: str) -> list[float]:
    return [float(m) for m in re.findall(rf"^{name}\s*=\s*([-\d.eE+]+)", log, re.M)]


def load(path: Path) -> np.ndarray:
    return np.loadtxt(path)


def comma(x: float, fmt: str) -> str:
    return format(x, fmt).replace(".", ",")


def save(fig, name):
    fig.savefig(IMG / name, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("✓", name)


def main():
    OUT.mkdir(exist_ok=True)
    IMG.mkdir(parents=True, exist_ok=True)
    res = {}

    # ---------------------------------------------------------------- 01
    log = spice("01_oscilador.cir")
    f = float(re.search(r"fosc = ([-\d.eE+]+)", log).group(1))
    res["f_osc"] = f
    d = load(OUT / "01_oscilador.dat")
    t, v = d[:, 0] * 1e6, d[:, 1]
    m = t > 60
    fig, ax = plt.subplots(figsize=(8.6, 3.2))
    ax.plot(t[m], v[m], color=S1)
    for y, lab in [(3.75, "3,75 V — fim da rampa"), (1.25, "1,25 V — início")]:
        ax.axhline(y, color=MUTED, lw=1, ls=(0, (4, 3)))
        ax.text(t[m][-1], y + 0.08, lab, ha="right", va="bottom", color=INK2, fontsize=8.5)
    ax.set(title=f"Oscilador RAMP1 (R26 = 21k5, C20 = 1 nF) — {comma(f / 1e3, '.1f')} kHz simulado",
           xlabel="tempo [µs]", ylabel="V(RAMP1) [V]", ylim=(0.8, 4.2))
    save(fig, "sim-oscilador.png")

    # ---------------------------------------------------------------- 02
    log = spice("02_vrms.cir")
    vavg, vpp, ipk = meas(log, "vrms_avg"), meas(log, "vrms_pp"), meas(log, "iac_pk")
    vacs = [90, 115, 230, 264]
    res["vrms"] = list(zip(vacs, vavg, vpp, ipk))
    fig, ax = plt.subplots(figsize=(8.6, 3.6))
    for vac, col in zip(vacs, [S1, S2, S3, S4]):
        d = load(OUT / f"02_vrms_{vac}")
        ax.plot(d[:, 0], d[:, 1], color=col, label=f"{vac} Vac")
        ax.text(2.02, d[-1, 1], f"{vac} Vac · {comma(d[-1, 1], '.2f')} V", va="center", fontsize=8.5, color=INK2)
    ax.set(title="Feed-forward de linha — VRMS (divisor 1053k/13k + filtro de 2 polos)",
           xlabel="tempo [s]", ylabel="V(VRMS) [V]", xlim=(0, 2.0), ylim=(0, 3.3))
    ax.legend(loc="upper left", ncols=4)
    save(fig, "sim-vrms.png")

    # ---------------------------------------------------------------- 03
    log = spice("03_rampa.cir")
    res["ramp_pk"], res["ilim_pk"], res["ilim_nc_pk"] = (meas(log, k)[0] for k in ("ramp_pk", "ilim_pk", "ilim_nc_pk"))
    d = load(OUT / "03_rampa.dat")
    t = (d[:, 0] - d[0, 0]) * 1e6
    m = t < 36
    fig, axs = plt.subplots(3, 1, figsize=(8.6, 6.4), sharex=True, gridspec_kw={"hspace": 0.38})
    axs[0].plot(t[m], d[m, 1], color=S1)
    axs[0].set(title="PWM_OUT (84 kHz, D = 40 %)", ylabel="[V]")
    axs[1].plot(t[m], d[m, 3], color=S2)
    axs[1].set(title="Rampa em C15 (R35 carrega no ton, D2/R36 resetam no toff)", ylabel="[V]")
    axs[2].plot(t[m], d[m, 5], color=S1, label="com compensação (Q4 + R40)")
    axs[2].plot(t[m], d[m, 7], color=S3, label="sem compensação")
    axs[2].axhline(1.0, color=MUTED, lw=1, ls=(0, (4, 3)))
    axs[2].text(t[m][-1], 1.02, "limite DC ILIMIT = 1,0 V", ha="right", va="bottom", fontsize=8.5, color=INK2)
    axs[2].set(title="Nó DC ILIMIT (pino 9)", ylabel="[V]", xlabel="tempo [µs]", ylim=(-0.05, 1.42))
    axs[2].legend(loc="upper left", ncols=2)
    save(fig, "sim-rampa.png")

    # ---------------------------------------------------------------- 04
    log = spice("04_gate.cir")
    res["tr"], res["tf"], res["tf_b"] = (meas(log, k)[0] for k in ("tr", "tf", "tf_b"))
    d = load(OUT / "04_gate.dat")
    t = d[:, 0] * 1e6
    fig, axs = plt.subplots(1, 2, figsize=(8.6, 3.3), sharey=True, gridspec_kw={"wspace": 0.08})
    for ax, (a, b), ttl in [(axs[0], (0.9, 1.7), "turn-on (R28 = 30 Ω)"), (axs[1], (4.9, 5.7), "turn-off (D39 em paralelo)")]:
        m = (t > a) & (t < b)
        ax.plot(t[m], d[m, 5], color=S3, label="só resistor")
        ax.plot(t[m], d[m, 3], color=S1, label="resistor ∥ LL4148 (placa)")
        ax.set(title=ttl, xlabel="tempo [µs]")
    axs[0].set_ylabel("V(gate) [V]")
    axs[1].legend(loc="upper right")
    fig.suptitle(f"Driver de gate → Ciss 2,2 nF:  tr = {comma(res['tr'] * 1e9, '.0f')} ns · "
                 f"tf = {comma(res['tf'] * 1e9, '.0f')} ns (vs {comma(res['tf_b'] * 1e9, '.0f')} ns sem diodo)",
                 x=0.125, ha="left", fontsize=12.5, fontweight="semibold", color=INK, y=1.02)
    save(fig, "sim-gate.png")

    # ---------------------------------------------------------------- 05
    spice("05_compensacao.cir")
    d = load(OUT / "05_comp.dat")
    fq = d[:, 0]
    fig, ax = plt.subplots(figsize=(8.6, 3.6))
    ax.loglog(fq, d[:, 1], color=S1, label="IEAO — malha de corrente")
    ax.loglog(fq, d[:, 3], color=S2, label="VEAO — malha de tensão")
    for fz, col, lab in [(1 / (2 * np.pi * 10e3 * 10e-9), S1, "zero 1,6 kHz"), (1 / (2 * np.pi * 430e3 * 100e-9), S2, "zero 3,7 Hz")]:
        ax.axvline(fz, color=col, lw=1, ls=(0, (4, 3)), alpha=0.7)
        ax.text(fz * 1.15, ax.get_ylim()[1] if False else 3e6, lab, color=INK2, fontsize=8.5, va="top")
    ax.set(title="Redes de compensação — |Z| na saída dos amplificadores de transcondutância",
           xlabel="frequência [Hz]", ylabel="|Z| [Ω]", xlim=(0.1, 1e6))
    ax.legend(loc="lower left")
    save(fig, "sim-compensacao.png")

    # ---------------------------------------------------------------- RESULTS.md
    import sys
    sys.path.insert(0, str(ROOT / "tools"))
    import pfc_calc
    c = pfc_calc.compute(pfc_calc.defaults())
    rows = "\n".join(f"| {v} Vac | {comma(a, '.3f')} V ({comma(t['VRMS_V'], '.3f')} V) | {comma(p * 1e3, '.1f')} mV | {comma(i * 1e6, '.0f')} µA ({comma(t['IAC_pk_uA'], '.0f')} µA) |"
                     for (v, a, p, i), t in zip(res["vrms"], c["linha"]["tabela"]))

    md = f"""# Resultados das simulações (gerado por `run_sims.py`)

| Grandeza | Simulado | Calculado (`tools/pfc_calc.py`) |
|---|---|---|
| Frequência do oscilador | {comma(res['f_osc'] / 1e3, '.1f')} kHz | {comma(c['oscilador']['f_osc_Hz'] / 1e3, '.1f')} kHz |
| Pico da rampa em C15 (D = 40 %) | {comma(res['ramp_pk'], '.2f')} V | {comma(c['rampa']['V_rampa_pico_V'], '.2f')} V |
| Rampa somada em ILIMIT (pico) | {comma((res['ilim_pk'] - res['ilim_nc_pk']) * 1e3, '.0f')} mV | {comma(c['rampa']['acrescimo_ILIMIT_V'] * 1e3, '.0f')} mV |
| Gate: tempo de subida 10–90 % | {comma(res['tr'] * 1e9, '.0f')} ns | — |
| Gate: tempo de descida 90–10 % | {comma(res['tf'] * 1e9, '.0f')} ns (sem diodo: {comma(res['tf_b'] * 1e9, '.0f')} ns) | — |

## Feed-forward de linha

| Linha | VRMS médio (calculado) | Ondulação p-p | IAC de pico (calculado) |
|---|---|---|---|
{rows}
"""
    (HERE / "RESULTS.md").write_text(md, encoding="utf-8")
    print("✓ RESULTS.md")


if __name__ == "__main__":
    main()
