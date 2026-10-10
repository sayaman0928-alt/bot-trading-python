SYMBOL = "BTCUSDT"

INTERVAL = "1m"

CANDLES = 200

# Capital virtual inicial
INITIAL_BALANCE = 1000.0

# Riesgo máximo por operación
RISK_PER_TRADE = 0.01

# No permitir utilizar más de este porcentaje
# del balance en una sola posición.
# (Lo usa simulator.py / main.py, no el motor nuevo.)
MAX_POSITION_PERCENT = 0.25

# ATR
ATR_PERIOD = 14
ATR_STOP_MULTIPLIER = 1.5

# Relación riesgo/beneficio
REWARD_RISK_RATIO = 2.0

# Trailing stop
TRAILING_ACTIVATION_R = 1.0
TRAILING_ATR_MULTIPLIER = 1.2

# Costos simulados
FEE_RATE = 0.001

# Slippage simulado (entradas y take profit)
SLIPPAGE_RATE = 0.0002


# ==============================================================
# MOTOR DE BACKTEST UNIFICADO (engine.py)
# ==============================================================
# Todo lo que sigue lo lee el motor nuevo.
# SOLO BACKTEST / PAPER TRADING. Nada de esto envía órdenes.

# Mercado por defecto: "spot" (solo LONG) o "futuros" (LONG y SHORT)
MERCADO = "spot"

# Comisiones por lado, según el tipo de orden
FEES = {
    "spot": {"taker": 0.001, "maker": 0.001},
    "futuros": {"taker": 0.0005, "maker": 0.0002},
}

# Tipo de orden para cada evento
TIPO_ORDEN_ENTRADA = "taker"   # entrada a mercado
TIPO_ORDEN_TP = "taker"        # conservador ("maker" como opción)
TIPO_ORDEN_STOP = "taker"      # un stop siempre se ejecuta a mercado
TIPO_ORDEN_SALIDA_SENAL = "taker"

# Slippage en stops (se ejecutan en el peor momento)
SLIPPAGE_STOP_RATE = 0.0005

# Tope de nocional = capital x apalancamiento
APALANCAMIENTO_MAX = {
    "spot": 1.0,
    "futuros": 1.0,
}

# Ratio mínimo beneficio/riesgo DESPUÉS de costos.
# El TP se coloca para que (TP - costos) / (SL + costos) = MIN_RR_NETO
MIN_RR_NETO = 2.0

# Solo entrar si el TP bruto es al menos N veces
# los costos de ida y vuelta (comisiones + slippage)
MIN_TP_VS_COSTOS = 3.0

# Si el capital cae por debajo de este % del inicial, se detiene
CAPITAL_MINIMO_PORCENTAJE = 0.10


# ==============================================================
# DATOS
# ==============================================================

CARPETA_DATOS = "data"
CARPETA_RESULTADOS = "resultados"

DIAS_HISTORICO = 730          # 2 años
TIMEFRAMES = ["4h", "1d"]   # 15m y 1h descartados en el paso 4

# Paso 5: datos desde esta fecha; la prueba empieza en TEST_INICIO
FECHA_INICIO_DATOS = "2020-01-01"
TEST_INICIO = "2026-02-26"   # 00:00 UTC. Entrenamiento = antes; prueba = desde acá


# ==============================================================
# VALIDACIÓN
# ==============================================================

# Primer 70% = entrenamiento, último 30% = prueba (se corre UNA vez)
TRAIN_FRACCION = 0.70

# Walk-forward DENTRO del 70% de entrenamiento
WF_VENTANA_ENTRENAMIENTO_DIAS = 180   # ~6 meses
WF_VENTANA_PRUEBA_DIAS = 60           # ~2 meses

# Paso 5: ventanas (entrenamiento, prueba) en días, por timeframe
WF_VENTANAS = {"4h": (180, 60), "1d": (365, 120)}

# Mínimo de operaciones para considerar un resultado concluyente
MIN_OPERACIONES_CONCLUYENTE = 100

# Criterio de selección (definido ANTES de ver resultados)
CRITERIO_PF_MINIMO = 1.10


# ==============================================================
# PARÁMETROS DE ESTRATEGIA (fijados ANTES de ver datos)
# ==============================================================
# "default" = valor estándar de la literatura.
# "grilla"  = valores que el walk-forward puede elegir,
#             usando SOLO datos de entrenamiento.

ESTRATEGIAS = {

    # A. Tendencia EMA 50/200 + pullback con RSI
    "A_tendencia_pullback": {
        "default": {
            "ema_rapida": 50,
            "ema_lenta": 200,
            "rsi_umbral": 40,
            "atr_stop": 2.0,
        },
        "grilla": {
            "rsi_umbral": [35, 40, 45],
            "atr_stop": [1.5, 2.0, 2.5],
        },
    },

    # B. Breakout de Donchian
    "B_donchian": {
        "default": {
            "canal_entrada": 20,
            "canal_salida": 10,
            "ema_filtro": 200,
            "atr_stop": 2.0,
        },
        "grilla": {
            "canal_entrada": [20, 55],
            "atr_stop": [1.5, 2.0, 2.5],
        },
    },

    # C. V7 simplificada (sin rechazo, volumen, cuerpo ni vela excesiva)
    "C_v7_simplificada": {
        "default": {
            "distancia_ema20_atr": 0.75,
            "rsi_min": 45,
            "rsi_max": 58,
            "atr_stop": 1.5,
        },
        "grilla": {
            "atr_stop": [1.5, 2.0, 2.5],
        },
    },

    # A sin TP: entrada de A, sale cuando el cierre < EMA rápida (EMA50)
    "A_sinTP": {
        "default": {
            "ema_rapida": 50,
            "ema_lenta": 200,
            "rsi_umbral": 40,
            "atr_stop": 2.0,
        },
        "grilla": {
            "rsi_umbral": [35, 40, 45],
        },
    },

    # B sin TP: entrada de B, solo salida por canal de 10
    "B_sinTP": {
        "default": {
            "canal_entrada": 20,
            "canal_salida": 10,
            "ema_filtro": 200,
            "atr_stop": 2.0,
        },
        "grilla": {
            "canal_entrada": [20, 55],
        },
    },
}

# Estrategias sin TP fijo (el motor usa un TP inalcanzable)
SIN_TP = ["A_sinTP", "B_sinTP"]
RR_SIN_TP = 1_000_000


# ==============================================================
# COMPARACIÓN CON EL BACKTEST V7 ORIGINAL
# ==============================================================
# Mismas condiciones que backtest_v7_original.py, corridas
# en el motor nuevo para comparar con el -1,58%.

V7_ORIGINAL = {
    "intervalo": "1m",
    "dias": 30,
    "riesgo": 0.005,
    "atr_stop": 1.5,
    "rr_bruto": 2.0,
    "cooldown_velas": 15,
}
