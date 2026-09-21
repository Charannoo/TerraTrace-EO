from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from .analysis import analyze_pair, sha256_file
from .remoteclip import RemoteClipIndex


TERM_GROUPS = {
    "industrial": ["industry", "industrial", "factory", "warehouse", "logistics", "depot", "construction", "built"],
    "river": ["river", "water", "channel", "stream", "reservoir", "lake", "riparian"],
    "road": ["road", "highway", "corridor", "transport", "linear", "access"],
    "agriculture": ["agriculture", "agricultural", "field", "farm", "crop", "seasonal"],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        try:
            return bool(super().__exit__(exc_type, exc, traceback))
        finally:
            self.close()


def _tokens(text: str) -> list[str]:
    raw = re.findall(r"[a-z0-9]+", text.lower())
    expanded: list[str] = []
    for token in raw:
        expanded.append(token)
        for canonical, values in TERM_GROUPS.items():
            if token in values:
                expanded.append(canonical)
    return expanded


def text_vector(text: str, dimensions: int = 128) -> np.ndarray:
    vector = np.zeros(dimensions, dtype=np.float32)
    tokens = _tokens(text)
    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "little") % dimensions
        sign = 1.0 if digest[4] % 2 else -1.0
        vector[bucket] += sign
    for left, right in zip(tokens, tokens[1:]):
        digest = hashlib.blake2b(f"{left}:{right}".encode("utf-8"), digest_size=8).digest()
        vector[int.from_bytes(digest[:4], "little") % dimensions] += 0.65
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm else vector


class Catalog:
    def __init__(self, project_root: Path):
        self.root = project_root
        self.data_dir = project_root / "data"
        self.db_path = self.data_dir / "terratrace.sqlite3"
        self.demo_dir = self.data_dir / "demo"
        self.upload_dir = self.data_dir / "uploads"
        self.generated_dir = self.data_dir / "generated"
        self.remoteclip = RemoteClipIndex(project_root)
        for directory in (self.data_dir, self.demo_dir, self.upload_dir, self.generated_dir):
            directory.mkdir(parents=True, exist_ok=True)
        self._init_database()
        self._prepare_demo_pair()
        self._seed()

    def connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, factory=ClosingConnection)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_database(self) -> None:
        with self.connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS scenes (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    location TEXT NOT NULL,
                    acquired_at TEXT NOT NULL,
                    before_at TEXT,
                    sensor TEXT NOT NULL,
                    cloud REAL NOT NULL DEFAULT 0,
                    quality REAL NOT NULL DEFAULT 1,
                    description TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    surface TEXT NOT NULL DEFAULT 'after',
                    before_path TEXT,
                    after_path TEXT,
                    crs TEXT NOT NULL DEFAULT 'EPSG:32643',
                    bbox TEXT NOT NULL,
                    aoi_area_ha REAL NOT NULL DEFAULT 96,
                    persistence INTEGER NOT NULL DEFAULT 1,
                    source TEXT NOT NULL DEFAULT 'local-demo',
                    checksum TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scene_id TEXT NOT NULL,
                    decision TEXT NOT NULL CHECK(decision IN ('confirmed','rejected','uncertain')),
                    note TEXT NOT NULL DEFAULT '',
                    analyst TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS processing_runs (
                    id TEXT PRIMARY KEY,
                    scene_id TEXT NOT NULL,
                    pipeline TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def _prepare_demo_pair(self) -> None:
        before = self.demo_dir / "narmada-before.png"
        after = self.demo_dir / "narmada-after.png"
        if before.exists() and after.exists():
            return
        composite = self.root / "dist" / "assets" / "satellite-change-pair.png"
        image = Image.open(composite).convert("RGB")
        midpoint = image.width // 2
        image.crop((0, 0, midpoint, image.height)).save(before)
        image.crop((midpoint, 0, image.width, image.height)).save(after)

    def _seed(self) -> None:
        before = str((self.demo_dir / "narmada-before.png").relative_to(self.root)).replace("\\", "/")
        after = str((self.demo_dir / "narmada-after.png").relative_to(self.root)).replace("\\", "/")
        scenes = [
            ("TTE-2026-017", "Narmada logistics expansion", "Hoshangabad · MP", "2022-01-17", "2021-11-08", "Sentinel-2 L2A", 4, .96, "industrial construction near a river with large logistics warehouses and new access roads", "industrial,construction,warehouse,logistics,river,water", "after", before, after, 96, 1),
            ("TTE-2026-042", "Riverside industrial construction", "Bharuch · GJ", "2023-03-09", "2022-12-14", "Sentinel-2 L2A", 7, .93, "industrial development and cleared earth near a broad river channel", "industrial,construction,river,clearing", "after", before, after, 118, 1),
            ("TTE-2026-105", "Warehouse complex near channel", "Nagpur · MH", "2025-01-27", "2024-10-04", "Sentinel-2 L2A", 6, .91, "warehouse complex and transport access close to a water channel", "warehouse,logistics,road,water", "after", before, after, 104, 1),
            ("TTE-2026-331", "Transport yard near tributary", "Vadodara · GJ", "2022-12-14", "2022-08-20", "Sentinel-2 L2A", 10, .89, "transport yard open ground and road corridor near a tributary", "transport,road,open ground,river", "before", before, after, 92, 0),
            ("TTE-2026-208", "Agricultural clearing near water", "Khandwa · MP", "2024-02-21", "2023-11-06", "Sentinel-2 L2A", 13, .86, "seasonal agricultural fields and clearing near water", "agriculture,seasonal,clearing,water", "before", before, after, 110, 0),
        ]
        with self.connection() as connection:
            for row in scenes:
                checksum = sha256_file(self.root / row[12]) if row[12] else None
                connection.execute(
                    """INSERT OR REPLACE INTO scenes
                    (id,name,location,acquired_at,before_at,sensor,cloud,quality,description,tags,surface,before_path,after_path,bbox,aoi_area_ha,persistence,source,checksum,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (*row[:13], json.dumps([77.62, 22.69, 77.81, 22.87]), row[13], row[14], "synthetic-demo", checksum, utc_now()),
                )

    def stats(self) -> dict[str, Any]:
        with self.connection() as connection:
            scenes = connection.execute("SELECT COUNT(*) FROM scenes").fetchone()[0]
            reviews = connection.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
            runs = connection.execute("SELECT COUNT(*) FROM processing_runs").fetchone()[0]
        return {"scenes": scenes, "reviews": reviews, "processing_runs": runs, "database": str(self.db_path), "engine": self.remoteclip.engine_name}

    def get_scene(self, scene_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM scenes WHERE id = ?", (scene_id,)).fetchone()
        return dict(row) if row else None

    def search(self, query: str, sensor: str = "", max_cloud: float = 100, limit: int = 8) -> list[dict[str, Any]]:
        query_embedding = text_vector(query)
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM scenes WHERE cloud <= ? ORDER BY acquired_at DESC", (max_cloud,)).fetchall()
        records = [dict(row) for row in rows]
        try:
            model_scores = self.remoteclip.scores(query, records)
        except Exception as exc:
            print(f"[TerraTrace] RemoteCLIP unavailable, using hybrid fallback: {exc}")
            model_scores = {}
        matches = []
        for item in records:
            if sensor and sensor.lower() not in ("all", "all sensors") and item["sensor"].lower() != sensor.lower():
                continue
            document = f'{item["name"]} {item["description"]} {item["tags"]} {item["location"]}'
            embedding = text_vector(document)
            cosine = float(np.dot(query_embedding, embedding))
            token_overlap = len(set(_tokens(query)) & set(_tokens(document))) / max(1, len(set(_tokens(query))))
            semantic = max(0.0, model_scores.get(item["id"], 0.58 * cosine + 0.42 * token_overlap))
            # Precision-first reranking: semantic relevance is tempered by observation
            # quality so a cleaner defensible scene can outrank a slightly closer text hit.
            score = min(
                0.98,
                0.32 + 0.28 * semantic + 0.20 * float(item["quality"]) + 0.20 * (1 - float(item["cloud"]) / 100),
            )
            matches.append({
                "id": item["id"], "name": item["name"], "location": item["location"],
                "date": item["acquired_at"], "before_date": item["before_at"], "sensor": item["sensor"],
                "cloud": item["cloud"], "quality": item["quality"], "score": round(score, 3),
                "surface": item["surface"], "engine": self.remoteclip.engine_name if model_scores else "offline-hybrid-128d", "source": item["source"],
            })
        return sorted(matches, key=lambda item: item["score"], reverse=True)[:limit]

    def analyze(self, scene_id: str) -> dict[str, Any]:
        scene = self.get_scene(scene_id)
        if not scene or not scene["before_path"] or not scene["after_path"]:
            raise KeyError(scene_id)
        mask_name = f"{re.sub(r'[^A-Za-z0-9_-]', '-', scene_id)}-mask.png"
        result = analyze_pair(
            self.root / scene["before_path"], self.root / scene["after_path"], self.generated_dir / mask_name,
            aoi_area_ha=float(scene["aoi_area_ha"]), persistence=bool(scene["persistence"]),
        )
        result.update({
            "scene_id": scene_id, "name": scene["name"], "location": scene["location"],
            "before_date": scene["before_at"], "after_date": scene["acquired_at"], "sensor": scene["sensor"],
            "crs": scene["crs"], "mask_url": f"/api/masks/{mask_name}",
            "provenance": {"source": scene["source"], "checksum": scene["checksum"], "pipeline": "robust-rgb-difference-v1"},
        })
        run_id = f"run-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{scene_id.lower()}"
        with self.connection() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO processing_runs (id,scene_id,pipeline,result_json,created_at) VALUES (?,?,?,?,?)",
                (run_id, scene_id, result["method"], json.dumps(result), utc_now()),
            )
        result["processing_run"] = run_id
        return result

    def add_review(self, scene_id: str, decision: str, note: str, analyst: str, evidence: dict[str, Any]) -> dict[str, Any]:
        if decision not in {"confirmed", "rejected", "uncertain"}:
            raise ValueError("invalid decision")
        if not self.get_scene(scene_id):
            raise KeyError(scene_id)
        created_at = utc_now()
        with self.connection() as connection:
            cursor = connection.execute(
                "INSERT INTO reviews (scene_id,decision,note,analyst,evidence_json,created_at) VALUES (?,?,?,?,?,?)",
                (scene_id, decision, note[:1000], analyst[:100], json.dumps(evidence), created_at),
            )
        return {"id": cursor.lastrowid, "scene_id": scene_id, "decision": decision, "analyst": analyst, "created_at": created_at}

    def reviews(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute("SELECT id,scene_id,decision,note,analyst,created_at FROM reviews ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def ingest_pair(self, metadata: dict[str, Any], before_path: Path, after_path: Path) -> dict[str, Any]:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        scene_id = metadata.get("id") or f"TTE-LOCAL-{stamp}"
        scene_id = re.sub(r"[^A-Za-z0-9_-]", "-", scene_id)[:64]
        checksum = sha256_file(after_path)
        with self.connection() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO scenes
                (id,name,location,acquired_at,before_at,sensor,cloud,quality,description,tags,surface,before_path,after_path,crs,bbox,aoi_area_ha,persistence,source,checksum,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    scene_id, str(metadata.get("name") or "Local comparison pair")[:160], str(metadata.get("location") or "Local AOI")[:160],
                    str(metadata.get("after_date") or datetime.now().date()), str(metadata.get("before_date") or "unknown"),
                    str(metadata.get("sensor") or "RGB local imagery")[:80], float(metadata.get("cloud") or 0), .9,
                    str(metadata.get("description") or "local image pair for change analysis")[:500],
                    str(metadata.get("tags") or "local,change"), "after",
                    str(before_path.relative_to(self.root)).replace("\\", "/"), str(after_path.relative_to(self.root)).replace("\\", "/"),
                    str(metadata.get("crs") or "LOCAL-PIXEL"), json.dumps(metadata.get("bbox") or [0, 0, 1, 1]),
                    float(metadata.get("aoi_area_ha") or 100), int(bool(metadata.get("persistence", True))), "local-upload", checksum, utc_now(),
                ),
            )
        return self.get_scene(scene_id) or {}
