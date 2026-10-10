import unittest

import numpy as np
import pandas as pd

import config
from engine import correr_backtest
from indicators import calcular_indicadores

T0 = 1_700_000_000_000
PASO = 900_000  # 15m

# Parámetros explícitos: los tests no dependen de config.py
FEE = {"taker": 0.001, "maker": 0.001}
BASE = dict(
    mercado="spot", fees=FEE, slippage=0.0, slippage_stop=0.001,
    atr_stop=2.0, rr_neto=2.0, min_tp_vs_costos=0.0, riesgo=0.01,
    capital_inicial=1000.0, apalancamiento=1.0,
)


def velas(filas, atr=10.0):
    """filas: (open, high, low, close). La vela 0 es la de la señal."""
    df = pd.DataFrame(filas, columns=["open", "high", "low", "close"])
    df["timestamp"] = T0 + np.arange(len(df)) * PASO
    df["volume"] = 1.0
    df["atr"] = atr
    return df


def senal_en_0(n):
    s = np.zeros(n)
    s[0] = 1
    return s


class TestSalidas(unittest.TestCase):

    # Entrada en la apertura de la vela 1 = 100, ATR 10 x 2 -> stop a 80.
    def correr(self, extra, **kw):
        filas = [(100, 100, 100, 100), (100, 101, 99, 100)] + extra
        df = velas(filas)
        res = correr_backtest(df, senal_en_0(len(df)), **{**BASE, **kw})
        self.assertEqual(len(res["trades"]), 1)
        return res["trades"].iloc[0]

    def test_entrada_en_apertura_siguiente_con_slippage(self):
        t = self.correr([(100, 101, 99, 100), (100, 101, 70, 70)], slippage=0.0002)
        self.assertAlmostEqual(t["entrada"], 100 * 1.0002)
        self.assertEqual(t["idx_entrada"], 1)
        self.assertEqual(t["idx_senal"], 0)

    def test_salto_del_stop(self):
        t = self.correr([(70, 75, 65, 72)])
        self.assertEqual(t["motivo"], "GAP_STOP")
        self.assertAlmostEqual(t["salida"], 70 * (1 - 0.001))

    def test_sl_y_tp_en_la_misma_vela_cuenta_como_stop(self):
        t = self.correr([(100, 500, 70, 100)])
        self.assertEqual(t["motivo"], "STOP_Y_TP")
        self.assertAlmostEqual(t["salida"], 80 * (1 - 0.001))

    def test_solo_sl(self):
        t = self.correr([(100, 105, 79, 85)])
        self.assertEqual(t["motivo"], "STOP")
        self.assertAlmostEqual(t["salida"], 80 * (1 - 0.001))

    def test_solo_tp_sale_al_precio_del_tp(self):
        t = self.correr([(100, 500, 95, 400)])
        self.assertEqual(t["motivo"], "TP")
        self.assertAlmostEqual(t["salida"], t["tp"])

    def test_short_salto_del_stop_y_tp(self):
        df = velas([(100, 100, 100, 100), (100, 101, 99, 100), (130, 135, 128, 130)])
        s = -senal_en_0(len(df))
        res = correr_backtest(df, s, **{**BASE, "mercado": "futuros"})
        t = res["trades"].iloc[0]
        self.assertEqual(t["lado"], "SHORT")
        self.assertEqual(t["motivo"], "GAP_STOP")
        self.assertAlmostEqual(t["salida"], 130 * (1 + 0.001))

    def test_short_no_entra_en_spot(self):
        df = velas([(100, 100, 100, 100), (100, 101, 99, 100), (100, 101, 99, 100)])
        res = correr_backtest(df, -senal_en_0(len(df)), **BASE)
        self.assertEqual(len(res["trades"]), 0)
        self.assertEqual(res["rechazadas"]["short_en_spot"], 1)


class TestComisiones(unittest.TestCase):

    def test_comisiones_tamano_y_tp_neto(self):
        # slippage_stop = 0 para cuentas limpias
        p = {**BASE, "slippage_stop": 0.0}
        df = velas([(100, 100, 100, 100), (100, 101, 99, 100), (100, 200, 99, 190)])
        res = correr_backtest(df, senal_en_0(len(df)), **p)
        t = res["trades"].iloc[0]

        d = 20.0
        c_sl = 100 * 0.002           # entrada + stop
        c_tp = 100 * 0.002           # entrada + tp
        qty = 1000 * 0.01 / (d + c_sl)
        tp = 100 + 2 * (d + c_sl) + c_tp

        self.assertAlmostEqual(t["qty"], qty)
        self.assertAlmostEqual(t["tp"], tp)
        self.assertEqual(t["motivo"], "TP")
        self.assertAlmostEqual(t["comisiones"], (100 + tp) * qty * 0.001)
        self.assertAlmostEqual(t["bruto"], (tp - 100) * qty)
        self.assertAlmostEqual(t["neto"], t["bruto"] - t["comisiones"])
        self.assertAlmostEqual(res["equity"]["equity"].iloc[-1], 1000 + t["neto"])
        # 1:2 neto: ganancia neta ~ 2R (el costo de salida se estimó con la entrada)
        self.assertAlmostEqual(t["r"], 2.0, delta=0.05)

    def test_perdida_en_stop_incluye_costos(self):
        p = {**BASE, "slippage_stop": 0.0005}
        df = velas([(100, 100, 100, 100), (100, 101, 99, 100), (100, 100, 70, 75)])
        t = correr_backtest(df, senal_en_0(len(df)), **p)["trades"].iloc[0]
        salida = 80 * (1 - 0.0005)
        self.assertAlmostEqual(t["salida"], salida)
        self.assertAlmostEqual(t["comisiones"], (100 + salida) * t["qty"] * 0.001)
        self.assertAlmostEqual(t["neto"], (salida - 100) * t["qty"] - t["comisiones"])
        # la pérdida real ronda 1R (el slippage de salida ya está en el tamaño)
        self.assertAlmostEqual(t["r"], -1.0, delta=0.01)

    def test_tope_de_apalancamiento(self):
        df = velas([(100, 100, 100, 100), (100, 101, 99, 100), (100, 100, 70, 75)], atr=0.1)
        t = correr_backtest(df, senal_en_0(len(df)), **BASE)["trades"].iloc[0]
        self.assertAlmostEqual(t["qty"] * t["entrada"], 1000.0)  # 1x capital

    def test_filtro_tp_vs_costos(self):
        # ATR minúsculo y RR 1: el TP no llega a 3x los costos
        df = velas([(100, 100, 100, 100), (100, 101, 99, 100), (100, 101, 99, 100)], atr=0.001)
        res = correr_backtest(
            df, senal_en_0(len(df)), **{**BASE, "rr_neto": 1.0, "min_tp_vs_costos": 3.0}
        )
        self.assertEqual(len(res["trades"]), 0)
        self.assertEqual(res["rechazadas"]["tp_vs_costos"], 1)


class TestFunding(unittest.TestCase):

    def test_funding_long_paga_tasa_positiva(self):
        # Posición abierta durante el instante del funding (vela 2)
        df = velas([
            (100, 100, 100, 100), (100, 101, 99, 100),
            (100, 101, 99, 100), (100, 500, 99, 400),
        ])
        fund = pd.DataFrame({
            "fundingTime": [T0 + 2 * PASO + 1000],
            "fundingRate": [0.0001],
            "markPrice": [100.0],
        })
        res = correr_backtest(
            df, senal_en_0(len(df)), funding=fund, **{**BASE, "mercado": "futuros"}
        )
        t = res["trades"].iloc[0]
        self.assertAlmostEqual(t["funding"], -t["qty"] * 100.0 * 0.0001)
        self.assertAlmostEqual(
            t["neto"], t["bruto"] - t["comisiones"] + t["funding"]
        )

    def test_sin_funding_en_spot(self):
        df = velas([
            (100, 100, 100, 100), (100, 101, 99, 100),
            (100, 101, 99, 100), (100, 500, 99, 400),
        ])
        fund = pd.DataFrame({"fundingTime": [T0 + 2 * PASO], "fundingRate": [0.01]})
        t = correr_backtest(df, senal_en_0(len(df)), funding=fund, **BASE)["trades"].iloc[0]
        self.assertEqual(t["funding"], 0.0)


class TestSalidaPorSenal(unittest.TestCase):

    def test_sale_en_apertura_siguiente(self):
        df = velas([
            (100, 100, 100, 100), (100, 101, 99, 100),
            (100, 102, 98, 101), (103, 104, 102, 103),
        ])
        sal = np.zeros(len(df))
        sal[2] = 1  # cierre de la vela 2 -> sale en la apertura de la 3
        res = correr_backtest(df, senal_en_0(len(df)), salida_senal=sal, **BASE)
        t = res["trades"].iloc[0]
        self.assertEqual(t["motivo"], "SALIDA_SENAL")
        self.assertEqual(t["idx_salida"], 3)
        self.assertAlmostEqual(t["salida"], 103.0)


def serie_sintetica(n, semilla):
    rng = np.random.default_rng(semilla)
    ret = rng.normal(0, 0.002, n)
    cierre = 100 * np.exp(np.cumsum(ret))
    apertura = np.concatenate([[100], cierre[:-1]])
    alto = np.maximum(apertura, cierre) * (1 + np.abs(rng.normal(0, 0.001, n)))
    bajo = np.minimum(apertura, cierre) * (1 - np.abs(rng.normal(0, 0.001, n)))
    df = pd.DataFrame({
        "timestamp": T0 + np.arange(n) * PASO,
        "open": apertura, "high": alto, "low": bajo, "close": cierre,
        "volume": rng.uniform(50, 150, n),
    })
    return df


def regla_simple(df):
    """Estrategia trivial: sigue el color de la vela (genera muchas operaciones)."""
    s = np.sign((df["close"] - df["open"]).to_numpy())
    return s


class TestAntiLookAhead(unittest.TestCase):

    def test_cambiar_el_futuro_no_cambia_el_pasado(self):
        from comparar_v7 import senales_v7_original

        n, k = 6000, 3500
        base = serie_sintetica(n, 1)

        # Futuro alterado al azar: velas posteriores a k
        alt = base.copy()
        otro = serie_sintetica(n - k - 1, 99)
        for col in ("open", "high", "low", "close", "volume"):
            alt.loc[k + 1:, col] = otro[col].to_numpy() * (
                base[col].iloc[k] / otro[col].iloc[0]
            )
        self.assertFalse(base.loc[k + 1:, "close"].equals(alt.loc[k + 1:, "close"]))

        res = {}
        sen_v7 = {}
        for nombre, d in (("base", base), ("alt", alt)):
            d = calcular_indicadores(d)
            sen_v7[nombre] = senales_v7_original(d)
            res[nombre] = correr_backtest(
                d, regla_simple(d), **{**BASE, "mercado": "futuros", "min_tp_vs_costos": 0.0}
            )

        # Señales V7 hasta k idénticas
        np.testing.assert_array_equal(sen_v7["base"][:k + 1], sen_v7["alt"][:k + 1])

        # Operaciones cerradas hasta k idénticas, y capital a mercado idéntico
        tb = res["base"]["trades"]
        ta = res["alt"]["trades"]
        tb = tb[tb["idx_salida"] <= k].reset_index(drop=True)
        ta = ta[ta["idx_salida"] <= k].reset_index(drop=True)
        self.assertGreater(len(tb), 50, "el test sería vacuo")
        pd.testing.assert_frame_equal(tb, ta)
        np.testing.assert_array_equal(
            res["base"]["equity"]["equity"].to_numpy()[:k + 1],
            res["alt"]["equity"]["equity"].to_numpy()[:k + 1],
        )


if __name__ == "__main__":
    unittest.main(verbosity=1)
