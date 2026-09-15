"""检验时间边界、单位校验及真实推理与独立测试的一致性。"""

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from red_tide.core import predict, read_monthly, supervised

ROOT = Path(__file__).resolve().parents[1]


class ForecastTests(unittest.TestCase):
    def test_next_month_target_never_enters_features(self):
        frame = read_monthly(ROOT / "data" / "monthly.csv", labelled=True)
        features, labels, targets = supervised(frame)
        self.assertEqual(str(targets[0]), "2005-01")
        self.assertEqual(labels[0], frame.iloc[12].red_tide_label)
        changed = frame.copy()
        changed.loc[12, "sst"] = 9999
        changed.loc[12, "red_tide_label"] = 1 - labels[0]
        changed_features, changed_labels, _ = supervised(changed)
        np.testing.assert_equal(features.iloc[0].values, changed_features.iloc[0].values)
        self.assertNotEqual(labels[0], changed_labels[0])

    def test_reject_missing_field_gap_duplicate_wrong_units(self):
        sample = read_monthly(ROOT / "examples" / "observations_2019.csv").drop(columns="period")
        cases = [sample.drop(columns="pressure"), sample.drop(index=5),
                 sample.assign(pressure=1013), sample.assign(month=1)]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csv"
            for frame in cases:
                frame.to_csv(path, index=False)
                with self.assertRaises(ValueError):
                    read_monthly(path)

    def test_heldout_prediction_matches_actual_saved_model(self):
        import pandas as pd
        result = predict(ROOT / "examples" / "observations_2019.csv", ROOT / "models" / "regional_v1")
        self.assertEqual(result["target_month"], "2020-01")
        expected = pd.read_csv(ROOT / "models" / "regional_v1" / "test_predictions.csv").iloc[0]
        self.assertAlmostEqual(result["probability"], expected.probability, places=10)

    def test_prediction_does_not_use_supplied_label(self):
        frame = read_monthly(ROOT / "examples" / "observations_2019.csv").drop(columns="period")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "labelled.csv"
            frame["red_tide_label"] = 0
            frame.to_csv(path, index=False)
            first = predict(path, ROOT / "models" / "regional_v1")["probability"]
            frame["red_tide_label"] = 1
            frame.to_csv(path, index=False)
            second = predict(path, ROOT / "models" / "regional_v1")["probability"]
            self.assertEqual(first, second)

    def test_training_counts_are_months_not_repeated_grids(self):
        meta = json.loads((ROOT / "models" / "regional_v1" / "metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["evaluation"]["train"]["model"]["n"], 156)
        self.assertEqual(meta["evaluation"]["validation"]["model"]["n"], 24)
        self.assertEqual(meta["evaluation"]["test"]["model"]["n"], 48)


if __name__ == "__main__":
    unittest.main()
