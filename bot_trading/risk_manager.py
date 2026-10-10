from config import (
    RISK_PER_TRADE,
    MAX_POSITION_PERCENT,
    ATR_STOP_MULTIPLIER,
    REWARD_RISK_RATIO,
    TRAILING_ATR_MULTIPLIER,
    TRAILING_ACTIVATION_R,
)


def calcular_niveles_entrada(
    precio_entrada,
    atr
):
    """
    Calcula Stop Loss y Take Profit iniciales
    utilizando ATR.
    """

    distancia_stop = (
        atr * ATR_STOP_MULTIPLIER
    )

    stop_loss = (
        precio_entrada
        - distancia_stop
    )

    take_profit = (
        precio_entrada
        + (
            distancia_stop
            * REWARD_RISK_RATIO
        )
    )

    return {
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "distancia_riesgo": distancia_stop,
    }


def calcular_tamano_posicion(
    balance,
    precio_entrada,
    distancia_riesgo
):
    """
    Calcula cuánto BTC comprar basándonos
    en el riesgo máximo permitido.
    """

    if distancia_riesgo <= 0:
        return 0.0

    # Dinero máximo que estamos dispuestos
    # a perder en esta operación.
    riesgo_dinero = (
        balance * RISK_PER_TRADE
    )

    cantidad_por_riesgo = (
        riesgo_dinero
        / distancia_riesgo
    )

    # Límite máximo de capital utilizado.
    capital_maximo = (
        balance
        * MAX_POSITION_PERCENT
    )

    cantidad_maxima = (
        capital_maximo
        / precio_entrada
    )

    cantidad_final = min(
        cantidad_por_riesgo,
        cantidad_maxima
    )

    return max(cantidad_final, 0.0)


def actualizar_trailing_stop(
    precio_actual,
    precio_entrada,
    stop_actual,
    atr
):
    """
    Mueve el stop solamente a favor
    de la posición LONG.
    """

    if atr <= 0:
        return stop_actual

    riesgo_inicial = (
        precio_entrada
        - stop_actual
    )

    if riesgo_inicial <= 0:
        return stop_actual

    beneficio_actual = (
        precio_actual
        - precio_entrada
    )

    r_actual = (
        beneficio_actual
        / riesgo_inicial
    )

    # Todavía no activar trailing.
    if r_actual < TRAILING_ACTIVATION_R:
        return stop_actual

    nuevo_stop = (
        precio_actual
        - (
            atr
            * TRAILING_ATR_MULTIPLIER
        )
    )

    # MUY IMPORTANTE:
    # nunca bajamos el stop.
    return max(
        stop_actual,
        nuevo_stop
    )