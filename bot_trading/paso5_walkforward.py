"""
Paso 5: walk-forward SOLO sobre entrenamiento (< config.TEST_INICIO).
Estrategias A, B, C, A_sinTP, B_sinTP en 4h y 1d. Spot, solo LONG.
"""

import itertools
import os

import numpy as np
import pandas as pd

import config
from data_cache import cargar_entrenamiento_spot
from engine import correr_backtest
from estrategias import FUNCIONES, generar
from metrics import calcular_metricas

DIA_MS = 86_400_000
WARM = 500  # velas previas a la ventana de prueba, solo para calentar indicadores


def correr(nombre, df, params, off=0, capital=None):
    """Backtest sobre df; las señales antes de la fila `off` se anulan."""
    s = generar(nombre, df, params)
    sen = s["senal"].copy()
    sen[:off] = 0
    sal = None if s["salida"] is None else s["salida"].copy()
    kw = {"capital_inicial": capital} if capital else {}
    if nombre in config.SIN_TP:
        kw["rr_neto"] = config.RR_SIN_TP
    return correr_backtest(
        df.assign(atr=s["atr"]), sen, salida_senal=sal, mercado="spot",
        atr_stop=s["atr_stop"], **kw,
    )


def combinaciones(nombre):
    g = config.ESTRATEGIAS[nombre]["grilla"]
    claves = list(g)
    return [dict(zip(claves, v)) for v in itertools.product(*g.values())]


def elegir(nombre, df_train):
    """Mayor expectancy R en entrenamiento; sin operaciones -> default."""
    mejor, mejor_s = None, -np.inf
    for p in combinaciones(nombre):
        t = correr(nombre, df_train, p)["trades"]
        if len(t) and t["r"].mean() > mejor_s:
            mejor, mejor_s = p, t["r"].mean()
    return mejor


def sharpe_diario(ts, valores, cap0):
    dias = pd.to_datetime(np.asarray(ts), unit="ms", utc=True).floor("D")
    d = pd.Series(np.asarray(valores)).groupby(np.asarray(dias)).last()
    r = pd.concat([pd.Series([cap0]), d.reset_index(drop=True)]).pct_change().dropna()
    return float(r.mean() / r.std(ddof=1) * np.sqrt(365)) if len(r) > 1 and r.std(ddof=1) > 0 else float("nan")


def walk_forward(nombre, tf, df):
    dt, dp = config.WF_VENTANAS[tf]
    paso = DIA_MS
    ts = df["timestamp"].to_numpy()
    t0, fin = ts[0], ts[-1] + 1
    ini_train = t0
    capital = config.INITIAL_BALANCE
    trades, eqs, rets = [], [], []
    ini_oos = None
    while ini_train + (dt + dp) * paso <= fin + 1:
        a, b, c = ini_train, ini_train + dt * paso, ini_train + (dt + dp) * paso
        i_a, i_b, i_c = (int(np.searchsorted(ts, x)) for x in (a, b, c))
        params = elegir(nombre, df.iloc[i_a:i_b].reset_index(drop=True))
        lo = max(0, i_b - WARM)
        sl = df.iloc[lo:i_c].reset_index(drop=True)
        res = correr(nombre, sl, params, off=i_b - lo, capital=capital)
        eq = res["equity"]
        eq = eq[eq["timestamp"] >= ts[i_b]]
        cap_ini = capital
        capital = float(eq["equity"].iloc[-1]) if len(eq) else capital
        rets.append(capital / cap_ini - 1)
        eqs.append(eq)
        if len(res["trades"]):
            trades.append(res["trades"])
        ini_oos = ts[i_b] if ini_oos is None else ini_oos
        fin_oos = ts[i_c - 1]
        ini_train += dp * paso
    equity = pd.concat(eqs, ignore_index=True)
    tr = pd.concat(trades, ignore_index=True) if trades else pd.DataFrame()
    return tr, equity, rets, ini_oos, fin_oos


def main():
    filas = []
    for tf in config.TIMEFRAMES:
        df = cargar_entrenamiento_spot(tf)
        assert df["timestamp"].max() < pd.Timestamp(config.TEST_INICIO, tz="UTC").timestamp() * 1000
        for nombre in FUNCIONES:
            tr, eq, rets, ini, fin = walk_forward(nombre, tf, df)
            res = {"trades": tr, "equity": eq, "capital_inicial": config.INITIAL_BALANCE}
            tramo = df[(df["timestamp"] >= ini) & (df["timestamp"] <= fin)]
            m = calcular_metricas(res, tramo)
            bh = tramo["close"].to_numpy() / tramo["open"].iloc[0] * config.INITIAL_BALANCE
            pico = np.maximum.accumulate(bh)
            filas.append({
                "estrategia": nombre, "tf": tf, "ventanas": len(rets),
                "ops": m["n_operaciones"], "PF neto": m["profit_factor"],
                "exp R": m["expectancy_r"], "ret%": m["retorno_pct"],
                "DD%": m["drawdown_max_pct"], "Sharpe": m["sharpe"],
                "vent+%": np.mean(np.array(rets) > 0) * 100,
                "B&H ret%": m["buy_hold_pct"],
                "B&H DD%": float(((pico - bh) / pico).max() * 100),
                "B&H Sharpe": sharpe_diario(tramo["timestamp"], bh, config.INITIAL_BALANCE),
                "nota": "no concluyente" if m["n_operaciones"] < config.MIN_OPERACIONES_CONCLUYENTE else "",
            })
    t = pd.DataFrame(filas)
    os.makedirs(config.CARPETA_RESULTADOS, exist_ok=True)
    t.to_csv(os.path.join(config.CARPETA_RESULTADOS, "paso5_walkforward.csv"), index=False)
    pd.options.display.width = 250
    pd.options.display.float_format = "{:.2f}".format
    print(t.to_string(index=False))


if __name__ == "__main__":
    main()
