from __future__ import annotations
import unittest
from pathlib import Path
SQL = Path(__file__).resolve().parents[1] / "sql" / "artifacts.sql"
class T(unittest.TestCase):
    def test_states(self):
        t = SQL.read_text()
        self.assertIn("PROVISIONAL", t)
        self.assertIn("PROMOTED", t)
if __name__ == "__main__":
    unittest.main()
