import pandas as pd

from market_data import obtener_historico
from indicators import calcular_indicadores
from strategy import evaluar_condiciones


# ============================================================
# CONFIGURACIÓN DEL BACKTEST V7
# ============================================================

SIMBOLO = "BTCUSDT"
INTERVALO = "1m"
DIAS = 30

CAPITAL_INICIAL = 1000.0

RIESGO_POR_OPERACION = 0.005
APALANCAMIENTO_MAXIMO = 1.0

ATR_STOP_MULTIPLICADOR = 1.5
RATIO_RIESGO_BENEFICIO = 2.0

COMISION = 0.001

ACTIVAR_TRAILING = False
TRAILING_ATR_MULTIPLICADOR = 1.0

COOLDOWN_VELAS = 15

CAPITAL_MINIMO_PORCENTAJE = 0.10


# ============================================================
# INICIO
# ============================================================

print()
print("=" * 70)
print("                 BACKTEST V7")
print("=" * 70)
print()

print(f"Símbolo: {SIMBOLO}")
print(f"Intervalo: {INTERVALO}")
print(f"Días: {DIAS}")
print(f"Capital inicial: ${CAPITAL_INICIAL:.2f}")
print(f"Riesgo por operación: {RIESGO_POR_OPERACION * 100:.2f}%")
print(f"Comisión por lado: {COMISION * 100:.3f}%")
print(f"Ratio Riesgo/Beneficio: 1:{RATIO_RIESGO_BENEFICIO:.1f}")
print()

print("📥 Descargando datos históricos...")
print()


# ============================================================
# DESCARGAR HISTÓRICO
# ============================================================

df = obtener_historico(
    symbol=SIMBOLO,
    interval=INTERVALO,
    dias=DIAS
)

if df.empty:
    print("❌ No se pudieron obtener datos históricos.")
    raise SystemExit


print()
print(f"✅ Velas descargadas: {len(df)}")
print()


# ============================================================
# LIMPIEZA
# ============================================================

df = df.copy()

df = df.sort_values("timestamp")

df = df.drop_duplicates(
    subset="timestamp"
)

df = df.reset_index(drop=True)


# ============================================================
# CALCULAR INDICADORES
# ============================================================

print("📊 Calculando indicadores...")

df = calcular_indicadores(df)

print("✅ Indicadores calculados.")
print()


# ============================================================
# VARIABLES DEL BACKTEST
# ============================================================

capital = CAPITAL_INICIAL

posicion = None

senal_pendiente = None

cooldown = 0

operaciones = []

max_capital = CAPITAL_INICIAL
max_drawdown = 0.0


# ============================================================
# DIAGNÓSTICO
# ============================================================

diagnostico = {
    "velas": 0,

    "long_tendencia": 0,
    "long_precio": 0,
    "long_rsi": 0,
    "long_vela": 0,
    "long_rechazo": 0,
    "long_volumen": 0,
    "long_vela_no_excesiva": 0,
    "long_completa": 0,

    "short_tendencia": 0,
    "short_precio": 0,
    "short_rsi": 0,
    "short_vela": 0,
    "short_rechazo": 0,
    "short_volumen": 0,
    "short_vela_no_excesiva": 0,
    "short_completa": 0,

    "entradas_rechazadas_comision": 0
}


# ============================================================
# ESTADÍSTICAS V7
# ============================================================

tp_alcanzados = 0
tp_netos_positivos = 0
tp_netos_negativos = 0

total_comisiones = 0.0

resultado_bruto_total = 0.0
resultado_neto_total = 0.0


# ============================================================
# RECORRER VELAS
# ============================================================

for i in range(1, len(df)):

    diagnostico["velas"] += 1

    vela = df.iloc[i]

    # --------------------------------------------------------
    # CAPITAL MÍNIMO
    # --------------------------------------------------------

    if capital <= CAPITAL_INICIAL * CAPITAL_MINIMO_PORCENTAJE:

        print()
        print("🛑 BACKTEST DETENIDO")
        print("El capital cayó por debajo del límite mínimo.")
        print()

        break


    # --------------------------------------------------------
    # ACTUALIZAR DRAWDOWN
    # --------------------------------------------------------

    if capital > max_capital:
        max_capital = capital

    drawdown = max_capital - capital

    if drawdown > max_drawdown:
        max_drawdown = drawdown


    # --------------------------------------------------------
    # COOLDOWN
    # --------------------------------------------------------

    if cooldown > 0:
        cooldown -= 1


    # ========================================================
    # ENTRADA PENDIENTE
    # ========================================================

    if (
        posicion is None
        and senal_pendiente is not None
    ):

        tipo = senal_pendiente["tipo"]

        precio_entrada = vela["open"]

        atr = vela["atr"]

        if pd.isna(atr) or atr <= 0:

            senal_pendiente = None

        else:

            # ------------------------------------------------
            # STOP
            # ------------------------------------------------

            distancia_stop = (
                atr * ATR_STOP_MULTIPLICADOR
            )

            if tipo == "LONG":

                stop_loss = (
                    precio_entrada
                    - distancia_stop
                )

                take_profit = (
                    precio_entrada
                    + distancia_stop
                    * RATIO_RIESGO_BENEFICIO
                )

            else:

                stop_loss = (
                    precio_entrada
                    + distancia_stop
                )

                take_profit = (
                    precio_entrada
                    - distancia_stop
                    * RATIO_RIESGO_BENEFICIO
                )


            # ------------------------------------------------
            # TAMAÑO DE POSICIÓN
            # ------------------------------------------------

            riesgo_dinero = (
                capital
                * RIESGO_POR_OPERACION
            )

            distancia_precio = abs(
                precio_entrada - stop_loss
            )

            if distancia_precio <= 0:

                senal_pendiente = None

            else:

                # Aproximación conservadora:
                # riesgo del stop + dos comisiones.

                riesgo_por_unidad = (
                    distancia_precio
                    + precio_entrada * COMISION * 2
                )

                cantidad = (
                    riesgo_dinero
                    / riesgo_por_unidad
                )

                # ------------------------------------------------
                # LIMITAR POR APALANCAMIENTO
                # ------------------------------------------------

                cantidad_maxima = (
                    capital
                    * APALANCAMIENTO_MAXIMO
                    / precio_entrada
                )

                cantidad = min(
                    cantidad,
                    cantidad_maxima
                )


                # ------------------------------------------------
                # V7 - COMPROBAR VIABILIDAD DEL TAKE PROFIT
                # ------------------------------------------------

                valor_entrada_estimado = (
                    precio_entrada * cantidad
                )

                valor_tp_estimado = (
                    take_profit * cantidad
                )

                if tipo == "LONG":

                    beneficio_bruto_tp = (
                        take_profit
                        - precio_entrada
                    ) * cantidad

                else:

                    beneficio_bruto_tp = (
                        precio_entrada
                        - take_profit
                    ) * cantidad


                comision_entrada_estimada = (
                    valor_entrada_estimado
                    * COMISION
                )

                comision_salida_estimada = (
                    valor_tp_estimado
                    * COMISION
                )

                comision_tp_estimada = (
                    comision_entrada_estimada
                    + comision_salida_estimada
                )

                beneficio_neto_tp_estimado = (
                    beneficio_bruto_tp
                    - comision_tp_estimada
                )


                # ------------------------------------------------
                # SI EL TP NI SIQUIERA CUBRE LAS COMISIONES,
                # NO ABRIMOS LA OPERACIÓN.
                # ------------------------------------------------

                if beneficio_neto_tp_estimado <= 0:

                    diagnostico[
                        "entradas_rechazadas_comision"
                    ] += 1

                    senal_pendiente = None

                    continue


                # ------------------------------------------------
                # CREAR POSICIÓN
                # ------------------------------------------------

                if cantidad > 0:

                    posicion = {
                        "tipo": tipo,
                        "entrada": precio_entrada,
                        "cantidad": cantidad,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "atr": atr
                    }

                    print(
                        f"🟢 ENTRADA {tipo} | "
                        f"Precio: {precio_entrada:.2f} | "
                        f"SL: {stop_loss:.2f} | "
                        f"TP: {take_profit:.2f} | "
                        f"TP neto estimado: "
                        f"${beneficio_neto_tp_estimado:.2f}"
                    )

                senal_pendiente = None


    # ========================================================
    # GESTIONAR POSICIÓN
    # ========================================================

    if posicion is not None:

        tipo = posicion["tipo"]

        entrada = posicion["entrada"]

        cantidad = posicion["cantidad"]

        stop_loss = posicion["stop_loss"]

        take_profit = posicion["take_profit"]

        atr_actual = vela["atr"]

        high = vela["high"]

        low = vela["low"]

        precio_salida = None

        motivo_salida = None


        # ----------------------------------------------------
        # LONG
        # ----------------------------------------------------

        if tipo == "LONG":

            toco_stop = low <= stop_loss

            toco_tp = high >= take_profit

            # Si toca ambos en la misma vela,
            # asumimos STOP por seguridad.

            if toco_stop and toco_tp:

                precio_salida = stop_loss

                motivo_salida = "STOP_Y_TP_MISMA_VELA"

            elif toco_stop:

                precio_salida = stop_loss

                motivo_salida = "STOP"

            elif toco_tp:

                precio_salida = take_profit

                motivo_salida = "TAKE_PROFIT"


        # ----------------------------------------------------
        # SHORT
        # ----------------------------------------------------

        else:

            toco_stop = high >= stop_loss

            toco_tp = low <= take_profit

            if toco_stop and toco_tp:

                precio_salida = stop_loss

                motivo_salida = "STOP_Y_TP_MISMA_VELA"

            elif toco_stop:

                precio_salida = stop_loss

                motivo_salida = "STOP"

            elif toco_tp:

                precio_salida = take_profit

                motivo_salida = "TAKE_PROFIT"


        # ----------------------------------------------------
        # TRAILING STOP
        # ----------------------------------------------------

        if (
            ACTIVAR_TRAILING
            and precio_salida is None
            and not pd.isna(atr_actual)
            and atr_actual > 0
        ):

            if tipo == "LONG":

                nuevo_stop = (
                    vela["close"]
                    - atr_actual
                    * TRAILING_ATR_MULTIPLICADOR
                )

                if nuevo_stop > stop_loss:

                    posicion["stop_loss"] = nuevo_stop


            else:

                nuevo_stop = (
                    vela["close"]
                    + atr_actual
                    * TRAILING_ATR_MULTIPLICADOR
                )

                if nuevo_stop < stop_loss:

                    posicion["stop_loss"] = nuevo_stop


        # ----------------------------------------------------
        # CERRAR OPERACIÓN
        # ----------------------------------------------------

        if precio_salida is not None:

            valor_entrada = (
                entrada * cantidad
            )

            valor_salida = (
                precio_salida * cantidad
            )


            # ------------------------------------------------
            # RESULTADO BRUTO
            # ------------------------------------------------

            if tipo == "LONG":

                resultado_bruto = (
                    precio_salida
                    - entrada
                ) * cantidad

            else:

                resultado_bruto = (
                    entrada
                    - precio_salida
                ) * cantidad


            # ------------------------------------------------
            # COMISIONES
            # ------------------------------------------------

            comision_entrada = (
                valor_entrada
                * COMISION
            )

            comision_salida = (
                valor_salida
                * COMISION
            )

            comisiones = (
                comision_entrada
                + comision_salida
            )


            # ------------------------------------------------
            # RESULTADO NETO
            # ------------------------------------------------

            resultado_neto = (
                resultado_bruto
                - comisiones
            )


            # ------------------------------------------------
            # ACTUALIZAR ESTADÍSTICAS
            # ------------------------------------------------

            total_comisiones += comisiones

            resultado_bruto_total += resultado_bruto

            resultado_neto_total += resultado_neto


            if motivo_salida == "TAKE_PROFIT":

                tp_alcanzados += 1

                if resultado_neto > 0:

                    tp_netos_positivos += 1

                else:

                    tp_netos_negativos += 1


            # ------------------------------------------------
            # ACTUALIZAR CAPITAL
            # ------------------------------------------------

            capital_anterior = capital

            capital += resultado_neto


            # ------------------------------------------------
            # GUARDAR OPERACIÓN
            # ------------------------------------------------

            operaciones.append({

                "tipo": tipo,

                "entrada": entrada,

                "salida": precio_salida,

                "cantidad": cantidad,

                "stop_loss": stop_loss,

                "take_profit": take_profit,

                "resultado_bruto": resultado_bruto,

                "comisiones": comisiones,

                "resultado_neto": resultado_neto,

                "capital": capital,

                "motivo": motivo_salida
            })


            print(
                f"🔴 SALIDA {tipo} | "
                f"{motivo_salida} | "
                f"Bruto: ${resultado_bruto:.2f} | "
                f"Comisión: ${comisiones:.2f} | "
                f"Neto: ${resultado_neto:.2f} | "
                f"Capital: ${capital:.2f}"
            )


            posicion = None

            cooldown = COOLDOWN_VELAS

            continue


    # ========================================================
    # BUSCAR NUEVA SEÑAL
    # ========================================================

    if (
        posicion is None
        and senal_pendiente is None
        and cooldown == 0
    ):

        resultado = evaluar_condiciones(vela)


        # ----------------------------------------------------
        # DIAGNÓSTICO LONG
        # ----------------------------------------------------

        long_condiciones = resultado.get(
            "long_conditions",
            {}
        )

        if long_condiciones:

            if long_condiciones.get("tendencia", False):
                diagnostico["long_tendencia"] += 1

            if long_condiciones.get("precio", False):
                diagnostico["long_precio"] += 1

            if long_condiciones.get("rsi", False):
                diagnostico["long_rsi"] += 1

            if long_condiciones.get("vela", False):
                diagnostico["long_vela"] += 1

            if long_condiciones.get("rechazo", False):
                diagnostico["long_rechazo"] += 1

            if long_condiciones.get("volumen", False):
                diagnostico["long_volumen"] += 1

            if long_condiciones.get(
                "vela_no_excesiva",
                False
            ):
                diagnostico[
                    "long_vela_no_excesiva"
                ] += 1


        # ----------------------------------------------------
        # DIAGNÓSTICO SHORT
        # ----------------------------------------------------

        short_condiciones = resultado.get(
            "short_conditions",
            {}
        )

        if short_condiciones:

            if short_condiciones.get("tendencia", False):
                diagnostico["short_tendencia"] += 1

            if short_condiciones.get("precio", False):
                diagnostico["short_precio"] += 1

            if short_condiciones.get("rsi", False):
                diagnostico["short_rsi"] += 1

            if short_condiciones.get("vela", False):
                diagnostico["short_vela"] += 1

            if short_condiciones.get("rechazo", False):
                diagnostico["short_rechazo"] += 1

            if short_condiciones.get("volumen", False):
                diagnostico["short_volumen"] += 1

            if short_condiciones.get(
                "vela_no_excesiva",
                False
            ):
                diagnostico[
                    "short_vela_no_excesiva"
                ] += 1


        # ----------------------------------------------------
        # CREAR SEÑAL PENDIENTE
        # ----------------------------------------------------

        if resultado.get("long", False):

            diagnostico["long_completa"] += 1

            senal_pendiente = {
                "tipo": "LONG"
            }


        elif resultado.get("short", False):

            diagnostico["short_completa"] += 1

            senal_pendiente = {
                "tipo": "SHORT"
            }


# ============================================================
# RESULTADOS
# ============================================================

print()
print("=" * 70)
print("                    RESULTADOS V7")
print("=" * 70)
print()


capital_final = capital

resultado_total = (
    capital_final
    - CAPITAL_INICIAL
)

rentabilidad = (
    resultado_total
    / CAPITAL_INICIAL
) * 100


# ============================================================
# RESULTADOS NETOS
# ============================================================

ganancias_netas = [
    op["resultado_neto"]
    for op in operaciones
    if op["resultado_neto"] > 0
]

perdidas_netas = [
    op["resultado_neto"]
    for op in operaciones
    if op["resultado_neto"] < 0
]


cantidad_operaciones = len(operaciones)

ganadoras = len(ganancias_netas)

perdedoras = len(perdidas_netas)


if cantidad_operaciones > 0:

    porcentaje_aciertos = (
        ganadoras
        / cantidad_operaciones
    ) * 100

else:

    porcentaje_aciertos = 0


# ============================================================
# RESULTADOS BRUTOS
# ============================================================

ganancias_brutas = [
    op["resultado_bruto"]
    for op in operaciones
    if op["resultado_bruto"] > 0
]

perdidas_brutas = [
    op["resultado_bruto"]
    for op in operaciones
    if op["resultado_bruto"] < 0
]


ganancia_bruta = sum(
    ganancias_brutas
)

perdida_bruta = abs(
    sum(perdidas_brutas)
)


# ============================================================
# RESULTADOS NETOS
# ============================================================

ganancia_neta = sum(
    ganancias_netas
)

perdida_neta = abs(
    sum(perdidas_netas)
)


# ============================================================
# PROFIT FACTOR BRUTO
# ============================================================

if perdida_bruta > 0:

    profit_factor_bruto = (
        ganancia_bruta
        / perdida_bruta
    )

else:

    profit_factor_bruto = float("inf")


# ============================================================
# PROFIT FACTOR NETO
# ============================================================

if perdida_neta > 0:

    profit_factor_neto = (
        ganancia_neta
        / perdida_neta
    )

else:

    profit_factor_neto = float("inf")


# ============================================================
# PROMEDIOS
# ============================================================

if ganadoras > 0:

    promedio_ganadora = (
        ganancia_neta
        / ganadoras
    )

else:

    promedio_ganadora = 0


if perdedoras > 0:

    promedio_perdedora = (
        perdida_neta
        / perdedoras
    )

else:

    promedio_perdedora = 0


# ============================================================
# EXPECTANCY
# ============================================================

if cantidad_operaciones > 0:

    expectancy = (
        resultado_total
        / cantidad_operaciones
    )

else:

    expectancy = 0


# ============================================================
# MOSTRAR RESULTADOS
# ============================================================

print(
    f"Capital inicial:        "
    f"${CAPITAL_INICIAL:.2f}"
)

print(
    f"Capital final:          "
    f"${capital_final:.2f}"
)

print(
    f"Resultado neto:         "
    f"${resultado_total:.2f}"
)

print(
    f"Rentabilidad:           "
    f"{rentabilidad:.2f}%"
)

print()

print(
    f"Operaciones:            "
    f"{cantidad_operaciones}"
)

print(
    f"Ganadoras netas:        "
    f"{ganadoras}"
)

print(
    f"Perdedoras netas:       "
    f"{perdedoras}"
)

print(
    f"Aciertos netos:         "
    f"{porcentaje_aciertos:.2f}%"
)

print()

print(
    f"Ganancia BRUTA:         "
    f"${ganancia_bruta:.2f}"
)

print(
    f"Pérdida BRUTA:          "
    f"${perdida_bruta:.2f}"
)

print(
    f"Ganancia NETA:          "
    f"${ganancia_neta:.2f}"
)

print(
    f"Pérdida NETA:           "
    f"${perdida_neta:.2f}"
)

print()

print(
    f"Profit Factor BRUTO:    "
    f"{profit_factor_bruto:.2f}"
)

print(
    f"Profit Factor NETO:     "
    f"{profit_factor_neto:.2f}"
)

print()

print(
    f"Promedio ganadora:      "
    f"${promedio_ganadora:.2f}"
)

print(
    f"Promedio perdedora:     "
    f"${promedio_perdedora:.2f}"
)

print(
    f"Expectancy:             "
    f"${expectancy:.4f}"
)

print()

print(
    f"Máximo drawdown:        "
    f"${max_drawdown:.2f}"
)

print()

# ============================================================
# ESTADÍSTICAS DE COMISIONES
# ============================================================

print("=" * 70)
print("                COMISIONES Y TP")
print("=" * 70)
print()

print(
    f"Comisiones totales:     "
    f"${total_comisiones:.2f}"
)

print(
    f"TP alcanzados:          "
    f"{tp_alcanzados}"
)

print(
    f"TP netos positivos:     "
    f"{tp_netos_positivos}"
)

print(
    f"TP netos negativos:     "
    f"{tp_netos_negativos}"
)

print(
    f"Entradas rechazadas por "
    f"comisión:              "
    f"{diagnostico['entradas_rechazadas_comision']}"
)

print()

print(
    f"Resultado bruto total:  "
    f"${resultado_bruto_total:.2f}"
)

print(
    f"Comisiones:             "
    f"-${total_comisiones:.2f}"
)

print(
    f"Resultado neto total:   "
    f"${resultado_neto_total:.2f}"
)


# ============================================================
# DIAGNÓSTICO
# ============================================================

print()
print("=" * 70)
print("                    DIAGNÓSTICO")
print("=" * 70)
print()

print(
    f"Velas analizadas:       "
    f"{diagnostico['velas']}"
)

print()

print("LONG")
print("-" * 40)

print(
    f"Tendencia:              "
    f"{diagnostico['long_tendencia']}"
)

print(
    f"Precio:                 "
    f"{diagnostico['long_precio']}"
)

print(
    f"RSI:                    "
    f"{diagnostico['long_rsi']}"
)

print(
    f"Vela:                   "
    f"{diagnostico['long_vela']}"
)

print(
    f"Rechazo:                "
    f"{diagnostico['long_rechazo']}"
)

print(
    f"Volumen:                "
    f"{diagnostico['long_volumen']}"
)

print(
    f"Vela no excesiva:       "
    f"{diagnostico['long_vela_no_excesiva']}"
)

print(
    f"TODO JUNTO:             "
    f"{diagnostico['long_completa']}"
)

print()

print("SHORT")
print("-" * 40)

print(
    f"Tendencia:              "
    f"{diagnostico['short_tendencia']}"
)

print(
    f"Precio:                 "
    f"{diagnostico['short_precio']}"
)

print(
    f"RSI:                    "
    f"{diagnostico['short_rsi']}"
)

print(
    f"Vela:                   "
    f"{diagnostico['short_vela']}"
)

print(
    f"Rechazo:                "
    f"{diagnostico['short_rechazo']}"
)

print(
    f"Volumen:                "
    f"{diagnostico['short_volumen']}"
)

print(
    f"Vela no excesiva:       "
    f"{diagnostico['short_vela_no_excesiva']}"
)

print(
    f"TODO JUNTO:             "
    f"{diagnostico['short_completa']}"
)


# ============================================================
# GUARDAR OPERACIONES
# ============================================================

if operaciones:

    df_operaciones = pd.DataFrame(
        operaciones
    )

    df_operaciones.to_csv(
        "backtest_trades.csv",
        index=False
    )

    print()
    print("📁 Operaciones guardadas en:")
    print("backtest_trades.csv")

else:

    print()
    print("⚠️ No hubo operaciones.")


print()
print("=" * 70)
print("                 BACKTEST V7 TERMINADO")
print("=" * 70)
print()