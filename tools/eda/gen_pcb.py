#!/usr/bin/env python3
"""Gera, roteia e finaliza as placas (.kicad_pcb) via API pcbnew do KiCad 7.

Etapas por placa:
  1. place   — contorno, footprints, redes, classes de rede, serigrafia
  2. route   — exporta Specctra DSN → Freerouting (CLI) → importa SES
  3. finish  — planos de GND nas duas faces, preenchimento, relatório DRC

Uso: python3 gen_pcb.py card|jig [--no-route]
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pcbnew

from designs import CARD_PARTS, JIG_PARTS
from pcb_layouts import CARD_POS, CARD_SIZE, JIG_POS, JIG_SIZE
from sexpr import det_uuid

ROOT = Path(__file__).resolve().parents[2]
FPLIB = Path("/usr/share/kicad/footprints")
FREEROUTING = Path(os.environ.get("FREEROUTING_JAR", ROOT / "tools" / "bin" / "freerouting-1.9.0.jar"))
OX, OY = 100.0, 100.0   # origem da placa na folha (mm)

BOARDS = {
    "card": dict(name="psh-card1", parts=CARD_PARTS, pos=CARD_POS, size=CARD_SIZE, corner=2.0,
                 title="PSH CARD1", subtitle="CM6800G PFC/PWM · REV 1.0", ref_on_silk=False,
                 hv=["VAC_RECT", "IAC_M", "VRMS_M"],
                 power=["VCC", "GND", "PFC_GATE", "PWM_GATE", "PFC_OUT", "PWM_OUT"]),
    "jig": dict(name="psh-jig1", parts=JIG_PARTS, pos=JIG_POS, size=JIG_SIZE, corner=3.0,
                title="PSH JIG1", subtitle="Bancada de testes · PSH CARD1 · REV 1.0", ref_on_silk=True,
                hv=["VAC_RECT"],
                power=["VCC", "VIN", "GND", "PFC_GATE", "PWM_GATE", "PFC_LOAD", "PWM_LOAD"]),
}


def mm(v):
    return pcbnew.FromMM(v)


def pt(x, y):
    return pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))


# ----------------------------------------------------------------------------- 1
def outline(board, w, h, r):
    def seg(x1, y1, x2, y2):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pt(x1, y1)); s.SetEnd(pt(x2, y2))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1)); board.Add(s)

    def arc(cx, cy, sx, sy, ang):
        a = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC)
        a.SetCenter(pt(cx, cy)); a.SetStart(pt(sx, sy))
        a.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(ang, pcbnew.DEGREES_T), True)
        a.SetLayer(pcbnew.Edge_Cuts); a.SetWidth(mm(0.1)); board.Add(a)

    seg(r, 0, w - r, 0); seg(w, r, w, h - r); seg(w - r, h, r, h); seg(0, h - r, 0, r)
    arc(w - r, r, w - r, 0, 90); arc(w - r, h - r, w, h - r, 90)
    arc(r, h - r, r, h, 90); arc(r, r, 0, r, 90)


def text(board, s, x, y, size, layer, bold=True, mirror=False, just_left=False, angle=0, halign=None):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s); t.SetPosition(pt(x, y)); t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(size * (0.18 if bold else 0.12)))
    t.SetBold(bold); t.SetMirrored(mirror)
    if halign == "right":
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_RIGHT)
    if angle:
        t.SetTextAngle(pcbnew.EDA_ANGLE(angle, pcbnew.DEGREES_T))
    if just_left:
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_RIGHT if mirror else pcbnew.GR_TEXT_H_ALIGN_LEFT)
    board.Add(t)


def board_rules(board):
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(2)
    ds.SetBoardThickness(mm(1.6))


def netclass(name, clr, tw, via=0.6, drill=0.3):
    return {"name": name, "clearance": clr, "track_width": tw, "via_diameter": via, "via_drill": drill,
            "bus_width": 12, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2,
            "line_style": 0, "microvia_diameter": 0.3, "microvia_drill": 0.1,
            "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "wire_width": 6}


def write_project(cfg, out_dir: Path):
    """.kicad_pro com regras de projeto e classes de rede (Default / Power / HV)."""
    import json
    pro = {
        "board": {"design_settings": {
            "defaults": {"board_outline_line_width": 0.1, "copper_line_width": 0.2,
                         "silk_line_width": 0.12, "silk_text_size_h": 1.0, "silk_text_size_v": 1.0,
                         "silk_text_thickness": 0.15, "fab_text_size_h": 0.6, "fab_text_size_v": 0.6},
            "diff_pair_dimensions": [], "drc_exclusions": [],
            "rule_severities": {"silk_overlap": "ignore", "silk_over_copper": "warning",
                                "lib_footprint_issues": "ignore", "lib_footprint_mismatch": "ignore",
                                "courtyards_overlap": "error", "silk_edge_clearance": "ignore",
                                "text_height": "ignore", "text_thickness": "ignore"},
            "rules": {"min_clearance": 0.2, "min_track_width": 0.2, "min_via_diameter": 0.6,
                      "min_via_annular_width": 0.13, "min_through_hole_diameter": 0.3,
                      "min_copper_edge_clearance": 0.4, "min_hole_clearance": 0.25,
                      "min_hole_to_hole": 0.25, "min_silk_clearance": 0.0,
                      "min_text_height": 0.6, "min_text_thickness": 0.08,
                      "min_microvia_diameter": 0.2, "min_microvia_drill": 0.1,
                      "allow_blind_buried_vias": False, "allow_microvias": False},
            "track_widths": [0.0, 0.25, 0.3, 0.5, 0.8],
            "via_dimensions": [{"diameter": 0.0, "drill": 0.0}, {"diameter": 0.6, "drill": 0.3},
                               {"diameter": 0.7, "drill": 0.35}]}},
        "boards": [],
        "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
        "meta": {"filename": f"{cfg['name']}.kicad_pro", "version": 1},
        "net_settings": {
            "classes": [netclass("Default", 0.2, 0.25), netclass("Power", 0.2, 0.5, 0.7, 0.35),
                        netclass("HV", 0.6, 0.3, 0.7, 0.35)],
            "meta": {"version": 3}, "net_colors": None, "netclass_assignments": None,
            "netclass_patterns": [{"netclass": "Power", "pattern": n} for n in cfg["power"]]
                                 + [{"netclass": "HV", "pattern": n} for n in cfg["hv"]]},
        "pcbnew": {"last_paths": {"gencad": "", "idf": "", "netlist": "", "specctra_dsn": "",
                                  "step": "", "vrml": ""}, "page_layout_descr_file": ""},
        "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},
        "sheets": [[det_uuid(cfg["name"], "root"), ""]],
        "text_variables": {},
    }
    (out_dir / f"{cfg['name']}.kicad_pro").write_text(json.dumps(pro, indent=2, ensure_ascii=False))
    (out_dir / "sym-lib-table").write_text(
        '(sym_lib_table\n  (lib (name "PFC")(type "KiCad")(uri "${KIPRJMOD}/../lib/PFC.kicad_sym")'
        '(options "")(descr "Símbolos do projeto PFC-circuit (CM6800G)"))\n)\n')


def place(cfg) -> pcbnew.BOARD:
    board = pcbnew.CreateEmptyBoard() if hasattr(pcbnew, "CreateEmptyBoard") else pcbnew.BOARD()
    w, h = cfg["size"]
    outline(board, w, h, cfg["corner"])
    board_rules(board)

    nets = {}
    for p in cfg["parts"]:
        for n in p.pins.values():
            if n and n not in nets:
                ni = pcbnew.NETINFO_ITEM(board, n)
                board.Add(ni)
                nets[n] = ni

    for p in cfg["parts"]:
        lib, name = p.fp.split(":")
        fp = pcbnew.FootprintLoad(str(FPLIB / f"{lib}.pretty"), name)
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        fp.SetReference(p.ref)
        fp.SetValue(p.value)
        fp.SetPath(pcbnew.KIID_PATH(f"/{det_uuid(cfg['name'], 's', p.ref)}"))
        x, y, rot = cfg["pos"][p.ref]
        fp.SetPosition(pt(x, y))
        fp.SetOrientationDegrees(rot)
        for pad in fp.Pads():
            n = p.pins.get(pad.GetNumber())
            if n:
                pad.SetNet(nets[n])
        if p.fp.endswith("_Socket"):
            # Modelo 3D do CI encaixado no soquete torneado
            m = pcbnew.FP_3DMODEL()
            m.m_Filename = "${KICAD6_3DMODEL_DIR}/Package_DIP.3dshapes/DIP-16_W7.62mm.step"
            m.m_Offset = pcbnew.VECTOR3D(0, 0, 3.0)
            fp.Models().push_back(m)
        ref = fp.Reference()
        ref.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
        ref.SetTextThickness(mm(0.12))
        if not cfg["ref_on_silk"]:
            ref.SetLayer(pcbnew.F_Fab if fp.GetLayer() == pcbnew.F_Cu else pcbnew.B_Fab)
            ref.SetTextSize(pcbnew.VECTOR2I(mm(0.6), mm(0.6)))
            ref.SetTextThickness(mm(0.09))
        board.Add(fp)

    return board


# ----------------------------------------------------------------------------- 2
def edge_keepouts(board, w, h, m=0.6):
    """Faixas de keep-out (trilhas/vias) junto às bordas — o Freerouting não
    recebe a regra de distância cobre-borda do KiCad pelo DSN."""
    zones = []
    for x1, y1, x2, y2 in [(0, 0, w, m), (0, h - m, w, h), (0, 0, m, h), (w - m, 0, w, h)]:
        z = pcbnew.ZONE(board)
        z.SetIsRuleArea(True); z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True)
        z.SetDoNotAllowCopperPour(False); z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False)
        ls = pcbnew.LSET(); ls.AddLayer(pcbnew.F_Cu); ls.AddLayer(pcbnew.B_Cu); z.SetLayerSet(ls)
        ol = z.Outline(); ol.NewOutline()
        for x, y in [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]:
            ol.Append(mm(OX + x), mm(OY + y))
        board.Add(z); zones.append(z)
    return zones


def route(board, work: Path, passes=15, size=None):
    dsn, ses = work / "board.dsn", work / "board.ses"
    keep = edge_keepouts(board, *size) if size else []
    ok = pcbnew.ExportSpecctraDSN(board, str(dsn))
    for z in keep:
        board.Remove(z)
    if not ok:
        raise RuntimeError("falha ao exportar DSN")
    cmd = ["java", "-jar", str(FREEROUTING), "-de", str(dsn), "-do", str(ses), "-mp", str(passes)]
    if os.environ.get("DISPLAY") is None and subprocess.run(["which", "xvfb-run"], capture_output=True).returncode == 0:
        cmd = ["xvfb-run", "-a"] + cmd
    print("·", " ".join(cmd))
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1200, cwd=work)
    import_ses(board, ses)


def import_ses(board, ses: Path):
    """Importa trilhas e vias de uma sessão Specctra (.ses) do Freerouting.

    (ImportSpecctraSES do KiCad 7 só atua na placa aberta na GUI.)
    Unidades da sessão: 0,1 µm, eixo Y invertido.
    """
    import re
    from sexpr import find, find_all, parse
    tree = parse(ses.read_text(encoding="utf-8", errors="replace"))
    routes = find(tree, "routes")
    res = find(routes, "resolution")
    scale = 1e-3 / float(res[2]) if res else 1e-4
    layers = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}

    def P(x, y):
        return pcbnew.VECTOR2I(mm(float(x) * scale), mm(-float(y) * scale))

    n_t = n_v = 0
    for net in find_all(find(routes, "network_out"), "net"):
        ni = board.FindNet(net[1])
        for w in find_all(net, "wire"):
            path = find(w, "path")
            layer, width, coords = path[1], float(path[2]) * scale, path[3:]
            pts = [P(coords[i], coords[i + 1]) for i in range(0, len(coords) - 1, 2)]
            for a, b in zip(pts, pts[1:]):
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(a); t.SetEnd(b); t.SetWidth(mm(width))
                t.SetLayer(layers[layer]); t.SetNet(ni); board.Add(t); n_t += 1
        for v in find_all(net, "via"):
            m = re.search(r"_(\d+):(\d+)_um", v[1])
            dia, drill = (int(m.group(1)) / 1000, int(m.group(2)) / 1000) if m else (0.6, 0.3)
            via = pcbnew.PCB_VIA(board)
            via.SetPosition(P(v[2], v[3])); via.SetWidth(mm(dia)); via.SetDrill(mm(drill))
            via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); via.SetNet(ni); board.Add(via); n_v += 1
    print(f"  SES importado: {n_t} segmentos, {n_v} vias")


# ----------------------------------------------------------------------------- 3
def gnd_zones(board, cfg):
    w, h = cfg["size"]
    gnd = board.FindNet("GND")
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer); z.SetNet(gnd); z.SetZoneName("GND")
        z.SetLocalClearance(mm(0.3)); z.SetMinThickness(mm(0.25))
        z.SetThermalReliefGap(mm(0.3)); z.SetThermalReliefSpokeWidth(mm(0.4))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        ol = z.Outline(); ol.NewOutline()
        for x, y in [(0, 0), (w, 0), (w, h), (0, h)]:
            ol.Append(mm(OX + x), mm(OY + y))
        board.Add(z)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())


def silk(board, cfg):
    w, h = cfg["size"]
    if cfg["name"] == "psh-card1":
        # Face inferior: identidade + pinagem do conector (SMD todos no topo)
        text(board, "PSH CARD1", 31.0, 6.0, 2.0, pcbnew.B_SilkS, mirror=True)
        text(board, "CM6800G · PFC/PWM", 31.0, 9.2, 1.2, pcbnew.B_SilkS, bold=False, mirror=True)
        text(board, "REV 1.0 · 2026", 31.0, 11.6, 1.0, pcbnew.B_SilkS, bold=False, mirror=True)
        text(board, "github.com/aragonxpd154", 31.0, 30.0, 0.9, pcbnew.B_SilkS, bold=False, mirror=True)
        text(board, "GPL-3.0 · (!) ALTA TENSÃO EM J1.4", 31.0, 32.2, 0.9, pcbnew.B_SilkS, bold=False, mirror=True)
        names = ["PFC_CS", "VDC", "NC", "VAC (!)", "VCC", "VFB", "PFC_G", "PWM_CS", "GND", "PWM_G"]
        for i, n in enumerate(names):
            text(board, f"{i + 1} {n}", 8.0, 29.43 - 2.54 * i, 0.8, pcbnew.B_SilkS, bold=False,
                 mirror=True, just_left=True)
        text(board, "CM6800G", 25.4, 18.2, 1.1, pcbnew.F_SilkS)
    else:
        text(board, "PSH JIG1 · bancada de testes da PSH CARD1", 45.0, 57.0, 1.5, pcbnew.F_SilkS)
        text(board, "REV 1.0 · github.com/aragonxpd154 · GPL-3.0", 45.0, 54.6, 1.0, pcbnew.F_SilkS, bold=False)
        for k, n in enumerate(["PFC_CS", "VDC", "NC", "VAC(!)", "VCC", "VFB", "PFC_G", "PWM_CS", "GND", "PWM_G"]):
            text(board, f"{k + 1} {n}", 33.57 + 2.54 * k, 13.0, 0.8, pcbnew.F_SilkS, bold=False,
                 angle=90, halign="right")
        for ref, (x, y, _r), lab in [("TP1", JIG_POS["TP1"], "GND"), ("TP2", JIG_POS["TP2"], "GND"),
                                     ("TP3", JIG_POS["TP3"], "VCC"), ("TP4", JIG_POS["TP4"], "VFB"),
                                     ("TP5", JIG_POS["TP5"], "VDC"), ("TP6", JIG_POS["TP6"], "PFC_G"),
                                     ("TP7", JIG_POS["TP7"], "PWM_G"), ("TP8", JIG_POS["TP8"], "VAC")]:
            text(board, lab, x, y + 3.6, 1.0, pcbnew.F_SilkS)
        text(board, "VIN 12-15 V", 8.0, 39.0, 1.1, pcbnew.F_SilkS)
        text(board, "(!) VAC: SOMENTE", 70.5, 49.0, 0.9, pcbnew.F_SilkS)
        text(board, "FONTE ISOLADA", 70.5, 50.6, 0.9, pcbnew.F_SilkS)
        text(board, "VFB 2,50 V", 40.0, 36.8, 1.0, pcbnew.F_SilkS)
        text(board, "DUTY (VDC)", 40.0, 49.8, 1.0, pcbnew.F_SilkS)
        text(board, "PFC_CS", 61.0, 28.0, 0.9, pcbnew.F_SilkS)
        text(board, "PWM_CS", 61.0, 41.0, 0.9, pcbnew.F_SilkS)
        text(board, "GATE LOADS", 66.6, 33.0, 0.9, pcbnew.F_SilkS, angle=90)


def drc(board, path: Path):
    pcbnew.WriteDRCReport(board, str(path), pcbnew.EDA_UNITS_MILLIMETRES, True)
    txt = path.read_text()
    import re
    vio = re.search(r"\*\* Found (\d+) DRC violations", txt)
    unc = re.search(r"\*\* Found (\d+) unconnected pads", txt)
    return int(vio.group(1)) if vio else -1, int(unc.group(1)) if unc else -1


def main():
    which = sys.argv[1]
    cfg = BOARDS[which]
    out_dir = ROOT / "hardware" / cfg["name"]
    work = ROOT / "build" / cfg["name"]
    work.mkdir(parents=True, exist_ok=True)
    pcb = out_dir / f"{cfg['name']}.kicad_pcb"

    if "--stage2" not in sys.argv:
        # Estágio 1: posicionamento (processo próprio)
        board = place(cfg)
        silk(board, cfg)
        board.Save(str(pcb))
        # modelos 3D: referência direta aos .step (exportação STEP com componentes)
        pcb.write_text(pcb.read_text(encoding="utf-8").replace('.wrl"', '.step"'), encoding="utf-8")
        write_project(cfg, out_dir)              # depois do Save (que regrava o .kicad_pro)
        # Estágio 2 em processo novo: o pcbnew precisa ler o .kicad_pro do zero
        subprocess.run([sys.executable, __file__] + sys.argv[1:] + ["--stage2"], check=True)
        return

    board = pcbnew.LoadBoard(str(pcb))
    nsx = board.GetDesignSettings().m_NetSettings
    assert nsx.GetEffectiveNetClass(cfg["hv"][0]).GetName() == "HV", "classes de rede não carregadas"
    if "--no-route" not in sys.argv:
        route(board, work, size=cfg["size"])
    gnd_zones(board, cfg)
    board.Save(str(pcb))
    board = pcbnew.LoadBoard(str(pcb))
    v, u = drc(board, work / "drc.rpt")
    print(f"✓ {pcb.name}: {len(board.GetFootprints())} footprints, "
          f"{len(board.GetTracks())} trilhas/vias, DRC={v} violações, {u} não conectados")


if __name__ == "__main__":
    os.environ.setdefault("KICAD7_FOOTPRINT_DIR", str(FPLIB))
    os.environ.setdefault("KICAD7_SYMBOL_DIR", "/usr/share/kicad/symbols")
    os.environ.setdefault("KICAD6_3DMODEL_DIR", "/usr/share/kicad/3dmodels")
    os.environ.setdefault("KICAD7_3DMODEL_DIR", "/usr/share/kicad/3dmodels")
    main()
