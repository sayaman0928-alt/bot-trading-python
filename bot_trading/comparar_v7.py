"""
Corre la V7 original (strategy.evaluar_condiciones, sin modificar) en el motor
nuevo, con los parámetros V7_ORIGINAL de config.py, y la compara con el -1,58%.
"""

import numpy as np

import config
import data_cache
from engine import correr_backtest
from indicators import calcular_indicadores
from metrics import calcular_metricas
from strategy import evaluar_condiciones

RESULTADO_ORIGINAL_PCT = -1.58


def senales_v7_original(df):
    """+1 / -1 / 0 por vela, usando solo datos hasta el cierre de esa vela."""
    sen = np.zeros(len(df))
    for i, vela in enumerate(df.to_dict("records")):
        r = evaluar_condiciones(vela)
        if r.get("long"):
            sen[i] = 1
        elif r.get("short"):
            sen[i] = -1
    return sen


def _fila(nombre, res, df):
    m = calcular_metricas(res, df)
    return {
        "variante": nombre,
        "ops": m["n_operaciones"],
        "win%": m["win_rate"] * 100,
        "PF": m["profit_factor"],
        "exp_R": m["expectancy_r"],
        "neto_$": m["resultado_neto"],
        "retorno%": m["retorno_pct"],
        "DD%": m["drawdown_max_pct"],
        "comis_$": m["comisiones"],
        "B&H%": m["buy_hold_pct"],
    }


def correr():
    v = config.V7_ORIGINAL
    df = data_cache.cargar_velas_cacheadas(
        config.SYMBOL, "spot", v["intervalo"], v["dias"]
    )
    df = calcular_indicadores(df)
    sen = senales_v7_original(df)

    comun = dict(
        riesgo=v["riesgo"],
        atr_stop=v["atr_stop"],
        cooldown=v["cooldown_velas"],
    )
    # Condiciones de la V7 original: comisión 0,1%, long+short, 1x, TP bruto 2R,
    # y solo exige que el TP cubra los costos (como su filtro de TP neto > 0).
    orig = dict(
        comun, mercado="spot", permitir_short=True,
        rr_bruto=v["rr_bruto"], min_tp_vs_costos=1.0,
    )

    filas = [
        _fila(
            "Motor nuevo, condiciones V7, sin slippage",
            correr_backtest(df, sen, slippage=0.0, slippage_stop=0.0, **orig), df,
        ),
        _fila(
            "Motor nuevo, condiciones V7, con slippage",
            correr_backtest(df, sen, **orig), df,
        ),
        _fila(
            "Motor nuevo, spot long-only, TP 1:2 neto",
            correr_backtest(df, sen, mercado="spot", rr_neto=2.0, **comun), df,
        ),
    ]
    return df, filas


if __name__ == "__main__":
    import pandas as pd

    df, filas = correr()
    t = pd.DataFrame(filas)
    pd.options.display.float_format = "{:.2f}".format
    pd.options.display.width = 200
    print(f"Velas: {len(df)} | "
          f"{pd.to_datetime(df['timestamp'].iloc[0], unit='ms')} -> "
          f"{pd.to_datetime(df['timestamp'].iloc[-1], unit='ms')}")
    print(t.to_string(index=False))
    print(f"V7 original (referencia): {RESULTADO_ORIGINAL_PCT}%")
