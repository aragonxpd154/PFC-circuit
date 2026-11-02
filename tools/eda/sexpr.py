"""Utilitários mínimos de S-expression para arquivos KiCad.

Sem dependências externas: usado para extrair símbolos das bibliotecas
oficiais do KiCad, ler pinos e verificar o netlist exportado.
"""
from __future__ import annotations

import re
import uuid as _uuid
from pathlib import Path

KICAD_SHARE = Path("/usr/share/kicad")


def new_uuid() -> str:
    return str(_uuid.uuid4())


def det_uuid(*parts: str) -> str:
    """UUID determinístico — gera arquivos reprodutíveis (diffs limpos no git)."""
    return str(_uuid.uuid5(_uuid.NAMESPACE_URL, "pfc-circuit/" + "/".join(parts)))


# --------------------------------------------------------------------------- parser
_TOKEN = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))')


def parse(text: str):
    """Converte texto S-expression em listas aninhadas de str."""
    stack: list[list] = [[]]
    pos = 0
    n = len(text)
    while pos < n:
        m = _TOKEN.match(text, pos)
        if not m:
            break
        pos = m.end()
        lpar, rpar, quoted, atom = m.groups()
        if lpar:
            stack.append([])
        elif rpar:
            node = stack.pop()
            stack[-1].append(node)
        elif quoted is not None:
            stack[-1].append(quoted.replace('\\"', '"'))
        elif atom is not None:
            stack[-1].append(atom)
    return stack[0][0] if stack[0] else None


def find_all(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


def find(node, key):
    for c in node:
        if isinstance(c, list) and c and c[0] == key:
            return c
    return None


# ------------------------------------------------------------- symbol extraction
def _balanced_block(text: str, start: int) -> str:
    depth = 0
    i = start
    in_str = False
    while i < len(text):
        ch = text[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        i += 1
    raise ValueError("bloco desbalanceado")


def library_symbol_text(lib_id: str, custom_libs: dict[str, Path] | None = None) -> str:
    """Retorna o bloco (symbol "Lib:Nome" ...) pronto para lib_symbols do .kicad_sch."""
    lib, name = lib_id.split(":", 1)
    if custom_libs and lib in custom_libs:
        path = custom_libs[lib]
    else:
        path = KICAD_SHARE / "symbols" / f"{lib}.kicad_sym"
    text = path.read_text(encoding="utf-8")
    m = re.search(r'\n\s*\(symbol "' + re.escape(name) + r'"', text)
    if not m:
        raise KeyError(lib_id)
    start = text.index("(", m.start())
    block = _balanced_block(text, start)
    # Renomeia somente o símbolo de topo (sub-unidades mantêm o nome curto)
    block = block.replace(f'(symbol "{name}"', f'(symbol "{lib_id}"', 1)
    return block


def symbol_pins(lib_id: str, custom_libs=None) -> dict[str, tuple[float, float, float]]:
    """{número_do_pino: (x, y, ângulo)} em coordenadas do símbolo (Y para cima)."""
    tree = parse(library_symbol_text(lib_id, custom_libs))
    pins: dict[str, tuple[float, float, float]] = {}

    def walk(node):
        for c in node:
            if isinstance(c, list) and c:
                if c[0] == "pin":
                    at = find(c, "at")
                    num = find(c, "number")
                    pins[num[1]] = (float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0)
                else:
                    walk(c)

    walk(tree)
    return pins
