"""
Estrategias A, B y C. Solo generan señales (SOLO LONG); no operan.

Cada estrategia recibe el DataFrame de velas y devuelve un dict:
    senal:     array +1 / 0 (señal de entrada al CIERRE de la vela i)
    salida:    array +1 / 0 (señal de salida al cierre de i) o None
    atr:       Series ATR (la usa el motor para SL / TP)
    atr_stop:  múltiplo de ATR para el stop

Todo se calcula solo con datos hasta la vela i (EMAs, rolling y shift hacia
atrás), así que cambiar velas futuras no altera señales pasadas.
Parámetros en config.ESTRATEGIAS.
"""

import numpy as np

import config
from indicators import calcular_atr, calcular_rsi


def _ema(serie, periodo):
    return serie.ewm(span=periodo, adjust=False).mean()


def estrategia_A(df, ema_rapida, ema_lenta, rsi_umbral, atr_stop):
    """Tendencia EMA rápida > EMA lenta + pullback: el RSI cae bajo el umbral
    y se recupera (cruce hacia arriba) con el cierre sobre la EMA lenta."""
    close = df["close"]
    rsi = calcular_rsi(df, 14)
    tendencia = (_ema(close, ema_rapida) > _ema(close, ema_lenta)) & (
        close > _ema(close, ema_lenta)
    )
    cruce = (rsi.shift(1) < rsi_umbral) & (rsi >= rsi_umbral)
    senal = (tendencia & cruce).to_numpy(dtype=float)
    return {
        "senal": senal, "salida": None,
        "atr": calcular_atr(df, config.ATR_PERIOD), "atr_stop": atr_stop,
    }


def estrategia_B(df, canal_entrada, canal_salida, ema_filtro, atr_stop):
    """Breakout de Donchian: cierre sobre el máximo de las `canal_entrada`
    velas previas, con filtro de EMA. Sale si cierra bajo el mínimo de las
    `canal_salida` velas previas."""
    close = df["close"]
    techo = df["high"].rolling(canal_entrada).max().shift(1)
    piso = df["low"].rolling(canal_salida).min().shift(1)
    entrada = (close > techo) & (close > _ema(close, ema_filtro))
    salida = close < piso
    return {
        "senal": entrada.to_numpy(dtype=float),
        "salida": salida.to_numpy(dtype=float),
        "atr": calcular_atr(df, config.ATR_PERIOD), "atr_stop": atr_stop,
    }


def estrategia_C(df, distancia_ema20_atr, rsi_min, rsi_max, atr_stop):
    """V7 simplificada: tendencia (EMA20 > EMA50 > EMA200), cierre entre la
    EMA20 y EMA20 + k x ATR, RSI en rango. Sin rechazo, volumen, cuerpo ni
    filtro de vela excesiva."""
    close = df["close"]
    atr = calcular_atr(df, config.ATR_PERIOD)
    ema20, ema50, ema200 = _ema(close, 20), _ema(close, 50), _ema(close, 200)
    rsi = calcular_rsi(df, 14)
    tendencia = (ema50 > ema200) & (ema20 > ema50)
    precio = (close >= ema20) & (close <= ema20 + atr * distancia_ema20_atr)
    rsi_ok = (rsi >= rsi_min) & (rsi <= rsi_max)
    senal = (tendencia & precio & rsi_ok).to_numpy(dtype=float)
    return {"senal": senal, "salida": None, "atr": atr, "atr_stop": atr_stop}


def estrategia_A_sinTP(df, ema_rapida, ema_lenta, rsi_umbral, atr_stop):
    """Entrada de A; sale cuando el cierre cae bajo la EMA rápida."""
    r = estrategia_A(df, ema_rapida, ema_lenta, rsi_umbral, atr_stop)
    r["salida"] = (df["close"] < _ema(df["close"], ema_rapida)).to_numpy(dtype=float)
    return r


def estrategia_B_sinTP(df, canal_entrada, canal_salida, ema_filtro, atr_stop):
    """Entrada de B; solo salida por canal (el TP no existe en el motor)."""
    return estrategia_B(df, canal_entrada, canal_salida, ema_filtro, atr_stop)


FUNCIONES = {
    "A_tendencia_pullback": estrategia_A,
    "B_donchian": estrategia_B,
    "C_v7_simplificada": estrategia_C,
    "A_sinTP": estrategia_A_sinTP,
    "B_sinTP": estrategia_B_sinTP,
}


def generar(nombre, df, params=None):
    """Señales de `nombre`; por defecto usa los parámetros "default" de config."""
    p = dict(config.ESTRATEGIAS[nombre]["default"])
    if params:
        p.update(params)
    return FUNCIONES[nombre](df, **p)
