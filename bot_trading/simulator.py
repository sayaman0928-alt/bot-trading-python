from config import (
    INITIAL_BALANCE,
    FEE_RATE,
    SLIPPAGE_RATE,
)

from risk_manager import (
    calcular_niveles_entrada,
    calcular_tamano_posicion,
    actualizar_trailing_stop,
)


class PaperTrader:

    def __init__(self):
        self.balance = INITIAL_BALANCE

        self.position_open = False

        self.entry_price = 0.0
        self.quantity = 0.0

        self.stop_loss = 0.0
        self.take_profit = 0.0

        self.highest_price = 0.0

        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0

        self.total_profit = 0.0

    def abrir_posicion(
        self,
        precio,
        atr
    ):

        if self.position_open:
            return False

        # Slippage de entrada.
        precio_real = (
            precio
            * (1 + SLIPPAGE_RATE)
        )

        niveles = calcular_niveles_entrada(
            precio_real,
            atr
        )

        cantidad = calcular_tamano_posicion(
            self.balance,
            precio_real,
            niveles["distancia_riesgo"]
        )

        if cantidad <= 0:
            return False

        capital_utilizado = (
            cantidad
            * precio_real
        )

        comision = (
            capital_utilizado
            * FEE_RATE
        )

        if (
            capital_utilizado
            + comision
            > self.balance
        ):
            return False

        self.balance -= (
            capital_utilizado
            + comision
        )

        self.position_open = True

        self.entry_price = precio_real
        self.quantity = cantidad

        self.stop_loss = niveles["stop_loss"]
        self.take_profit = niveles["take_profit"]

        self.highest_price = precio_real

        self.total_trades += 1

        print()
        print("🟢 ===== ENTRADA =====")
        print(f"Precio: ${self.entry_price:.2f}")
        print(f"Cantidad BTC: {self.quantity:.6f}")
        print(f"Stop Loss: ${self.stop_loss:.2f}")
        print(f"Take Profit: ${self.take_profit:.2f}")
        print()

        return True

    def actualizar(
        self,
        high,
        low,
        close,
        atr
    ):

        if not self.position_open:
            return

        # Actualizamos máximo alcanzado.
        self.highest_price = max(
            self.highest_price,
            high
        )

        # Actualizamos trailing stop.
        nuevo_stop = actualizar_trailing_stop(
            self.highest_price,
            self.entry_price,
            self.stop_loss,
            atr
        )

        if nuevo_stop > self.stop_loss:

            self.stop_loss = nuevo_stop

            print(
                f"🔒 Trailing Stop → "
                f"${self.stop_loss:.2f}"
            )

        # ======================================================
        # SALIDAS
        # ======================================================

        # En caso de que una misma vela toque
        # stop y TP, usamos el stop primero.
        # Esto es conservador.
        if low <= self.stop_loss:

            self.cerrar_posicion(
                self.stop_loss,
                "STOP LOSS"
            )

        elif high >= self.take_profit:

            self.cerrar_posicion(
                self.take_profit,
                "TAKE PROFIT"
            )

    def cerrar_posicion(
        self,
        precio,
        motivo
    ):

        if not self.position_open:
            return

        precio_real = (
            precio
            * (1 - SLIPPAGE_RATE)
        )

        valor_venta = (
            self.quantity
            * precio_real
        )

        comision = (
            valor_venta
            * FEE_RATE
        )

        resultado = (
            valor_venta
            - comision
            - (
                self.quantity
                * self.entry_price
            )
        )

        self.balance += (
            valor_venta
            - comision
        )

        self.total_profit += resultado

        if resultado >= 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1

        print()
        print("🔴 ===== SALIDA =====")
        print(f"Motivo: {motivo}")
        print(f"Precio: ${precio_real:.2f}")
        print(f"Resultado: ${resultado:.2f}")
        print(f"Balance: ${self.balance:.2f}")
        print()

        self.position_open = False

        self.entry_price = 0.0
        self.quantity = 0.0

        self.stop_loss = 0.0
        self.take_profit = 0.0

        self.highest_price = 0.0

    def mostrar_estado(self):

        print()
        print("📊 ===== ESTADO =====")
        print(f"Balance: ${self.balance:.2f}")
        print(f"Operaciones: {self.total_trades}")
        print(f"Ganadoras: {self.winning_trades}")
        print(f"Perdedoras: {self.losing_trades}")
        print(f"Resultado: ${self.total_profit:.2f}")

        if self.total_trades > 0:

            win_rate = (
                self.winning_trades
                / self.total_trades
                * 100
            )

            print(
                f"Win Rate: {win_rate:.2f}%"
            )

        print()