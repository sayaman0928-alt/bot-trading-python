# Plan

Parámetros en `config.py` (DIAS_HISTORICO, TIMEFRAMES, CARPETA_DATOS, etc.).
Todo es SOLO BACKTEST / PAPER TRADING. Nada envía órdenes.

## Paso 2: crear `data_cache.py` (HECHO)

- Spot: BTCUSDT de api.binance.com, 2 años, en 15m, 1h y 4h, descargadas directo (NO remuestreadas).
- Futuros: BTCUSDT perpetuo de fapi.binance.com, mismos timeframes, más el historial de funding de /fapi/v1/fundingRate.
- Solo endpoints públicos, sin API key.
- Guardar en CSV dentro de data/. Si el archivo ya existe, no volver a descargar.
- Descartar la vela sin cerrar (close_time > ahora) y usar datetime.now(timezone.utc).
- Revisar huecos y duplicados.

Restricciones (todos los pasos):
- No tocar main.py, strategy.py, backtest.py ni backtest_v7_original.py.
- No correr ningún backtest salvo donde el paso lo pida.
- Salida corta; al terminar cada paso, parar y esperar.

## Paso 3: motor, métricas y tests

### engine.py (motor único, sin look-ahead)
- Señal con el cierre de la vela i, entrada en la apertura de i+1 más slippage.
- SL y TP salen del ATR de la vela i (la de la señal).
- Salidas por vela:
  1. Si abre más allá del stop, sale en la apertura más slippage de stop.
  2. Si toca SL y TP en la misma vela, cuenta como stop.
  3. Si toca solo el SL, sale al precio del stop menos slippage de stop.
  4. Si toca el TP, sale al precio del TP.
- Tamaño = 1% del capital / (distancia al stop + costos por unidad), con tope capital x apalancamiento.
- TP con 1:2 neto (después de costos).
- Filtro: solo entrar si TP bruto >= 3x costos ida y vuelta.
- Funding cada 8h en futuros.
- Capital valuado a mercado; drawdown en % incluyendo la posición abierta.

### metrics.py
- Nº de operaciones, win rate, profit factor, expectancy en $ y en R.
- Sharpe anualizado (retornos diarios, raíz de 365).
- Drawdown máximo %, resultado neto, comisiones.
- Comparación con buy & hold.
- Aviso si hay menos de 100 operaciones.

### estrategias.py (todavía NO)
- A: EMA50/200 + pullback RSI. B: Donchian. C: V7 simplificada. Parámetros en config.py.

### Validación
- Split 70/30 temporal.
- Walk-forward de 180/60 días SOLO dentro del 70%.
- Criterio: PF neto > 1,1 con >= 100 operaciones.
- El 30% de prueba se corre UNA sola vez, al final.

### Orden de pasos
- 3: engine.py + metrics.py + tests (velas sintéticas, anti look-ahead, V7 original en el motor nuevo vs -1,58%).
- 4: estrategias en spot, solo con entrenamiento.
- 5: walk-forward.
- 6: futuros con funding.
- 7: prueba final (30%) y tabla en resultados/.
- 8: conclusión honesta.

### Paso 3: HECHO (15 tests OK; V7 en motor nuevo comparada con -1,58%)

### Paso 4: HECHO
- `estrategias.py` (A, B, C; solo LONG, parámetros "default" de config.py), `correr_entrenamiento.py`, `test_estrategias.py` (anti look-ahead).
- Corridas A/B/C en 15m, 1h, 4h SOLO sobre el primer 70% (hasta 2026-02-26). Tabla en `resultados/paso4_entrenamiento.csv`.
- Win% y PF son ambos netos (la fila "win 12,5% / PF 0,00" del paso 3 era 1 ganadora de +$0,05 contra pérdidas de ~$3: PF 0,002 redondeado; no era bug).
- Definiciones: A = RSI cruza hacia arriba el umbral con EMA50>EMA200 y cierre>EMA200; B = cierre sobre máximo previo de 20 velas + EMA200, salida bajo mínimo previo de 10; C = V7 sin rechazo/volumen/cuerpo/vela excesiva. Todas con SL por ATR y TP 1:2 neto (B también con salida por canal).

### Decisiones de implementación (paso 3)
- TP y SL del TP neto: TP_dist = RR_neto x (SL_dist + costos_stop) + costos_tp, con costos por unidad.
- Opción `rr_bruto` en el motor solo para reproducir las condiciones de la V7 original.
- Salida por señal opcional (para Donchian): sale en la apertura de i+1 con slippage.
- Funding: se cobra si la posición estaba abierta en el instante del funding (vela de salida incluida).

## Paso 5: decisiones (anotadas ANTES de correr nada)

1. Se descartan 15m y 1h (PF 0,50-0,72 con más de 100 operaciones y comisiones enormes). Quedan 4h y 1d.
2. Spot BTCUSDT 4h y 1d desde 2020-01-01, con caché (`data/BTCUSDT_spot_{tf}_train.csv`). `TEST_INICIO = 2026-02-26 00:00 UTC` en config.py:
   entrenamiento = todo lo anterior, prueba = desde esa fecha. La descarga se corta en TEST_INICIO: el tramo de prueba no se baja, no se carga y no se usa.
3. Dos variantes sin TP fijo, definidas en config.py y que no se cambian después:
   - A_sinTP: entrada de A, salida cuando cierre < EMA50, stop 2 ATR.
   - B_sinTP: entrada de B, solo salida por canal de 10, stop 2 ATR.
   Estrategias: A, B, C, A_sinTP, B_sinTP x {4h, 1d} = 10 combinaciones.
   (Sin TP en el motor = rr_neto enorme: el TP nunca se toca; el filtro de costos pasa.)
4. Walk-forward SOLO en entrenamiento, grillas chicas de config.py (A_sinTP y B_sinTP: stop fijo en 2 ATR, solo varía el parámetro de entrada).
   Ventanas 180/60 días en 4h y 365/120 en 1d (ventana de entrenamiento móvil, paso = ventana de prueba, solo ventanas de prueba completas).
   Elección en cada ventana: mayor expectancy R en la ventana de entrenamiento (si nada opera, parámetros default). Capital encadenado entre ventanas.
5. Métricas por combinación: operaciones, PF neto, expectancy R, retorno %, DD %, Sharpe, % de ventanas de prueba positivas (sin operaciones = no positiva),
   buy & hold del mismo tramo con su DD y Sharpe. Menos de 100 operaciones = "no concluyente".

### Paso 5: HECHO
- `paso5_walkforward.py` -> `resultados/paso5_walkforward.csv`. 10 combinaciones, solo entrenamiento (datos < 2026-02-26; el tramo de prueba no se descargó).
- 4h: 34 ventanas (180/60). 1d: 15 ventanas (365/120). Capital encadenado, por lo que PF (en $) y retorno pueden diferir en signo cuando el tamaño crece con el capital (A_sinTP 4h).
- Tramo de prueba intacto; se corre una sola vez en el paso 7.

## Paso 7: decisiones (anotadas ANTES de correr la prueba)
- Candidatas: B_donchian y B_sinTP en 4h spot (solo LONG).
- Parámetros congelados, elegidos con el entrenamiento completo (< 2026-02-26) por mayor expectancy R (mismo criterio del paso 5), sin walk-forward adicional:
  - B_donchian: canal_entrada 55, atr_stop 2.5 (canal_salida 10, EMA200, TP 1:2 neto).
  - B_sinTP: canal_entrada 20, atr_stop 2.0 (canal_salida 10, EMA200, sin TP).
- Criterio de aprobación: PF neto > 1,1 Y drawdown menor que el de buy & hold en el tramo de prueba.
- Prueba (desde 2026-02-26 00:00 UTC) se corre UNA sola vez; 500 velas de entrenamiento previas solo calientan indicadores (señales anuladas antes de la prueba). No se repite ni se cambia nada tras verla. Sin futuros.

### Paso 7: HECHO
- `paso7_prueba.py` -> `resultados/paso7_prueba.csv`. Prueba 2026-02-26 -> 2026-10-03 (1318 velas 4h), corrida una sola vez (el script se niega a repetirla).
- B_donchian: 17 ops, PF 0,47, ret -5,48% -> NO aprobada. B_sinTP: 18 ops, PF 1,74, ret +7,70%, DD 6,24% (B&H 29,25%) -> aprobada por criterio, pero con < 100 ops: NO concluyente.

## Paso 8: conclusión honesta (solo documentación; no se corrió nada nuevo)

### Resultados
Spot BTCUSDT, solo LONG, con costos del motor (comisión 0,1% por lado, slippage). Fuentes: `resultados/paso4_entrenamiento.csv`, `paso5_walkforward.csv`, `paso7_prueba.csv`.

**Entrenamiento (paso 4, 4h, primer 70%, parámetros default)**

| Estrategia | Ops | PF neto | Exp R | Ret % | DD % |
|---|---|---|---|---|---|
| A | 33 | 0,86 | -0,09 | -3,2 | 8,2 |
| B_donchian | 46 | 1,25 | +0,15 | +6,5 | 8,4 |
| C | 40 | 1,06 | +0,05 | +1,6 | 7,4 |

15m y 1h quedaron descartadas (PF 0,50-0,72, comisiones enormes).

**Walk-forward (paso 5, solo entrenamiento)**

| Estrategia | TF | Ops | PF neto | Exp R | Ret % | DD % | Sharpe | Vent.+ % | Concluyente |
|---|---|---|---|---|---|---|---|---|---|
| A | 4h | 101 | 0,91 | -0,05 | -1,0 | 15,7 | 0,00 | 35 | sí |
| B_donchian | 4h | 154 | 1,44 | +0,23 | +42,7 | 8,2 | 0,95 | 68 | sí |
| C | 4h | 92 | 1,25 | +0,17 | +23,1 | 13,8 | 0,62 | 41 | no |
| A_sinTP | 4h | 188 | 0,83 | -0,04 | +15,8 | 16,4 | 0,36 | 29 | sí |
| B_sinTP | 4h | 112 | 1,88 | +0,64 | +128,9 | 11,6 | 1,30 | 56 | sí |
| A / B_donchian / C / A_sinTP / B_sinTP | 1d | 16-30 | 0,80-1,27 | | | | | | no (todas < 100 ops) |

Buy & hold del mismo tramo 4h: +879%, DD 77%, Sharpe 0,99. Con el criterio PF > 1,1 y >= 100 ops pasaron B_donchian 4h y B_sinTP 4h; C 4h tuvo PF > 1,1 pero con 92 ops. A y A_sinTP no pasaron. Ninguna de 1d es concluyente.

**Prueba final (paso 7, 2026-02-26 -> 2026-10-03, corrida una sola vez)**

| Estrategia | Ops | PF neto | Exp R | Ret % | DD % | Sharpe | Aprobada |
|---|---|---|---|---|---|---|---|
| B_donchian (55 / 2,5 ATR) | 17 | 0,47 | -0,33 | -5,5 | 7,5 | -1,66 | NO |
| B_sinTP (20 / 2,0 ATR) | 18 | 1,74 | +0,48 | +7,7 | 6,2 | 0,92 | SÍ (no concluyente) |
| Buy & hold | | | | +24,6 | 29,3 | 1,13 | |

### Lectura
- B_donchian falló la prueba: lo que se veía bien en entrenamiento no se sostuvo.
- B_sinTP pasó el criterio formal (PF 1,74 > 1,1 y DD 6,2% < 29,3%), pero con **solo 18 operaciones**: no es concluyente. Con tan pocas operaciones, un par de trades cambia el PF por completo.
- **No supera a buy & hold en retorno (+7,7% vs +24,6%) ni en Sharpe (0,92 vs 1,13).** Solo gana en drawdown (6,2% vs 29,3%), lo cual es esperable en una estrategia que pasa buena parte del tiempo fuera del mercado.
- No hay evidencia de ventaja estadística demostrada. Lo único que se puede afirmar es "no se descartó".
- El tramo de prueba queda **CONSUMIDO**: no se vuelve a usar para elegir ni ajustar nada (parámetros, estrategias, filtros). Cualquier cambio futuro necesita datos nuevos (paper trading).

### Limitaciones
1. **10 combinaciones probadas** (5 estrategias x 2 timeframes), más la selección de candidatas: con tantas pruebas, que alguna salga bien por azar es esperable. No se corrigió por comparaciones múltiples.
2. **Capital encadenado** entre ventanas del walk-forward: el tamaño crece con el capital, lo que infla el retorno compuesto y puede hacer que PF (en $) y retorno difieran (ej. A_sinTP 4h: PF 0,83 con ret +15,8%). Mejor mirar PF y expectancy R que el retorno.
3. **Parámetros elegidos por expectancy R**: criterio sensible a pocas operaciones grandes, y favorece sobreajuste en la ventana de entrenamiento.
4. **Un solo activo (BTC)**: sin evidencia en otros activos.
5. **Un solo régimen de mercado**: BTC en fuerte tendencia alcista en el entrenamiento (B&H +879%) y alcista moderado en la prueba; no se probó en mercado bajista ni lateral prolongado.
6. Adicionales: prueba de 18 operaciones; solo spot LONG (futuros no evaluados en la prueba); slippage y comisiones son supuestos del modelo, no ejecuciones reales.

### Propuesta: paper trading de B_sinTP en 4h spot (NO implementado)
**Parámetros congelados** (los del paso 7): canal_entrada 20, canal_salida 10, EMA200, stop 2,0 ATR, sin TP, solo LONG, BTCUSDT 4h spot. Nada se cambia durante el paper trading.

**Diseño**
- Solo datos públicos de Binance (klines), **sin API keys y sin enviar órdenes reales**.
- Un script que corre al cierre de cada vela 4h (cron / tarea programada), descarta la vela sin cerrar y usa el mismo `engine.py` y `estrategias.py` (misma lógica de señal, entrada en la apertura de i+1 con slippage, stop por ATR de la vela de señal, salida por canal de 10, mismos costos y slippage de stop).
- Registro en CSV (`paper/paper_trades.csv`), append-only, con: id, timestamp de señal, precio de señal, ATR, timestamp y precio de entrada simulada, stop, timestamp y precio de salida simulada, motivo de salida (stop / canal), tamaño, comisión de entrada y salida, slippage, PnL neto $, R, capital resultante. Un segundo CSV de señales (`paper_senales.csv`) con cada evaluación de vela (señal sí/no, por qué).
- Capital inicial virtual fijo (1000 USD) y riesgo 1% por operación, igual que el motor.
- Control: al final comparar las operaciones del paper trading con un re-run del motor sobre las mismas velas; deben coincidir (verifica que no haya look-ahead ni divergencias).

**Criterio de éxito (definido de antemano)**
- Mínimo **30 operaciones cerradas** (a ~1 operación/2 semanas puede tardar más de 1 año; se acepta, no se acorta el criterio).
- **PF neto > 1,1** y **expectancy R > 0** sobre esas operaciones.
- Drawdown máximo < 15% sobre el capital simulado.
- Resultados no dependientes de 1-2 operaciones: PF > 1 al excluir la mejor operación.
- Si tras 30 operaciones PF neto <= 1,1 (o con criterio de aborto: DD > 20%), se declara fallida y se descarta; no se reajustan parámetros para "rescatarla".

**Antes de usar dinero real** haría falta, como mínimo:
1. Paper trading exitoso según el criterio anterior, sin cambios de parámetros.
2. Coincidencia verificada entre paper trading y motor (sin divergencias de lógica).
3. Medir slippage y comisiones reales con operaciones de tamaño mínimo (cuenta con tope pequeño), no solo supuestos.
4. Capital que se pueda perder por completo, tamaño pequeño y límite de pérdida diaria/total con corte automático.
5. API keys con permisos solo de trading (sin retiro), código de ejecución separado y probado, manejo de errores/desconexiones y alertas.
6. Idealmente, evidencia adicional en otro régimen de mercado (o al menos conciencia explícita de que no la hay) y, si es posible, en otro activo.
