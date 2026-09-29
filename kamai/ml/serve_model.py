"""Dependency-light HTTP service for Kamai model inference."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from src.predictor import KamaiPredictor


ROOT = Path(__file__).resolve().parent


class PredictionHandler(BaseHTTPRequestHandler):
    predictor: KamaiPredictor

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send(204, {})

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send(200, {"status": "ok", "service": "kamai-ml", "model": self.predictor.metadata["selected_model"]})
        elif self.path == "/model-info":
            self._send(200, self.predictor.metadata)
        else:
            self._send(404, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > 100_000:
                raise ValueError("Request body must contain JSON and be smaller than 100 KB")
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("JSON body must be an object")
            if self.path == "/predict":
                self._send(200, self.predictor.predict(payload))
            elif self.path == "/recommend":
                self._send(200, self.predictor.recommend(payload))
            elif self.path == "/rank":
                self._send(200, self.predictor.rank(payload))
            else:
                self._send(404, {"error": "Not found"})
        except (ValueError, json.JSONDecodeError) as exc:
            self._send(400, {"error": str(exc)})
        except Exception as exc:  # pragma: no cover - defensive service boundary
            self._send(500, {"error": "Prediction failed", "detail": str(exc)})

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[kamai-ml] {self.address_string()} - {format % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    PredictionHandler.predictor = KamaiPredictor(ROOT / "artifacts")
    server = ThreadingHTTPServer((args.host, args.port), PredictionHandler)
    print(f"Kamai ML service listening on http://{args.host}:{args.port}")
    print("Endpoints: GET /health, GET /model-info, POST /predict, POST /recommend, POST /rank")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping Kamai ML service")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
