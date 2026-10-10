"""Métricas de un resultado de engine.correr_backtest."""

import numpy as np
import pandas as pd

import config


def calcular_metricas(resultado, df, fee_buy_hold=0.001):
    trades = resultado["trades"]
    equity = resultado["equity"]
    cap0 = resultado["capital_inicial"]

    n = len(trades)
    out = {"n_operaciones": n}

    if n:
        neto = trades["neto"]
        ganancias = neto[neto > 0].sum()
        perdidas = -neto[neto < 0].sum()
        out["win_rate"] = float((neto > 0).mean())
        out["profit_factor"] = float(ganancias / perdidas) if perdidas > 0 else float("inf")
        out["expectancy_usd"] = float(neto.mean())
        out["expectancy_r"] = float(trades["r"].mean())
        out["comisiones"] = float(trades["comisiones"].sum())
        out["funding"] = float(trades["funding"].sum())
    else:
        for k in ("win_rate", "profit_factor", "expectancy_usd", "expectancy_r"):
            out[k] = float("nan")
        out["comisiones"] = 0.0
        out["funding"] = 0.0

    # Capital final a mercado (incluye posición abierta, si la hay)
    eq = equity["equity"].to_numpy()
    out["capital_final"] = float(eq[-1]) if len(eq) else cap0
    out["resultado_neto"] = out["capital_final"] - cap0
    out["retorno_pct"] = out["resultado_neto"] / cap0 * 100

    # Drawdown máximo %, incluyendo la posición abierta (peor punto de cada vela)
    if len(eq):
        pico = np.maximum.accumulate(np.maximum(eq, cap0))
        dd = (pico - equity["equity_peor"].to_numpy()) / pico
        out["drawdown_max_pct"] = float(dd.max() * 100)
    else:
        out["drawdown_max_pct"] = 0.0

    # Sharpe: retornos diarios (UTC), anualizado con raíz de 365
    if len(equity):
        dias = pd.to_datetime(equity["timestamp"], unit="ms", utc=True).dt.floor("D")
        diario = equity.groupby(dias)["equity"].last()
        serie = pd.concat([pd.Series([cap0]), diario.reset_index(drop=True)])
        ret = serie.pct_change().dropna()
        if len(ret) >= 2 and ret.std(ddof=1) > 0:
            out["sharpe"] = float(ret.mean() / ret.std(ddof=1) * np.sqrt(365))
        else:
            out["sharpe"] = float("nan")
    else:
        out["sharpe"] = float("nan")

    # Buy & hold: compra en la 1ª apertura, vende en el último cierre, con comisiones
    bh = (df["close"].iloc[-1] / df["open"].iloc[0] - 1 - 2 * fee_buy_hold) * 100
    out["buy_hold_pct"] = float(bh)
    out["vs_buy_hold_pct"] = out["retorno_pct"] - out["buy_hold_pct"]

    out["aviso"] = (
        f"Solo {n} operaciones (< {config.MIN_OPERACIONES_CONCLUYENTE}): "
        "resultado NO concluyente"
        if n < config.MIN_OPERACIONES_CONCLUYENTE
        else ""
    )
    return out
