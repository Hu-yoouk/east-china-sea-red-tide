"""验证审计能识别统一标签、空间混合标签、重复键和缺失数据。"""

import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "audit_data.py"
SPEC = importlib.util.spec_from_file_location("audit_data", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AuditTests(unittest.TestCase):
    def test_labels_duplicates_missing_and_source_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.db"
            with sqlite3.connect(path) as connection:
                fields = ",".join(f"{name} REAL" for name in MODULE.ENVIRONMENT)
                connection.execute("CREATE TABLE integrated_data "
                                   "(year INTEGER,month INTEGER,longitude REAL,latitude REAL,"
                                   f"red_tide_label INTEGER,{fields})")
                connection.executemany(
                    "INSERT INTO integrated_data (year,month,longitude,latitude,red_tide_label) "
                    "VALUES (?,?,?,?,?)",
                    [(2020, 1, 121.0, 30.0, 0), (2020, 1, 121.25, 30.0, 1),
                     (2020, 2, 121.0, 30.0, 1), (2020, 2, 121.0, 30.0, 1)],
                )
            connection.close()
            original = path.read_bytes()
            result = MODULE.audit(path)
            self.assertEqual(result["mixed_label_months"], 1)
            self.assertEqual(result["uniform_label_months"], 1)
            self.assertEqual(result["duplicate_keys"], 1)
            self.assertEqual(result["missing_environment_values"]["pressure"], 4)
            self.assertEqual(result["test_2020_2023"]["positive"], 3)
            self.assertEqual(path.read_bytes(), original)

    def test_missing_file_is_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "absent.db"
            with self.assertRaises(FileNotFoundError):
                MODULE.audit(path)
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
