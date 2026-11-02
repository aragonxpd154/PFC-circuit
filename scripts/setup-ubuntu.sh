#!/usr/bin/env bash
# Instala todas as dependências do PFC-circuit (Ubuntu 24.04 / Debian 12+ / Zorin OS 17+)
set -euo pipefail
cd "$(dirname "$0")/.."

echo "▶ pacotes do sistema (KiCad 7, ngspice, Java, rsvg)"
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  kicad kicad-footprints kicad-symbols kicad-packages3d \
  ngspice openjdk-17-jre-headless xvfb librsvg2-bin python3-pip nodejs npm

echo "▶ bibliotecas Python"
python3 -m pip install --user -r requirements.txt || \
  python3 -m pip install --break-system-packages -r requirements.txt

echo "▶ Freerouting 1.9.0 (autoroteador)"
mkdir -p tools/bin
[ -f tools/bin/freerouting-1.9.0.jar ] || curl -fsSL -o tools/bin/freerouting-1.9.0.jar \
  https://github.com/freerouting/freerouting/releases/download/v1.9.0/freerouting-1.9.0.jar

echo "▶ visualizador 3D (three.js + esbuild)"
(cd tools/render/viewer && npm install --silent)

echo "▶ tabelas de bibliotecas do KiCad (primeira execução)"
mkdir -p ~/.config/kicad/7.0
for t in fp-lib-table sym-lib-table; do
  [ -f ~/.config/kicad/7.0/$t ] || cp /usr/share/kicad/template/$t ~/.config/kicad/7.0/
done
echo "✓ pronto — rode: make check && make calc"
