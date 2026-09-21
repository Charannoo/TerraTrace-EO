from __future__ import annotations

import base64
import json
import mimetypes
import re
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from PIL import Image

from .catalog import Catalog


MAX_BODY = 28 * 1024 * 1024


class TerraTraceHandler(SimpleHTTPRequestHandler):
    server_version = "TerraTraceEO/0.2"
    catalog: Catalog
    project_root: Path

    def __init__(self, *args: Any, directory: str | None = None, **kwargs: Any):
        super().__init__(*args, directory=directory, **kwargs)

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[TerraTrace] {self.address_string()} - {format % args}")

    def _json(self, payload: Any, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_BODY:
            raise ValueError("invalid request size")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _send_path(self, path: Path) -> None:
        if not path.is_file():
            self.send_error(404)
            return
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._json({"status": "ok", "offline": True, "service": "TerraTrace EO", "version": "0.2.0", **self.catalog.stats()})
            return
        if parsed.path == "/api/search":
            query = parse_qs(parsed.query)
            term = query.get("q", [""])[0][:500]
            sensor = query.get("sensor", [""])[0][:80]
            try:
                max_cloud = min(100.0, max(0.0, float(query.get("max_cloud", [100])[0])))
            except ValueError:
                max_cloud = 100.0
            results = self.catalog.search(term, sensor, max_cloud)
            self._json({"query": term, "results": results, "engine": results[0]["engine"] if results else self.catalog.remoteclip.engine_name})
            return
        if parsed.path == "/api/reviews":
            self._json({"reviews": self.catalog.reviews()})
            return
        match = re.fullmatch(r"/api/cases/([A-Za-z0-9_-]+)/analysis", parsed.path)
        if match:
            try:
                self._json(self.catalog.analyze(match.group(1)))
            except KeyError:
                self._json({"error": "case not found or has no comparison pair"}, 404)
            return
        mask_match = re.fullmatch(r"/api/masks/([A-Za-z0-9_-]+\.png)", parsed.path)
        if mask_match:
            self._send_path(self.catalog.generated_dir / mask_match.group(1))
            return
        if parsed.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = self._body()
            if parsed.path == "/api/review":
                result = self.catalog.add_review(
                    str(payload.get("scene_id", "")), str(payload.get("decision", "")),
                    str(payload.get("note", "")), str(payload.get("analyst", "Analyst K-07")),
                    payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {},
                )
                self._json(result, HTTPStatus.CREATED)
                return
            if parsed.path == "/api/ingest-pair":
                result = self._ingest(payload)
                self._json(result, HTTPStatus.CREATED)
                return
            self._json({"error": "route not found"}, 404)
        except (ValueError, json.JSONDecodeError) as exc:
            self._json({"error": str(exc)}, 400)
        except KeyError as exc:
            self._json({"error": f"not found: {exc.args[0]}"}, 404)
        except Exception as exc:
            self._json({"error": f"request failed: {exc}"}, 500)

    def _decode_image(self, value: str, label: str, stem: str) -> Path:
        if "," in value:
            value = value.split(",", 1)[1]
        raw = base64.b64decode(value, validate=True)
        if len(raw) > 12 * 1024 * 1024:
            raise ValueError(f"{label} image exceeds 12 MB")
        image = Image.open(BytesIO(raw))
        image.verify()
        image = Image.open(BytesIO(raw)).convert("RGB")
        path = self.catalog.upload_dir / f"{stem}-{label}.png"
        image.save(path, optimize=True)
        return path

    def _ingest(self, payload: dict[str, Any]) -> dict[str, Any]:
        before_data = str(payload.pop("before_data", ""))
        after_data = str(payload.pop("after_data", ""))
        if not before_data or not after_data:
            raise ValueError("before_data and after_data are required")
        safe = re.sub(r"[^A-Za-z0-9_-]", "-", str(payload.get("id") or "local-pair"))[:64]
        before_path = self._decode_image(before_data, "before", safe)
        after_path = self._decode_image(after_data, "after", safe)
        scene = self.catalog.ingest_pair(payload, before_path, after_path)
        analysis = self.catalog.analyze(scene["id"])
        return {"scene": scene, "analysis": analysis}


def create_server(project_root: Path, host: str, port: int) -> ThreadingHTTPServer:
    catalog = Catalog(project_root)
    handler = partial(TerraTraceHandler, directory=str(project_root / "dist"))
    handler.catalog = catalog  # type: ignore[attr-defined]
    handler.project_root = project_root  # type: ignore[attr-defined]
    TerraTraceHandler.catalog = catalog
    TerraTraceHandler.project_root = project_root
    return ThreadingHTTPServer((host, port), handler)
