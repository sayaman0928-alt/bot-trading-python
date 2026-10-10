import requests
import pandas as pd


BINANCE_API_URL = "https://api.binance.com/api/v3/klines"


def obtener_datos_mercado(
    symbol="BTCUSDT",
    interval="1m",
    limit=100
):
    """
    Obtiene velas de mercado desde la API pública de Binance.
    No requiere API Key.
    """

    parametros = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }

    respuesta = requests.get(
        BINANCE_API_URL,
        params=parametros,
        timeout=10
    )

    respuesta.raise_for_status()

    datos = respuesta.json()

    columnas = [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "quote_asset_volume",
        "number_of_trades",
        "taker_buy_base_asset_volume",
        "taker_buy_quote_asset_volume",
        "ignore"
    ]

    df = pd.DataFrame(datos, columns=columnas)

    columnas_numericas = [
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]

    for columna in columnas_numericas:
        df[columna] = pd.to_numeric(
            df[columna],
            errors="coerce"
        )

    return df


def obtener_historico(
    symbol="BTCUSDT",
    interval="1m",
    dias=30
):
    """
    Descarga velas históricas cerradas desde Binance.

    La descarga se hace por bloques para respetar
    los límites de la API.
    """

    import time
    from datetime import datetime, timedelta

    ahora = datetime.utcnow()

    inicio = ahora - timedelta(days=dias)

    start_time = int(
        inicio.timestamp() * 1000
    )

    end_time = int(
        ahora.timestamp() * 1000
    )

    todos_los_datos = []

    while start_time < end_time:

        parametros = {
            "symbol": symbol,
            "interval": interval,
            "limit": 1000,
            "startTime": start_time,
            "endTime": end_time
        }

        respuesta = requests.get(
            BINANCE_API_URL,
            params=parametros,
            timeout=10
        )

        respuesta.raise_for_status()

        datos = respuesta.json()

        if not datos:
            break

        todos_los_datos.extend(datos)

        ultimo_timestamp = datos[-1][0]

        nuevo_start_time = (
            ultimo_timestamp + 1
        )

        if nuevo_start_time <= start_time:
            break

        start_time = nuevo_start_time

        print(
            f"📥 Velas descargadas: "
            f"{len(todos_los_datos)}"
        )

        time.sleep(0.15)

    columnas = [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "quote_asset_volume",
        "number_of_trades",
        "taker_buy_base_asset_volume",
        "taker_buy_quote_asset_volume",
        "ignore"
    ]

    df = pd.DataFrame(
        todos_los_datos,
        columns=columnas
    )

    columnas_numericas = [
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]

    for columna in columnas_numericas:

        df[columna] = pd.to_numeric(
            df[columna],
            errors="coerce"
        )

    df = df.drop_duplicates(
        subset="timestamp"
    )

    df = df.sort_values(
        "timestamp"
    )

    df = df.reset_index(
        drop=True
    )

    return df