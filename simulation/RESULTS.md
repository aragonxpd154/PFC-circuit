# Resultados das simulações (gerado por `run_sims.py`)

| Grandeza | Simulado | Calculado (`tools/pfc_calc.py`) |
|---|---|---|
| Frequência do oscilador | 82,6 kHz | 83,9 kHz |
| Pico da rampa em C15 (D = 40 %) | 3,91 V | 3,91 V |
| Rampa somada em ILIMIT (pico) | 109 mV | 114 mV |
| Gate: tempo de subida 10–90 % | 184 ns | — |
| Gate: tempo de descida 90–10 % | 56 ns (sem diodo: 184 ns) | — |

## Feed-forward de linha

| Linha | VRMS médio (calculado) | Ondulação p-p | IAC de pico (calculado) |
|---|---|---|---|
| 90 Vac | 1,000 V (1,000 V) | 2,0 mV | 135 µA (135 µA) |
| 115 Vac | 1,278 V (1,278 V) | 2,5 mV | 173 µA (173 µA) |
| 230 Vac | 2,556 V (2,556 V) | 5,0 mV | 346 µA (346 µA) |
| 264 Vac | 2,934 V (2,933 V) | 5,8 mV | 397 µA (397 µA) |
