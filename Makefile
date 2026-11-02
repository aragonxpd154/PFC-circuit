# PFC-circuit — atalhos do fluxo de projeto
#   make help        lista os alvos
PY ?= python3
BUILD = $(PY) tools/build_all.py

.PHONY: help setup check calc sim sch pcb fab render viewer all clean

help:            ## mostra esta ajuda
	@grep -E '^[a-z]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[1m%-8s\033[0m %s\n", $$1, $$2}'

setup:           ## instala dependências (Ubuntu/Debian/Zorin)
	./scripts/setup-ubuntu.sh

check:           ## netlist == designs.py e DRC = 0 nas duas placas
	$(PY) tools/eda/check.py

calc:            ## calculadora de projeto (pontos de operação)
	$(PY) tools/pfc_calc.py

sim:             ## simulações ngspice + gráficos em docs/images
	$(BUILD) sim

sch:             ## regenera os esquemáticos a partir de tools/eda/designs.py
	$(BUILD) sym sch

pcb:             ## posiciona, roteia (Freerouting), planos de GND, DRC
	$(BUILD) pcb

fab:             ## Gerbers, furação, BOM, pick-and-place, STEP, PDFs
	$(BUILD) fab

render:          ## texturas, GLB/STL, imagens 2D e 3D
	$(BUILD) tex mesh images viewer

viewer:          ## abre o visualizador 3D no navegador
	xdg-open docs/3d/viewer.html 2>/dev/null || open docs/3d/viewer.html

all:             ## pipeline completo (sch → pcb → fab → render → sim)
	$(BUILD)

clean:           ## remove artefatos temporários
	rm -rf build simulation/out tools/eda/logs
