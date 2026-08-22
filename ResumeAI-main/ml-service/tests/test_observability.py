from __future__ import annotations

import unittest

import app as flask_app


class ObservabilityAPITests(unittest.TestCase):
    def setUp(self):
        flask_app.app.config.update(TESTING=True)
        self.client = flask_app.app.test_client()

    def test_health_reports_safe_rag_readiness(self):
        response = self.client.get("/health")
        body = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["service"], "resume-analysis")
        self.assertIn(body["status"], {"healthy", "degraded"})
        self.assertEqual(
            set(body["rag"]),
            {"enabled", "ready", "knowledgeBaseVersion"},
        )
        self.assertNotIn("path", response.get_data(as_text=True).lower())
        self.assertNotIn("key", response.get_data(as_text=True).lower())

    def test_valid_request_id_is_echoed(self):
        response = self.client.post(
            "/analyze", headers={"X-Request-ID": "req-test-123"}
        )
        self.assertEqual(response.headers["X-Request-ID"], "req-test-123")

    def test_invalid_request_id_is_replaced(self):
        response = self.client.post(
            "/analyze", headers={"X-Request-ID": "invalid id with spaces"}
        )
        self.assertNotEqual(
            response.headers["X-Request-ID"], "invalid id with spaces"
        )
        self.assertRegex(response.headers["X-Request-ID"], r"^[a-f0-9]{32}$")


if __name__ == "__main__":
    unittest.main()
