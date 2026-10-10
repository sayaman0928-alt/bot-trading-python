import pandas as pd
import numpy as np


# ==============================================================
# RSI
# ==============================================================

def calcular_rsi(df, periodo=14):
    """
    Calcula RSI usando ganancias y pérdidas promedio.
    """

    delta = df["close"].diff()

    ganancias = delta.clip(lower=0)

    perdidas = -delta.clip(upper=0)

    ganancia_media = ganancias.rolling(
        window=periodo
    ).mean()

    perdida_media = perdidas.rolling(
        window=periodo
    ).mean()

    rs = ganancia_media / perdida_media.replace(
        0,
        np.nan
    )

    rsi = 100 - (
        100 / (1 + rs)
    )

    return rsi


# ==============================================================
# ATR
# ==============================================================

def calcular_atr(df, periodo=14):
    """
    Average True Range.
    Mide la volatilidad del mercado.
    """

    high_low = (
        df["high"] - df["low"]
    )

    high_close = (
        df["high"]
        - df["close"].shift(1)
    ).abs()

    low_close = (
        df["low"]
        - df["close"].shift(1)
    ).abs()

    true_range = pd.concat(
        [
            high_low,
            high_close,
            low_close
        ],
        axis=1
    ).max(axis=1)

    atr = true_range.rolling(
        window=periodo
    ).mean()

    return atr


# ==============================================================
# TODOS LOS INDICADORES
# ==============================================================

def calcular_indicadores(df):
    """
    Calcula todos los indicadores utilizados
    por el sistema de trading.
    """

    df = df.copy()

    # ==========================================================
    # RSI 14
    # ==========================================================

    df["rsi"] = calcular_rsi(
        df,
        periodo=14
    )

    # ==========================================================
    # EMA 20
    # ==========================================================

    df["ema_20"] = (
        df["close"]
        .ewm(
            span=20,
            adjust=False
        )
        .mean()
    )

    # ==========================================================
    # EMA 50
    # ==========================================================

    df["ema_50"] = (
        df["close"]
        .ewm(
            span=50,
            adjust=False
        )
        .mean()
    )

    # ==========================================================
    # EMA 200
    # ==============================================================

    df["ema_200"] = (
        df["close"]
        .ewm(
            span=200,
            adjust=False
        )
        .mean()
    )

    # ==========================================================
    # ATR 14
    # ==============================================================

    df["atr"] = calcular_atr(
        df,
        periodo=14
    )

    # ==========================================================
    # CUERPO DE LA VELA
    # ==============================================================

    df["cuerpo"] = (
        df["close"]
        - df["open"]
    ).abs()

    # ==========================================================
    # RANGO TOTAL
    # ==============================================================

    df["rango_total"] = (
        df["high"]
        - df["low"]
    )

    # ==========================================================
    # MECHA SUPERIOR
    # ==============================================================

    df["mecha_sup"] = (
        df["high"]
        - df[["open", "close"]].max(axis=1)
    )

    # ==========================================================
    # MECHA INFERIOR
    # ==============================================================

    df["mecha_inf"] = (
        df[["open", "close"]].min(axis=1)
        - df["low"]
    )

    # ==========================================================
    # VOLUMEN PROMEDIO
    # ==============================================================

    df["volumen_promedio"] = (
        df["volume"]
        .rolling(
            window=20
        )
        .mean()
    )

    # ==========================================================
    # RELACIÓN CUERPO / RANGO
    # ==============================================================

    df["cuerpo_relativo"] = np.where(
        df["rango_total"] > 0,
        df["cuerpo"]
        / df["rango_total"],
        0
    )

    # ==========================================================
    # DIRECCIÓN DE LA VELA
    # ==============================================================

    df["vela_alcista"] = (
        df["close"] > df["open"]
    )

    df["vela_bajista"] = (
        df["close"] < df["open"]
    )

    return df