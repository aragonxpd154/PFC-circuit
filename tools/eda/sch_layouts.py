"""Disposição dos blocos funcionais nas folhas A3 das duas placas."""
from pathlib import Path

from designs import CARD_PARTS, JIG_PARTS, CARD_PWR_FLAGS, JIG_PWR_FLAGS
from gen_schematic import Sheet, g

COMPANY = "Marcos Santos · github.com/aragonxpd154"

CARD_PINDOC = [
    "PFC_CS   · sensor de corrente PFC (shunt, tensão negativa)",
    "VDC      · realimentação do PWM (coletor do optoacoplador)",
    "NC       · sem conexão — isola o pino 4 (alta tensão)",
    "VAC_RECT · linha retificada (feed-forward IAC / VRMS) — ALTA TENSÃO",
    "VCC      · alimentação 12–15 V vinda do standby",
    "VFB      · topo do divisor do barramento de 380 V",
    "PFC_GATE · gate do MOSFET boost PFC",
    "PWM_CS   · sensor de corrente do conversor DC-DC",
    "GND      · referência (terra do primário)",
    "PWM_GATE · gate/driver do conversor DC-DC (forward)",
]


def build_card(out: Path):
    s = Sheet("psh-card1", "PSH CARD1 — Controlador PFC/PWM CM6800G", [
        "Reprodução fiel do esquemático PSH CARD1 REV 0.5 (engenharia reversa) + JP1 e pontos de teste",
        "Valores marcados como 'sugerido' eram ilegíveis/ausentes no original — ver docs/BOM",
        "Licença GPL-3.0 · github.com/aragonxpd154/PFC-circuit",
    ])
    P = {p.ref: p for p in CARD_PARTS}

    # ---------- Linha A
    x, y = s.block("CONTROLADOR · U4 CM6800G", 15, 20, 115, 72, [
        "PFC: borda de subida, corrente média  ·  PWM: borda de descida — sincronizados",
        "JP1 (REV 1.0): RAMP2 estava em aberto no REV 0.5 — ligado a ILIMIT (modo corrente)",
    ])
    s.place(P["U4"], x + 57.15, y + 34.29, 0, ref_xy=(g(x + 57.15), g(y + 19.05)),
            val_xy=(g(x + 57.15), g(y + 49.53)))

    x, y = s.block("INTERFACE PSH-BUS · J1 (placa de potência)", 135, 20, 135, 72, [
        "Pino 3 sem conexão: distância de isolação para o pino 4 (VAC_RECT)",
    ])
    jx, jy = g(x + 35.56), g(y + 31.75)
    s.place(P["J1"], jx, jy, 0, ref_xy=(jx, g(jy - 13.97)), val_xy=(jx, g(jy + 16.51)))
    for i, line in enumerate(CARD_PINDOC):
        s.text(f"{i + 1:>2}  {line}", g(x + 45.72), round(jy - 10.16 + 2.54 * i + 0.6, 2), 1.27)

    x, y = s.block("MALHA DE CORRENTE PFC · ISENSE", 275, 20, 130, 72, [
        "Rede tipo II referenciada a VREF:  fz = 1/(2π·R27·C6) ≈ 1,6 kHz",
        "D1+D3: grampo de ISENSE em ≈ −1,3 V  ·  R18/C13: filtro ≈ 1,6 MHz",
    ])
    s.column_parts(P, [["C5", "R27", "C6"], ["R18", "C13", "D3", "D1"]], x, y)

    # ---------- Linha B
    x, y = s.block("FEED-FORWARD DE LINHA · IAC / VRMS", 15, 100, 115, 70, [
        "IAC = VAC_RECT / 940 kΩ  ·  VRMS ≈ 0,9·Vac·13k/1053k  (1,00 V @ 90 Vac)",
        "Filtro de 2 polos: R31·C10 e R45·C17  ·  470k em 1206 (tensão)",
    ])
    s.column_parts(P, [["R32", "R23", "R19", "R22"], ["R31", "C10", "R45", "C17"]], x, y)

    x, y = s.block("MALHA DE TENSÃO PFC · VFB / VEAO · VREF", 135, 100, 115, 70, [
        "VFB = 2,50 V (regulação)  ·  OVP 2,75 V  ·  VIN-OK 2,45 V",
        "fz = 1/(2π·R44·C22) ≈ 3,7 Hz  ·  VREF = 7,5 V",
    ])
    s.column_parts(P, [["R47", "C8", "C7"], ["R44", "C22", "C23"]], x, y)

    x, y = s.block("PWM · OSCILADOR · SOFT-START · VDC", 255, 100, 150, 70, [
        "fosc = 1/(0,51·R26·C20 + 943 Ω·C20) ≈ 84 kHz",
        "Soft-start 20 µA · C14 ⇒ ≈ 1,2 s até 0,7 V  ·  VDC em aberto ≈ 4,5 V",
    ])
    s.column_parts(P, [["R26", "C20", "C14"], ["R25", "R46", "C19"], ["R43", "C18"]], x, y,
                   colw=45.72)

    # ---------- Linha C
    x, y = s.block("DRIVERS DE GATE", 15, 178, 115, 70, [
        "Turn-on por 30 Ω, turn-off rápido pelo LL4148 em antiparalelo",
        "D4: grampo de undershoot em PFC_OUT",
    ])
    s.column_parts(P, [["R137", "D38", "D4"], ["R28", "D39"]], x, y)

    x, y = s.block("LIMITE DE CORRENTE PWM · COMPENSAÇÃO DE RAMPA", 135, 178, 150, 70, [
        "Limite ciclo-a-ciclo: ILIMIT > 1,0 V  ·  rampa: R35·C15 carrega no ton,",
        "D2/R36 resetam no toff; Q4 (seguidor) + R40 somam a rampa ao sensor",
    ])
    s.column_parts(P, [["R29", "C21", "R40", "JP1"], ["R35", "C15", "R36", "D2"]], x, y)
    qx, qy = g(x + 25.4 + 2 * 50.8 - 5.08), g(y + 27.94)
    s.place(P["Q4"], qx, qy, 0, ref_xy=(g(qx + 10.16), g(qy - 1.27)), val_xy=(g(qx + 10.16), g(qy + 1.27)))

    x, y = s.block("ALIMENTAÇÃO VCC", 290, 178, 60, 70, ["VCC 12–15 V (OVP de VCC: 17,9 V)"])
    s.column_parts(P, [["C24", "C16", "R30", "C9"]], x, y, x0=17.78)
    s.flag("VCC", x + 38.1, y + 22.86)
    s.flag("GND", x + 53.34, y + 22.86)

    x, y = s.block("PONTOS DE TESTE", 355, 178, 50, 70, ["Novos no REV 1.0 · Ø1,5 mm"])
    for i in range(8):
        p = P[f"TP{i + 1}"]
        cx, cy = x + 7.62 + (i // 4) * 25.4, y + 15.24 + (i % 4) * 10.16
        s.place(p, cx, cy, 90, ref_xy=(g(cx - 2.54), g(cy - 3.81)), hide_val=True)

    s.write(out, company=COMPANY)


def build_jig(out: Path):
    s = Sheet("psh-jig1", "PSH JIG1 — Bancada de testes para a PSH CARD1", [
        "Opera a PSH-CARD1 com 12–15 V DC, sem placa de potência e sem rede elétrica",
        "Emula VFB, optoacoplador, sensores de corrente e cargas de gate",
        "Licença GPL-3.0 · github.com/aragonxpd154/PFC-circuit",
    ])
    P = {p.ref: p for p in JIG_PARTS}

    x, y = s.block("SOQUETE PSH-BUS · J1", 15, 20, 95, 95, ["A PSH-CARD1 encaixa aqui (barra fêmea 1×10)"])
    jx, jy = g(x + 55.88), g(y + 44.45)
    s.place(P["J1"], jx, jy, 0, ref_xy=(jx, g(jy - 13.97)), val_xy=(jx, g(jy + 16.51)))

    x, y = s.block("ENTRADA 12–15 V · PROTEÇÃO · INDICAÇÃO", 115, 20, 150, 95, [
        "D1 Schottky: proteção contra inversão de polaridade (queda ≈ 0,4 V)",
    ])
    s.place(P["J2"], x + 25.4, y + 20.32, 0)
    s.column_parts(P, [["D1", "C1", "C2"], ["R1", "D2"]], x, y, x0=60.96)

    x, y = s.block("EMULAÇÃO DO BARRAMENTO · VFB", 270, 20, 135, 95, [
        "Ajuste RV1 para 2,50 V em TP4 (= barramento 380 V regulado)",
        "2,45 V libera o PWM (VIN-OK) · 2,75 V aciona a OVP do PFC",
    ])
    s.place(P["R2"], x + 25.4, y + 22.86, 90)
    s.place(P["RV1"], x + 63.5, y + 38.1, 0, ref_xy=(g(x + 55.88), g(y + 36.83)), val_xy=(g(x + 55.88), g(y + 39.37)))
    s.place(P["R3"], x + 101.6, y + 38.1, 90)

    x, y = s.block("EMULAÇÃO DO OPTOACOPLADOR · VDC", 15, 120, 95, 65, [
        "RV2 ↓ ⇒ VDC ↓ ⇒ razão cíclica do PWM ↓",
    ])
    s.place(P["R4"], x + 25.4, y + 22.86, 90)
    s.place(P["RV2"], x + 63.5, y + 33.02, 0, ref_xy=(g(x + 55.88), g(y + 31.75)), val_xy=(g(x + 55.88), g(y + 34.29)))

    x, y = s.block("INJEÇÃO DE SINAL DE CORRENTE", 115, 120, 150, 65, [
        "J3: forma de onda negativa em PFC_CS (−1 V = limite de pico)",
        "J4: pulso em PWM_CS (> 1,0 V = limite ciclo-a-ciclo)",
    ])
    s.place(P["R5"], x + 25.4, y + 20.32, 90)
    s.place(P["J3"], x + 88.9, y + 20.32, 0)
    s.place(P["R6"], x + 25.4, y + 38.1, 90)
    s.place(P["J4"], x + 88.9, y + 38.1, 0)

    x, y = s.block("CARGAS DE GATE · ≈ Ciss DE MOSFET", 270, 120, 135, 65, [
        "10 Ω + 4,7 nF ≈ MOSFET 600 V / 20 A — observe tr/tf em TP6 e TP7",
    ])
    s.column_parts(P, [["R9", "R10"], ["C3", "C4"]], x, y)

    x, y = s.block("LINHA RETIFICADA · OPCIONAL", 15, 190, 95, 62, [
        "ATENÇÃO: somente fonte DC isolada e limitada em corrente.",
        "Nunca conecte diretamente à rede elétrica.",
    ])
    s.place(P["J5"], x + 55.88, y + 22.86, 0)

    x, y = s.block("PONTOS DE TESTE", 115, 190, 150, 62, ["Keystone 5000-series"])
    for i in range(8):
        p = P[f"TP{i + 1}"]
        cx, cy = x + 10.16 + (i % 4) * 35.56, y + 20.32 + (i // 4) * 15.24
        s.place(p, cx, cy, 90, ref_xy=(g(cx - 2.54), g(cy - 3.81)), hide_val=True)

    x, y = s.block("MECÂNICA · FLAGS", 270, 190, 135, 62, ["Furos M3 aterrados"])
    for i in range(4):
        p = P[f"H{i + 1}"]
        hx = x + 12.7 + i * 17.78
        s.place(p, hx, y + 20.32, 0, ref_xy=(g(hx + 5.08), g(y + 17.78)), val_xy=(g(hx + 5.08), g(y + 20.32)))
    s.flag("VIN", x + 93.98, y + 22.86)
    s.flag("GND", x + 114.3, y + 22.86)

    s.write(out, company=COMPANY)
