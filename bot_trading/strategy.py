def evaluar_condiciones(vela):
    """
    ESTRATEGIA V7

    Busca setups de continuación después de un retroceso
    dentro de una tendencia definida.

    La estrategia solamente genera señales.
    El backtest decide si la operación es económicamente
    viable teniendo en cuenta las comisiones.
    """

    # ============================================================
    # DATOS
    # ============================================================

    rsi = vela["rsi"]

    close = vela["close"]
    open_price = vela["open"]
    high = vela["high"]
    low = vela["low"]

    ema20 = vela["ema_20"]
    ema50 = vela["ema_50"]
    ema200 = vela["ema_200"]

    volume = vela["volume"]
    volume_avg = vela["volumen_promedio"]

    cuerpo = vela["cuerpo"]
    rango = vela["rango_total"]

    mecha_sup = vela["mecha_sup"]
    mecha_inf = vela["mecha_inf"]

    atr = vela["atr"]

    # ============================================================
    # VALIDACIÓN
    # ============================================================

    valores = [
        rsi,
        close,
        open_price,
        high,
        low,
        ema20,
        ema50,
        ema200,
        volume,
        volume_avg,
        cuerpo,
        rango,
        mecha_sup,
        mecha_inf,
        atr
    ]

    if any(valor != valor for valor in valores):
        return {
            "long": False,
            "short": False,
            "long_conditions": {},
            "short_conditions": {}
        }

    if rango <= 0:
        return {
            "long": False,
            "short": False,
            "long_conditions": {},
            "short_conditions": {}
        }

    if atr <= 0:
        return {
            "long": False,
            "short": False,
            "long_conditions": {},
            "short_conditions": {}
        }

    if volume_avg <= 0:
        return {
            "long": False,
            "short": False,
            "long_conditions": {},
            "short_conditions": {}
        }

    # ============================================================
    # ESTRUCTURA DE LA VELA
    # ============================================================

    vela_alcista = close > open_price

    vela_bajista = close < open_price

    cuerpo_relativo = (
        cuerpo / rango
    )

    # ============================================================
    # POSICIÓN DEL CIERRE
    # ============================================================

    posicion_cierre = (
        close - low
    ) / rango

    # ============================================================
    # VOLUMEN
    # ============================================================

    volumen_confirmado = (
        volume >= volume_avg * 1.05
    )

    # ============================================================
    # TENDENCIA LONG
    # ============================================================

    tendencia_long = (
        ema50 > ema200
        and ema20 > ema50
    )

    # ============================================================
    # TENDENCIA SHORT
    # ============================================================

    tendencia_short = (
        ema50 < ema200
        and ema20 < ema50
    )

    # ============================================================
    # PRECIO LONG
    # ============================================================

    precio_long = (
        close >= ema20
        and close <= ema20 + atr * 0.75
    )

    # ============================================================
    # PRECIO SHORT
    # ============================================================

    precio_short = (
        close <= ema20
        and close >= ema20 - atr * 0.75
    )

    # ============================================================
    # RSI LONG
    # ============================================================

    rsi_long = (
        rsi >= 45
        and rsi <= 58
    )

    # ============================================================
    # RSI SHORT
    # ============================================================

    rsi_short = (
        rsi >= 42
        and rsi <= 55
    )

    # ============================================================
    # VELA LONG
    # ============================================================

    cuerpo_long = (
        vela_alcista
        and cuerpo_relativo >= 0.30
        and posicion_cierre >= 0.65
    )

    # ============================================================
    # VELA SHORT
    # ============================================================

    cuerpo_short = (
        vela_bajista
        and cuerpo_relativo >= 0.30
        and posicion_cierre <= 0.35
    )

    # ============================================================
    # RECHAZO LONG
    # ============================================================

    rechazo_long = (
        mecha_inf >= rango * 0.15
        and mecha_inf >= cuerpo * 0.50
    )

    # ============================================================
    # RECHAZO SHORT
    # ============================================================

    rechazo_short = (
        mecha_sup >= rango * 0.15
        and mecha_sup >= cuerpo * 0.50
    )

    # ============================================================
    # EVITAR VELAS EXCESIVAMENTE GRANDES
    # ============================================================

    vela_no_excesiva = (
        rango <= atr * 2.0
    )

    # ============================================================
    # SEÑAL LONG
    # ============================================================

    long_signal = (
        tendencia_long
        and precio_long
        and rsi_long
        and cuerpo_long
        and rechazo_long
        and volumen_confirmado
        and vela_no_excesiva
    )

    # ============================================================
    # SEÑAL SHORT
    # ============================================================

    short_signal = (
        tendencia_short
        and precio_short
        and rsi_short
        and cuerpo_short
        and rechazo_short
        and volumen_confirmado
        and vela_no_excesiva
    )

    # ============================================================
    # RESULTADO
    # ============================================================

    return {
        "long": long_signal,

        "short": short_signal,

        "long_conditions": {
            "tendencia": tendencia_long,
            "precio": precio_long,
            "rsi": rsi_long,
            "vela": cuerpo_long,
            "rechazo": rechazo_long,
            "volumen": volumen_confirmado,
            "vela_no_excesiva": vela_no_excesiva
        },

        "short_conditions": {
            "tendencia": tendencia_short,
            "precio": precio_short,
            "rsi": rsi_short,
            "vela": cuerpo_short,
            "rechazo": rechazo_short,
            "volumen": volumen_confirmado,
            "vela_no_excesiva": vela_no_excesiva
        }
    }