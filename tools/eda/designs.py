"""Fonte única da verdade do projeto (netlist + valores + footprints + posições).

Tudo o que está em hardware/ é GERADO a partir deste arquivo:
    python3 tools/eda/build_all.py

PSH-CARD1  — reprodução fiel do esquemático "PSH CARD1 REV 0.5" (CM6800G.gif),
             placa-filha de controle PFC/PWM de uma fonte ATX.
PSH-JIG1   — placa de bancada (baixa tensão) para energizar e testar a PSH-CARD1
             sem a placa de potência.

Convenção de pinos (bibliotecas KiCad):
  Device:R / C / C_Polarized : 1 = topo (+ no eletrolítico), 2 = base
  Device:D / LED             : 1 = catodo (K), 2 = anodo (A)
  Device:Q_NPN_BEC (SOT-23)  : 1 = B, 2 = E, 3 = C        (MMBT3904)
"""
from dataclasses import dataclass, field


@dataclass
class Part:
    ref: str
    lib: str
    value: str
    fp: str
    pins: dict
    desc: str = ""
    note: str = ""          # "sugerido" = valor ilegível/ausente no REV 0.5
    mpn: str = ""
    dnp: bool = False


# Footprints recorrentes ------------------------------------------------------
R0805 = "Resistor_SMD:R_0805_2012Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
MELF = "Diode_SMD:D_MiniMELF"
SUG = "sugerido"


def R(ref, val, a, b, desc="", note="", fp=R0805):
    return Part(ref, "Device:R", val, fp, {"1": a, "2": b}, desc or "Resistor 0805 1%", note)


def C(ref, val, a, b, desc="", note="", fp=C0805):
    return Part(ref, "Device:C", val, fp, {"1": a, "2": b}, desc or "Capacitor cerâmico 0805 X7R", note)


def D(ref, k, a, val="LL4148", desc="Diodo de sinal rápido 100 V / 200 mA (MiniMELF)", fp=MELF, lib="Device:D"):
    return Part(ref, lib, val, fp, {"1": k, "2": a}, desc, mpn="LL4148")


# =============================================================================
#  PSH-CARD1 — placa-filha CM6800G
# =============================================================================
CARD_PARTS = [
    Part("U4", "PFC:CM6800G", "CM6800G", "Package_DIP:DIP-16_W7.62mm_Socket",
         {"1": "IEAO", "2": "IAC", "3": "ISENSE", "4": "VRMS", "5": "SS", "6": "VDC",
          "7": "RAMP1", "8": "RAMP2", "9": "ILIMIT", "10": "GND", "11": "PWM_OUT",
          "12": "PFC_OUT", "13": "VCC", "14": "VREF", "15": "VFB", "16": "VEAO"},
         "Controlador combo PFC/PWM, PDIP-16 (soquete torneado)", mpn="CM6800GIP"),

    # --- Malha de corrente PFC (IEAO) — rede tipo II referenciada ao VREF ---
    C("C5", "470p", "VREF", "IEAO", "Polo de alta frequência da malha de corrente", SUG),
    R("R27", "10k", "VREF", "IEAO_Z", "Zero da malha de corrente"),
    C("C6", "10n", "IEAO_Z", "IEAO", "Zero da malha de corrente (fz ≈ 1,6 kHz)", SUG),

    # --- Sensor de corrente PFC (ISENSE) ---
    R("R18", "100", "ISENSE", "PFC_CS", "Filtro RC do sensor de corrente PFC"),
    C("C13", "1n", "ISENSE", "GND", "Filtro RC do sensor de corrente PFC", SUG),
    D("D3", "D1D3", "GND"),
    D("D1", "ISENSE", "D1D3"),

    # --- Feed-forward de linha: IAC e VRMS ---
    R("R32", "470k", "IAC", "IAC_M", "Programação de IAC (2 × 470k ⇒ 940 kΩ)", fp="Resistor_SMD:R_1206_3216Metric"),
    R("R23", "470k", "IAC_M", "VAC_RECT", "Programação de IAC — alta tensão (1206)", fp="Resistor_SMD:R_1206_3216Metric"),
    R("R19", "470k", "VAC_RECT", "VRMS_M", "Divisor VRMS — alta tensão (1206)", fp="Resistor_SMD:R_1206_3216Metric"),
    R("R22", "470k", "VRMS_M", "VRMS_F", "Divisor VRMS (1206)", fp="Resistor_SMD:R_1206_3216Metric"),
    R("R31", "100k", "VRMS_F", "VRMS", "Divisor/filtro VRMS — 2º polo"),
    C("C10", "470n", "VRMS_F", "GND", "Filtro VRMS — 1º polo", SUG),
    R("R45", "13k", "VRMS", "GND", "Divisor VRMS — base"),
    C("C17", "2u2", "VRMS", "GND", "Filtro VRMS — 2º polo", SUG),

    # --- Malha de tensão PFC (VFB / VEAO) + referência ---
    R("R47", "5k1", "VFB", "GND", "Base do divisor do barramento de 380 V"),
    C("C8", "1n", "VFB", "GND", "Filtro de ruído em VFB", SUG),
    R("R44", "430k", "VEAO", "VEAO_Z", "Zero da malha de tensão"),
    C("C22", "100n", "VEAO_Z", "GND", "Zero da malha de tensão (fz ≈ 3,7 Hz)", SUG),
    C("C23", "10n", "VEAO", "GND", "Polo da malha de tensão", SUG),
    C("C7", "1u", "VREF", "GND", "Desacoplamento da referência de 7,5 V", SUG),

    # --- Seção PWM: oscilador, soft-start, realimentação VDC ---
    R("R26", "21k5", "VREF", "RAMP1", "RT do oscilador"),
    C("C20", "1n", "RAMP1", "GND", "CT do oscilador (C0G/NP0)"),
    Part("C14", "Device:C_Polarized", "33u/50V", "Capacitor_SMD:CP_Elec_6.3x5.4",
         {"1": "SS", "2": "GND"}, "Capacitor do soft-start do PWM (eletrolítico SMD)"),
    R("R25", "10k", "VREF", "VDC", "Pull-up de VDC (optoacoplador puxa para baixo)"),
    R("R46", "15k", "VDC", "GND", "Divisor de VDC (VDC máx ≈ 4,5 V)"),
    C("C19", "1n", "VDC", "GND", "Filtro de ruído em VDC", SUG),
    R("R43", "820", "VDC", "VDC_Z", "Rede RC de VDC"),
    C("C18", "100n", "VDC_Z", "GND", "Rede RC de VDC", SUG),

    # --- Drivers de gate (liga lento por R, desliga rápido pelo diodo) ---
    R("R137", "30", "PFC_OUT", "PFC_GATE", "Resistor de gate PFC (turn-on)"),
    D("D38", "PFC_OUT", "PFC_GATE"),
    D("D4", "PFC_OUT", "GND"),
    R("R28", "30", "PWM_OUT", "PWM_GATE", "Resistor de gate PWM (turn-on)"),
    D("D39", "PWM_OUT", "PWM_GATE"),

    # --- Limite de corrente PWM + compensação de rampa (slope compensation) ---
    R("R29", "1k", "PWM_CS", "ILIMIT", "Filtro RC do sensor de corrente PWM"),
    C("C21", "470p", "ILIMIT", "GND", "Filtro RC / blanking do sensor PWM", SUG),
    R("R40", "22k", "ILIMIT", "SLOPE_E", "Injeção da rampa de compensação"),
    Part("Q4", "Device:Q_NPN_BEC", "MMBT3904", "Package_TO_SOT_SMD:SOT-23",
         {"1": "SLOPE_RAMP", "2": "SLOPE_E", "3": "VCC"},
         "NPN seguidor de emissor (buffer da rampa)", mpn="MMBT3904"),
    R("R35", "22k", "VCC", "SLOPE_RAMP", "Carga da rampa (durante o ton do PWM)"),
    C("C15", "1n", "SLOPE_RAMP", "GND", "Capacitor da rampa", SUG),
    R("R36", "1k", "SLOPE_RAMP", "D2_A", "Descarga da rampa (PWM em nível baixo)"),
    D("D2", "PWM_OUT", "D2_A"),
    Part("JP1", "Jumper:SolderJumper_2_Bridged", "RAMP2-ILIMIT",
         "Jumper:SolderJumper-2_P1.3mm_Bridged_RoundedPad1.0x1.5mm",
         {"1": "RAMP2", "2": "ILIMIT"},
         "Liga RAMP2 ao sensor (modo corrente). Novo no REV 1.0 — ver README", "REV 1.0"),

    # --- Alimentação ---
    C("C24", "1u", "VCC", "GND", "Desacoplamento de VCC", SUG),
    Part("C16", "Device:C_Polarized", "10u/50V", "Capacitor_SMD:CP_Elec_5x5.4",
         {"1": "VCC", "2": "GND"}, "Reservatório de VCC (eletrolítico SMD)"),
    R("R30", "0", "VCC", "VCC_HF", "Jumper 0 Ω (opção de RC em VCC)"),
    C("C9", "100n", "VCC_HF", "GND", "Desacoplamento HF de VCC junto ao CI", SUG),

    # --- Conector para a placa-mãe ---
    Part("J1", "Connector_Generic:Conn_01x10", "PSH-BUS",
         "Connector_PinHeader_2.54mm:PinHeader_1x10_P2.54mm_Horizontal",
         {"1": "PFC_CS", "2": "VDC", "3": None, "4": "VAC_RECT", "5": "VCC",
          "6": "VFB", "7": "PFC_GATE", "8": "PWM_CS", "9": "GND", "10": "PWM_GATE"},
         "Barra de pinos 1×10, 2,54 mm, 90° (encaixe na placa de potência)"),
]

# Pontos de teste (novos no REV 1.0)
for i, net in enumerate(["VREF", "VCC", "GND", "RAMP1", "SS", "VEAO", "IEAO", "VRMS"], 1):
    CARD_PARTS.append(Part(f"TP{i}", "Connector:TestPoint", net, "TestPoint:TestPoint_Pad_D1.5mm",
                           {"1": net}, "Ponto de teste SMD Ø1,5 mm", "REV 1.0"))

CARD_PWR_FLAGS = ["VCC", "GND"]


# =============================================================================
#  PSH-JIG1 — placa de bancada para a PSH-CARD1 (12–15 V, sem rede elétrica)
# =============================================================================
TBLOCK = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal"
TPK = "TestPoint:TestPoint_Keystone_5000-5004_Miniature"
TRIM = "Potentiometer_THT:Potentiometer_Bourns_3296W_Vertical"

JIG_PARTS = [
    Part("J1", "Connector_Generic:Conn_01x10", "PSH-BUS-F",
         "Connector_PinSocket_2.54mm:PinSocket_1x10_P2.54mm_Vertical",
         {"1": "PFC_CS", "2": "VDC", "3": None, "4": "VAC_RECT", "5": "VCC",
          "6": "VFB", "7": "PFC_GATE", "8": "PWM_CS", "9": "GND", "10": "PWM_GATE"},
         "Barra fêmea 1×10, 2,54 mm — recebe a PSH-CARD1"),

    # Entrada de alimentação
    Part("J2", "Connector_Generic:Conn_01x02", "VIN 12-15V", TBLOCK,
         {"1": "VIN", "2": "GND"}, "Borne 2 vias 5,08 mm — alimentação de bancada"),
    D("D1", "VCC", "VIN", "SS34", "Schottky 3 A 40 V — proteção contra inversão", "Diode_SMD:D_SMA",
      "Device:D_Schottky"),
    Part("C1", "Device:C_Polarized", "100u/25V", "Capacitor_SMD:CP_Elec_6.3x7.7",
         {"1": "VCC", "2": "GND"}, "Reservatório de entrada"),
    C("C2", "100n", "VCC", "GND", "Desacoplamento"),
    R("R1", "2k2", "VCC", "LED_A", "Limitador do LED"),
    Part("D2", "Device:LED", "Verde", "LED_SMD:LED_0805_2012Metric",
         {"1": "GND", "2": "LED_A"}, "LED indicador de alimentação"),

    # Emulação de VFB (barramento de 380 V)
    R("R2", "10k", "VCC", "VFB_TOP", "Topo do divisor de VFB"),
    Part("RV1", "Device:R_Potentiometer_Trim", "10k", TRIM,
         {"1": "VFB_TOP", "2": "VFB_SET", "3": "GND"}, "Trimpot multivoltas — ajuste de VFB (2,50 V nominal)"),
    R("R3", "1k", "VFB_SET", "VFB", "Série para VFB"),

    # Emulação do optoacoplador (VDC)
    R("R4", "1k", "VDC", "OPTO", "Série do emulador de opto"),
    Part("RV2", "Device:R_Potentiometer_Trim", "50k", TRIM,
         {"1": "OPTO", "2": "GND", "3": "GND"}, "Trimpot como reostato — emula o transistor do opto"),

    # Injeção de sinais de corrente
    R("R5", "10", "PFC_CS", "GND", "Terminação de PFC_CS (0 V sem gerador)"),
    Part("J3", "Connector_Generic:Conn_01x02", "PFC_CS", "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
         {"1": "PFC_CS", "2": "GND"}, "Injeção de sinal em PFC_CS (gerador de funções)"),
    R("R6", "10", "PWM_CS", "GND", "Terminação de PWM_CS"),
    Part("J4", "Connector_Generic:Conn_01x02", "PWM_CS", "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
         {"1": "PWM_CS", "2": "GND"}, "Injeção de pulso em PWM_CS (teste do limite de 1 V)"),

    # Entrada de linha retificada (opcional / fonte isolada)
    Part("J5", "Connector_Generic:Conn_01x02", "VAC_RECT", TBLOCK,
         {"1": "VAC_RECT", "2": "GND"}, "Borne VAC_RECT — SOMENTE fonte DC isolada e limitada"),

    # Cargas de gate (≈ Ciss de um MOSFET de potência)
    R("R9", "10", "PFC_GATE", "PFC_LOAD", "Rg interna emulada"),
    C("C3", "4n7", "PFC_LOAD", "GND", "Ciss emulada (PFC)", fp="Capacitor_SMD:C_1206_3216Metric"),
    R("R10", "10", "PWM_GATE", "PWM_LOAD", "Rg interna emulada"),
    C("C4", "4n7", "PWM_LOAD", "GND", "Ciss emulada (PWM)", fp="Capacitor_SMD:C_1206_3216Metric"),
]

for i, net in enumerate(["GND", "GND", "VCC", "VFB", "VDC", "PFC_GATE", "PWM_GATE", "VAC_RECT"], 1):
    JIG_PARTS.append(Part(f"TP{i}", "Connector:TestPoint", net, TPK, {"1": net},
                          "Ponto de teste Keystone 5000-series (gancho de ponta de prova)"))
for i in range(1, 5):
    JIG_PARTS.append(Part(f"H{i}", "Mechanical:MountingHole_Pad", "M3", "MountingHole:MountingHole_3.2mm_M3_Pad_Via",
                          {"1": "GND"}, "Furo de fixação M3 aterrado"))

JIG_PWR_FLAGS = ["VIN", "GND"]


def nets_of(parts):
    nets = {}
    for p in parts:
        for pin, n in p.pins.items():
            if n:
                nets.setdefault(n, []).append(f"{p.ref}.{pin}")
    return nets
