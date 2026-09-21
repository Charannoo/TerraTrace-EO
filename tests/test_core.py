from __future__ import annotations

import json
import unittest
import urllib.request
import threading
from pathlib import Path

from backend.api import create_server
from backend.catalog import Catalog


SOURCE_ROOT = Path(__file__).resolve().parents[1]


class TerraTraceCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = SOURCE_ROOT
        self.catalog = Catalog(SOURCE_ROOT)

    def test_seed_and_semantic_search(self) -> None:
        self.assertEqual(self.catalog.stats()["scenes"], 5)
        results = self.catalog.search("industrial construction near a river", "Sentinel-2 L2A", 15)
        self.assertGreaterEqual(len(results), 3)
        self.assertIn(results[0]["id"], {"TTE-2026-017", "TTE-2026-042"})
        self.assertTrue(all(result["cloud"] <= 15 for result in results))

    def test_measured_change_analysis(self) -> None:
        result = self.catalog.analyze("TTE-2026-017")
        self.assertEqual(result["decision"], "CHANGE")
        self.assertGreater(result["changed_fraction"], 0.02)
        self.assertTrue(result["quality_gates"]["registration"])
        self.assertEqual(len(result["asset_hashes"]["after_sha256"]), 64)
        self.assertTrue((self.root / "data" / "generated" / "TTE-2026-017-mask.png").exists())

    def test_review_is_persisted(self) -> None:
        review = self.catalog.add_review("TTE-2026-017", "confirmed", "verified", "Test analyst", {"score": 0.9})
        self.assertEqual(review["decision"], "confirmed")
        self.assertEqual(self.catalog.reviews()[0]["note"], "verified")
        with self.catalog.connection() as connection:
            connection.execute("DELETE FROM reviews WHERE id = ?", (review["id"],))

    def test_http_health_endpoint(self) -> None:
        server = create_server(self.root, "127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=5) as response:
                payload = json.loads(response.read())
            self.assertEqual(payload["status"], "ok")
            self.assertTrue(payload["offline"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
