"""Paso 7: tramo de prueba, UNA sola vez, B y B_sinTP en 4h spot."""
import os
import numpy as np
import pandas as pd
import config
import data_cache as dc
from data_cache import cargar_entrenamiento_spot
from metrics import calcular_metricas
from paso5_walkforward import correr, WARM, sharpe_diario

CAND = {
    "B_donchian": {"canal_entrada": 55, "atr_stop": 2.5},
    "B_sinTP": {"canal_entrada": 20, "atr_stop": 2.0},
}

ruta = os.path.join(config.CARPETA_DATOS, "BTCUSDT_spot_4h_prueba.csv")
if os.path.exists(ruta):
    raise SystemExit("La prueba ya se corrió una vez; no se repite.")
ini = dc._ms_utc(config.TEST_INICIO)
ahora = dc._ahora_ms()
prueba = dc._limpiar(dc._descargar_klines(dc.SPOT_URL, config.SYMBOL, "4h", (ahora - ini) // 86_400_000 + 1), "timestamp")[0]
prueba = prueba[prueba["timestamp"] >= ini].reset_index(drop=True)
prueba.to_csv(ruta, index=False)
tr = cargar_entrenamiento_spot("4h")
df = pd.concat([tr.iloc[-WARM:], prueba], ignore_index=True)
off = WARM
print("prueba:", len(prueba), "velas", pd.to_datetime(prueba.timestamp.iloc[0], unit="ms"), "->", pd.to_datetime(prueba.timestamp.iloc[-1], unit="ms"))

filas = []
for n, p in CAND.items():
    res = correr(n, df, p, off=off)
    res["equity"] = res["equity"][res["equity"]["timestamp"] >= ini]
    m = calcular_metricas(res, prueba)
    filas.append({"estrategia": n, "ops": m["n_operaciones"], "PF neto": m["profit_factor"],
                  "exp R": m["expectancy_r"], "ret%": m["retorno_pct"], "DD%": m["drawdown_max_pct"],
                  "Sharpe": m["sharpe"], "comis $": m["comisiones"],
                  "nota": "no concluyente" if m["n_operaciones"] < 100 else ""})
    bh_ret = m["buy_hold_pct"]
bh = prueba["close"].to_numpy() / prueba["open"].iloc[0] * config.INITIAL_BALANCE
pico = np.maximum.accumulate(bh)
bh_dd = float(((pico - bh) / pico).max() * 100)
bh_sh = sharpe_diario(prueba["timestamp"], bh, config.INITIAL_BALANCE)
for f in filas:
    f["B&H ret%"], f["B&H DD%"], f["B&H Sharpe"] = bh_ret, bh_dd, bh_sh
    f["aprobado"] = "SI" if (f["PF neto"] > 1.1 and f["DD%"] < bh_dd) else "NO"
t = pd.DataFrame(filas)
t.to_csv(os.path.join(config.CARPETA_RESULTADOS, "paso7_prueba.csv"), index=False)
pd.options.display.width = 250
pd.options.display.float_format = "{:.2f}".format
print(t.to_string(index=False))
