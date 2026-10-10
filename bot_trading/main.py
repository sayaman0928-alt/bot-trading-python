import time

from market_data import obtener_datos_mercado
from indicators import calcular_indicadores
from strategy import evaluar_entrada
from simulator import PaperTrader

from config import (
    SYMBOL,
    INTERVAL,
    CANDLES,
)


def ejecutar_ciclo(trader):

    print()
    print("=" * 60)
    print("🤖 ANALIZANDO MERCADO")
    print("=" * 60)

    # ==========================================================
    # 1. OBTENER DATOS
    # ==========================================================

    df = obtener_datos_mercado(
        symbol=SYMBOL,
        interval=INTERVAL,
        limit=CANDLES
    )

    # ==========================================================
    # 2. ELIMINAR LA VELA EN FORMACIÓN
    # ==========================================================

    # La última vela puede todavía estar formándose.
    # Trabajamos solamente con velas cerradas.

    df = df.iloc[:-1].copy()

    # ==========================================================
    # 3. CALCULAR INDICADORES
    # ==========================================================

    df = calcular_indicadores(df)

    vela = df.iloc[-1]

    precio = vela["close"]

    print(
        f"🪙 {SYMBOL}"
    )

    print(
        f"💰 Precio: ${precio:.2f}"
    )

    print(
        f"📈 EMA20: ${vela['ema_20']:.2f}"
    )

    print(
        f"📊 RSI: {vela['rsi']:.2f}"
    )

    print(
        f"🔥 ATR: ${vela['atr']:.2f}"
    )

    print(
        f"📦 Volumen: {vela['volume']:.2f}"
    )

    print(
        f"📦 Vol. promedio: "
        f"{vela['volume_average']:.2f}"
    )

    # ==========================================================
    # 4. ACTUALIZAR POSICIÓN
    # ==========================================================

    if trader.position_open:

        trader.actualizar(
            high=vela["high"],
            low=vela["low"],
            close=vela["close"],
            atr=vela["atr"]
        )

    # ==========================================================
    # 5. BUSCAR NUEVA ENTRADA
    # ==========================================================

    if not trader.position_open:

        señal = evaluar_entrada(df)

        if señal:

            print()
            print(
                "🚀 SEÑAL DE COMPRA DETECTADA"
            )

            trader.abrir_posicion(
                precio=precio,
                atr=vela["atr"]
            )

        else:

            print()
            print(
                "⏳ No hay señal."
            )

    trader.mostrar_estado()


def main():

    print()
    print("🤖 BOT DE TRADING")
    print("🧪 MODO PAPER TRADING")
    print("💰 DINERO REAL: NO")
    print()

    trader = PaperTrader()

    while True:

        try:

            ejecutar_ciclo(trader)

            print(
                "⏳ Esperando 60 segundos..."
            )

            time.sleep(60)

        except KeyboardInterrupt:

            print()
            print(
                "🛑 Bot detenido por el usuario."
            )

            trader.mostrar_estado()

            break

        except Exception as error:

            print()
            print(
                "⚠️ ERROR:"
            )

            print(error)

            print(
                "🔄 Reintentando en 10 segundos..."
            )

            time.sleep(10)


if __name__ == "__main__":
    main()