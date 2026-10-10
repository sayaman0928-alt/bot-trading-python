"""
Paso 4: estrategias A, B y C en spot (solo LONG), SOLO sobre el primer
config.TRAIN_FRACCION de los datos. El tramo de prueba no se carga ni se usa.
"""

import os

import pandas as pd

import config
from engine import correr_backtest
from estrategias import FUNCIONES, generar
from metrics import calcular_metricas


def cargar_entrenamiento(tf, mercado="spot", symbol=None):
    symbol = symbol or config.SYMBOL
    ruta = os.path.join(config.CARPETA_DATOS, f"{symbol}_{mercado}_{tf}.csv")
    df = pd.read_csv(ruta).sort_values("timestamp").reset_index(drop=True)
    corte = int(len(df) * config.TRAIN_FRACCION)
    return df.iloc[:corte].reset_index(drop=True)  # el resto no se usa


def correr_estrategia(nombre, df, params=None, **kw):
    s = generar(nombre, df, params)
    d = df.assign(atr=s["atr"])
    res = correr_backtest(
        d, s["senal"], salida_senal=s["salida"], mercado="spot",
        atr_stop=s["atr_stop"], **kw,
    )
    return res, d


def main():
    filas = []
    tramos = {}
    for tf in config.TIMEFRAMES:
        df = cargar_entrenamiento(tf)
        tramos[tf] = (len(df), df["timestamp"].iloc[0], df["timestamp"].iloc[-1])
        for nombre in FUNCIONES:
            res, d = correr_estrategia(nombre, df)
            m = calcular_metricas(res, d)
            filas.append({
                "estrategia": nombre, "tf": tf,
                "ops": m["n_operaciones"],
                "win%": m["win_rate"] * 100,
                "PF neto": m["profit_factor"],
                "exp R": m["expectancy_r"],
                "retorno%": m["retorno_pct"],
                "DD%": m["drawdown_max_pct"],
                "comisiones $": m["comisiones"],
                "B&H%": m["buy_hold_pct"],
                "nota": "no concluyente" if m["n_operaciones"] < config.MIN_OPERACIONES_CONCLUYENTE else "",
            })

    t = pd.DataFrame(filas)
    os.makedirs(config.CARPETA_RESULTADOS, exist_ok=True)
    t.to_csv(os.path.join(config.CARPETA_RESULTADOS, "paso4_entrenamiento.csv"), index=False)

    for tf, (n, a, b) in tramos.items():
        print(f"{tf}: {n} velas, {pd.to_datetime(a, unit='ms')} -> {pd.to_datetime(b, unit='ms')}")
    pd.options.display.width = 220
    pd.options.display.float_format = "{:.3f}".format
    print(t.to_string(index=False))


if __name__ == "__main__":
    main()
