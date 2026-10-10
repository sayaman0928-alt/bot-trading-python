import unittest

import numpy as np
import pandas as pd

from engine import correr_backtest
from estrategias import FUNCIONES, generar
from test_engine import BASE, serie_sintetica


class TestAntiLookAheadEstrategias(unittest.TestCase):

    def test_cambiar_el_futuro_no_cambia_senales_ni_operaciones(self):
        n, k = 8000, 5000
        base = serie_sintetica(n, 7)

        alt = base.copy()
        otro = serie_sintetica(n - k - 1, 123)
        for col in ("open", "high", "low", "close", "volume"):
            alt.loc[k + 1:, col] = otro[col].to_numpy() * (
                base[col].iloc[k] / otro[col].iloc[0]
            )
        self.assertFalse(base.loc[k + 1:, "close"].equals(alt.loc[k + 1:, "close"]))

        for nombre in FUNCIONES:
            with self.subTest(estrategia=nombre):
                sb, sa = generar(nombre, base), generar(nombre, alt)

                np.testing.assert_array_equal(sb["senal"][:k + 1], sa["senal"][:k + 1])
                self.assertGreater(sb["senal"][:k + 1].sum(), 10, "el test sería vacuo")
                if sb["salida"] is not None:
                    np.testing.assert_array_equal(sb["salida"][:k + 1], sa["salida"][:k + 1])
                np.testing.assert_allclose(
                    sb["atr"].to_numpy()[:k + 1], sa["atr"].to_numpy()[:k + 1],
                    equal_nan=True,
                )

                res = []
                for d, s in ((base, sb), (alt, sa)):
                    res.append(correr_backtest(
                        d.assign(atr=s["atr"]), s["senal"], salida_senal=s["salida"],
                        **{**BASE, "atr_stop": s["atr_stop"], "min_tp_vs_costos": 0.0},
                    ))
                tb, ta = (r["trades"] for r in res)
                tb = tb[tb["idx_salida"] <= k].reset_index(drop=True)
                ta = ta[ta["idx_salida"] <= k].reset_index(drop=True)
                self.assertGreater(len(tb), 5, "el test sería vacuo")
                pd.testing.assert_frame_equal(tb, ta)

    def test_solo_long(self):
        df = serie_sintetica(3000, 3)
        for nombre in FUNCIONES:
            s = generar(nombre, df)["senal"]
            self.assertTrue(set(np.unique(s)) <= {0.0, 1.0})


if __name__ == "__main__":
    unittest.main(verbosity=1)
