"""
Motor de backtest unificado. SOLO BACKTEST / PAPER TRADING: no envía órdenes.

Sin look-ahead:
  - La señal de la vela i se decide con datos hasta el cierre de i.
  - La entrada es en la apertura de i+1 (más slippage).
  - SL y TP salen del ATR de la vela i (la de la señal).

El motor recibe las señales ya calculadas (array alineado con df):
  +1 = LONG, -1 = SHORT, 0 = nada. df debe traer la columna "atr".
"""

import numpy as np
import pandas as pd

import config


def _tasa(fees, tipo):
    return fees[tipo]


def correr_backtest(
    df,
    senal,
    *,
    salida_senal=None,
    mercado=None,
    capital_inicial=None,
    riesgo=None,
    atr_stop=2.0,
    rr_neto=None,
    rr_bruto=None,
    min_tp_vs_costos=None,
    cooldown=0,
    fees=None,
    slippage=None,
    slippage_stop=None,
    apalancamiento=None,
    permitir_short=None,
    funding=None,
):
    """
    salida_senal: array opcional; si en la vela i vale +1 (o -1) y hay un LONG
        (o SHORT) abierto, se sale en la apertura de i+1 con slippage.
    rr_neto:  TP tal que (TP - costos) / (SL + costos) = rr_neto.
    rr_bruto: si se indica, TP = rr_bruto x distancia al stop (solo para
        reproducir las condiciones de la V7 original).
    funding: DataFrame con fundingTime, fundingRate y opcional markPrice.
    """

    mercado = mercado or config.MERCADO
    capital_inicial = config.INITIAL_BALANCE if capital_inicial is None else capital_inicial
    riesgo = config.RISK_PER_TRADE if riesgo is None else riesgo
    rr_neto = config.MIN_RR_NETO if rr_neto is None else rr_neto
    min_tp_vs_costos = (
        config.MIN_TP_VS_COSTOS if min_tp_vs_costos is None else min_tp_vs_costos
    )
    fees = config.FEES[mercado] if fees is None else fees
    slippage = config.SLIPPAGE_RATE if slippage is None else slippage
    slippage_stop = (
        config.SLIPPAGE_STOP_RATE if slippage_stop is None else slippage_stop
    )
    apalancamiento = (
        config.APALANCAMIENTO_MAX[mercado] if apalancamiento is None else apalancamiento
    )
    permitir_short = (mercado == "futuros") if permitir_short is None else permitir_short

    f_ent = _tasa(fees, config.TIPO_ORDEN_ENTRADA)
    f_tp = _tasa(fees, config.TIPO_ORDEN_TP)
    f_stop = _tasa(fees, config.TIPO_ORDEN_STOP)
    f_sen = _tasa(fees, config.TIPO_ORDEN_SALIDA_SENAL)

    ts = df["timestamp"].to_numpy(dtype="int64")
    o = df["open"].to_numpy(dtype=float)
    h = df["high"].to_numpy(dtype=float)
    l = df["low"].to_numpy(dtype=float)
    c = df["close"].to_numpy(dtype=float)
    atr = df["atr"].to_numpy(dtype=float)
    n = len(df)

    sen = np.nan_to_num(np.asarray(senal, dtype=float))
    sal = (
        np.nan_to_num(np.asarray(salida_senal, dtype=float))
        if salida_senal is not None
        else np.zeros(n)
    )

    # Funding por vela: idx -> [(instante, tasa, precio_marca)]
    fund_por_idx = {}
    if funding is not None and mercado == "futuros" and len(funding):
        ft = funding["fundingTime"].to_numpy(dtype="int64")
        fr = funding["fundingRate"].to_numpy(dtype=float)
        mk = (
            funding["markPrice"].to_numpy(dtype=float)
            if "markPrice" in funding.columns
            else np.full(len(ft), np.nan)
        )
        idxs = np.searchsorted(ts, ft, side="right") - 1
        for k in range(len(ft)):
            if 0 <= idxs[k] < n:
                fund_por_idx.setdefault(int(idxs[k]), []).append((ft[k], fr[k], mk[k]))

    capital = float(capital_inicial)
    pos = None
    pend = None
    ultima_salida = -10**9
    trades = []
    eq = np.empty(n)
    eq_peor = np.empty(n)
    rech = {"tp_vs_costos": 0, "atr_invalido": 0, "qty_cero": 0, "short_en_spot": 0}
    detenido = False
    fin = n

    for i in range(n):

        # ---------------- ENTRADA (señal de la vela anterior) ----------------
        if pos is None and pend is not None:
            lado, atr_s = pend
            pend = None

            if not (atr_s == atr_s) or atr_s <= 0:
                rech["atr_invalido"] += 1
            else:
                entrada = o[i] * (1 + lado * slippage)
                d = atr_s * atr_stop

                c_sl = entrada * (f_ent + f_stop + slippage_stop)
                c_tp = entrada * (f_ent + f_tp)
                c_rt = entrada * (f_ent + f_tp + 2 * slippage)

                if rr_bruto is not None:
                    tp_dist = rr_bruto * d
                else:
                    tp_dist = rr_neto * (d + c_sl) + c_tp

                if tp_dist < min_tp_vs_costos * c_rt:
                    rech["tp_vs_costos"] += 1
                else:
                    qty = capital * riesgo / (d + c_sl)
                    qty = min(qty, capital * apalancamiento / entrada)
                    if qty <= 0:
                        rech["qty_cero"] += 1
                    else:
                        fee_in = entrada * qty * f_ent
                        capital -= fee_in
                        pos = {
                            "lado": lado,
                            "entrada": entrada,
                            "qty": qty,
                            "sl": entrada - lado * d,
                            "tp": entrada + lado * tp_dist,
                            "idx_e": i,
                            "idx_senal": i - 1,
                            "fee_in": fee_in,
                            "funding": 0.0,
                            "r_usd": qty * (d + c_sl),
                        }

        # ---------------- GESTIÓN DE LA POSICIÓN ----------------
        if pos is not None:
            s = pos["lado"]

            for f_t, f_r, f_m in fund_por_idx.get(i, ()):
                # Cobra si la posición ya existía antes de la vela o
                # se abrió antes del instante del funding.
                if pos["idx_e"] < i or f_t > ts[i]:
                    precio = f_m if f_m == f_m else o[i]
                    pago = -s * pos["qty"] * precio * f_r
                    pos["funding"] += pago
                    capital += pago

            salida = None
            if i > pos["idx_e"] and s * (o[i] - pos["sl"]) <= 0:
                salida = (o[i] * (1 - s * slippage_stop), "GAP_STOP", f_stop)
            elif i > pos["idx_e"] and sal[i - 1] == s:
                salida = (o[i] * (1 - s * slippage), "SALIDA_SENAL", f_sen)
            else:
                adverso = l[i] if s == 1 else h[i]
                favorable = h[i] if s == 1 else l[i]
                toca_sl = s * (adverso - pos["sl"]) <= 0
                toca_tp = s * (favorable - pos["tp"]) >= 0
                if toca_sl:
                    motivo = "STOP_Y_TP" if toca_tp else "STOP"
                    salida = (pos["sl"] * (1 - s * slippage_stop), motivo, f_stop)
                elif toca_tp:
                    salida = (pos["tp"], "TP", f_tp)

            if salida is not None:
                precio_s, motivo, f_out = salida
                bruto = s * (precio_s - pos["entrada"]) * pos["qty"]
                fee_out = precio_s * pos["qty"] * f_out
                capital += bruto - fee_out
                comisiones = pos["fee_in"] + fee_out
                neto = bruto - comisiones + pos["funding"]
                trades.append({
                    "lado": "LONG" if s == 1 else "SHORT",
                    "idx_senal": pos["idx_senal"],
                    "idx_entrada": pos["idx_e"],
                    "idx_salida": i,
                    "ts_entrada": int(ts[pos["idx_e"]]),
                    "ts_salida": int(ts[i]),
                    "entrada": pos["entrada"],
                    "salida": precio_s,
                    "qty": pos["qty"],
                    "sl": pos["sl"],
                    "tp": pos["tp"],
                    "bruto": bruto,
                    "comisiones": comisiones,
                    "funding": pos["funding"],
                    "neto": neto,
                    "r_usd": pos["r_usd"],
                    "r": neto / pos["r_usd"],
                    "motivo": motivo,
                    "capital": capital,
                })
                pos = None
                ultima_salida = i

        # ---------------- CAPITAL A MERCADO ----------------
        if pos is None:
            eq[i] = capital
            eq_peor[i] = capital
        else:
            s = pos["lado"]
            eq[i] = capital + s * (c[i] - pos["entrada"]) * pos["qty"]
            peor = l[i] if s == 1 else h[i]
            eq_peor[i] = min(eq[i], capital + s * (peor - pos["entrada"]) * pos["qty"])

        # ---------------- NUEVA SEÑAL (se ejecuta en i+1) ----------------
        if pos is None:
            if capital <= capital_inicial * config.CAPITAL_MINIMO_PORCENTAJE:
                detenido = True
                fin = i + 1
                break
            if pend is None and i - ultima_salida >= max(cooldown, 1) and sen[i] != 0:
                if sen[i] < 0 and not permitir_short:
                    rech["short_en_spot"] += 1
                else:
                    pend = (1 if sen[i] > 0 else -1, atr[i])

    equity = pd.DataFrame({
        "timestamp": ts[:fin],
        "equity": eq[:fin],
        "equity_peor": eq_peor[:fin],
    })

    return {
        "trades": pd.DataFrame(trades),
        "equity": equity,
        "rechazadas": rech,
        "detenido": detenido,
        "posicion_abierta": pos is not None,
        "capital_inicial": float(capital_inicial),
    }
