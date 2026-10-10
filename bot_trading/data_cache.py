"""
Caché de datos históricos (solo endpoints públicos, sin API key).

Spot:     api.binance.com /api/v3/klines
Futuros:  fapi.binance.com /fapi/v1/klines y /fapi/v1/fundingRate

Guarda CSV en CARPETA_DATOS. Si el archivo existe, no se vuelve a descargar.
"""

import os
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

import config

SPOT_URL = "https://api.binance.com/api/v3/klines"
FUT_URL = "https://fapi.binance.com/fapi/v1/klines"
FUNDING_URL = "https://fapi.binance.com/fapi/v1/fundingRate"

COLUMNAS = [
    "timestamp", "open", "high", "low", "close", "volume",
    "close_time", "quote_asset_volume", "number_of_trades",
    "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore",
]
NUMERICAS = [
    "open", "high", "low", "close", "volume",
    "quote_asset_volume", "taker_buy_base_asset_volume",
    "taker_buy_quote_asset_volume",
]

INTERVALO_MS = {
    "1m": 60_000,
    "15m": 15 * 60_000,
    "1h": 60 * 60_000,
    "4h": 4 * 60 * 60_000,
    "1d": 24 * 60 * 60_000,
}
FUNDING_MS = 8 * 60 * 60_000


def _get(url, params):
    for intento in range(5):
        r = requests.get(url, params=params, timeout=15)
        if r.status_code in (418, 429):
            time.sleep(2 ** intento)
            continue
        r.raise_for_status()
        return r.json()
    r.raise_for_status()


def _ahora_ms():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _inicio_ms(ahora_ms, dias=None):
    dias = config.DIAS_HISTORICO if dias is None else dias
    return ahora_ms - dias * 24 * 3600 * 1000


def _descargar_klines(url, symbol, intervalo, dias=None):
    ahora_ms = _ahora_ms()
    start = _inicio_ms(ahora_ms, dias)
    filas = []
    while start < ahora_ms:
        datos = _get(url, {
            "symbol": symbol, "interval": intervalo, "limit": 1000,
            "startTime": start, "endTime": ahora_ms,
        })
        if not datos:
            break
        filas.extend(datos)
        nuevo = datos[-1][0] + 1
        if nuevo <= start:
            break
        start = nuevo
        time.sleep(0.15)

    df = pd.DataFrame(filas, columns=COLUMNAS)
    for c in NUMERICAS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["timestamp"] = df["timestamp"].astype("int64")
    df["close_time"] = df["close_time"].astype("int64")
    df = df.drop(columns="ignore")

    # Descartar la vela sin cerrar
    df = df[df["close_time"] <= ahora_ms]
    return df


def _descargar_funding(symbol):
    ahora_ms = _ahora_ms()
    start = _inicio_ms(ahora_ms)
    filas = []
    while start < ahora_ms:
        datos = _get(FUNDING_URL, {
            "symbol": symbol, "limit": 1000,
            "startTime": start, "endTime": ahora_ms,
        })
        if not datos:
            break
        filas.extend(datos)
        nuevo = datos[-1]["fundingTime"] + 1
        if nuevo <= start:
            break
        start = nuevo
        time.sleep(0.15)

    df = pd.DataFrame(filas)
    df["fundingTime"] = df["fundingTime"].astype("int64")
    df["fundingRate"] = pd.to_numeric(df["fundingRate"], errors="coerce")
    if "markPrice" in df.columns:
        df["markPrice"] = pd.to_numeric(df["markPrice"], errors="coerce")
    return df


def _limpiar(df, col_ts):
    """Devuelve (df sin duplicados y ordenado, duplicados eliminados)."""
    dups = int(df.duplicated(subset=col_ts).sum())
    df = df.drop_duplicates(subset=col_ts).sort_values(col_ts)
    return df.reset_index(drop=True), dups


def _revisar(df, col_ts, paso_ms, tolerancia_ms=0):
    """Cuenta duplicados y huecos (diferencias mayores al paso esperado)."""
    dups = int(df.duplicated(subset=col_ts).sum())
    ts = df[col_ts].drop_duplicates().sort_values()
    diffs = ts.diff().dropna()
    huecos = int((diffs > paso_ms + tolerancia_ms).sum())
    return dups, huecos


def _fecha(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


def _asegurar(ruta, descargar):
    """Devuelve (df, duplicados_descartados_al_descargar)."""
    if os.path.exists(ruta):
        return pd.read_csv(ruta), 0
    df, dups = descargar()
    df.to_csv(ruta, index=False)
    return df, dups


def cargar_velas_cacheadas(symbol, mercado, tf, dias):
    """Velas de un rango corto (p. ej. 1m x 30 días), cacheadas en CSV."""
    os.makedirs(config.CARPETA_DATOS, exist_ok=True)
    url = SPOT_URL if mercado == "spot" else FUT_URL
    ruta = os.path.join(config.CARPETA_DATOS, f"{symbol}_{mercado}_{tf}_{dias}d.csv")
    df, _ = _asegurar(
        ruta,
        lambda: _limpiar(_descargar_klines(url, symbol, tf, dias), "timestamp"),
    )
    return df


def _ms_utc(fecha):
    return int(pd.Timestamp(fecha, tz="UTC").timestamp() * 1000)


def cargar_entrenamiento_spot(tf, symbol=None):
    """Spot desde FECHA_INICIO_DATOS hasta TEST_INICIO (exclusive), cacheado.
    La descarga se corta en TEST_INICIO: el tramo de prueba nunca se baja."""
    symbol = symbol or config.SYMBOL
    os.makedirs(config.CARPETA_DATOS, exist_ok=True)
    ruta = os.path.join(config.CARPETA_DATOS, f"{symbol}_spot_{tf}_train.csv")
    if os.path.exists(ruta):
        return pd.read_csv(ruta)

    fin = _ms_utc(config.TEST_INICIO)
    start = _ms_utc(config.FECHA_INICIO_DATOS)
    filas = []
    while start < fin:
        datos = _get(SPOT_URL, {
            "symbol": symbol, "interval": tf, "limit": 1000,
            "startTime": start, "endTime": fin - 1,
        })
        if not datos:
            break
        filas.extend(datos)
        nuevo = datos[-1][0] + 1
        if nuevo <= start:
            break
        start = nuevo
        time.sleep(0.15)
    df = pd.DataFrame(filas, columns=COLUMNAS).drop(columns="ignore")
    for c in NUMERICAS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["timestamp"] = df["timestamp"].astype("int64")
    df["close_time"] = df["close_time"].astype("int64")
    df = df[df["close_time"] < fin]
    df, _ = _limpiar(df, "timestamp")
    df.to_csv(ruta, index=False)
    return df


def actualizar_cache(symbol="BTCUSDT"):
    os.makedirs(config.CARPETA_DATOS, exist_ok=True)
    resumen = []

    for mercado, url in (("spot", SPOT_URL), ("futuros", FUT_URL)):
        for tf in config.TIMEFRAMES:
            ruta = os.path.join(config.CARPETA_DATOS, f"{symbol}_{mercado}_{tf}.csv")
            df, dups_desc = _asegurar(
                ruta,
                lambda u=url, t=tf: _limpiar(
                    _descargar_klines(u, symbol, t), "timestamp"
                ),
            )
            dups, huecos = _revisar(df, "timestamp", INTERVALO_MS[tf])
            resumen.append((
                os.path.basename(ruta), len(df),
                _fecha(df["timestamp"].iloc[0]), _fecha(df["timestamp"].iloc[-1]),
                huecos, dups + dups_desc,
            ))

    ruta = os.path.join(config.CARPETA_DATOS, f"{symbol}_funding.csv")
    df, dups_desc = _asegurar(
        ruta,
        lambda: _limpiar(_descargar_funding(symbol), "fundingTime"),
    )
    # tolerancia de 1 min: el momento exacto de liquidación varía unos ms
    dups, huecos = _revisar(df, "fundingTime", FUNDING_MS, tolerancia_ms=60_000)
    resumen.append((
        os.path.basename(ruta), len(df),
        _fecha(df["fundingTime"].iloc[0]), _fecha(df["fundingTime"].iloc[-1]),
        huecos, dups + dups_desc,
    ))
    return resumen


def imprimir_tabla(resumen):
    cols = ["archivo", "velas", "inicio (UTC)", "fin (UTC)", "huecos", "duplicados"]
    filas = [[str(x) for x in f] for f in resumen]
    anchos = [max(len(c), *(len(f[i]) for f in filas)) for i, c in enumerate(cols)]
    fmt = " | ".join(f"{{:<{a}}}" for a in anchos)
    print(fmt.format(*cols))
    print("-+-".join("-" * a for a in anchos))
    for f in filas:
        print(fmt.format(*f))


if __name__ == "__main__":
    imprimir_tabla(actualizar_cache(config.SYMBOL))
