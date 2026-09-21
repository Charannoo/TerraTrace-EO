from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


class RemoteClipIndex:
    """Optional exact RemoteCLIP retrieval adapter.

    Imports are lazy so the core prototype still runs on a clean machine with
    only NumPy and Pillow. When the official checkpoint and OpenCLIP runtime are
    present, the same API switches to real 512-dimensional image/text vectors.
    """

    model_name = "ViT-B-32"
    checkpoint_name = "RemoteCLIP-ViT-B-32.pt"

    def __init__(self, project_root: Path):
        self.root = project_root
        self.checkpoint = project_root / "models" / self.checkpoint_name
        self.index_dir = project_root / "indexes"
        self.index_path = self.index_dir / "remoteclip-vib32.npz"
        self.meta_path = self.index_dir / "remoteclip-vib32.json"
        self._model: Any = None
        self._preprocess: Any = None
        self._tokenizer: Any = None
        self._torch: Any = None
        self._device = "cpu"
        self._ids: list[str] = []
        self._vectors: np.ndarray | None = None

    @property
    def available(self) -> bool:
        if not self.checkpoint.is_file():
            return False
        try:
            import open_clip  # noqa: F401
            import torch  # noqa: F401
        except ImportError:
            return False
        return True

    @property
    def engine_name(self) -> str:
        return "remoteclip-vib32-exact" if self.available else "offline-hybrid-128d"

    def _load_model(self) -> None:
        if self._model is not None:
            return
        import open_clip
        import torch

        model, _, preprocess = open_clip.create_model_and_transforms(self.model_name)
        checkpoint = torch.load(self.checkpoint, map_location="cpu", weights_only=False)
        state = checkpoint.get("state_dict", checkpoint) if isinstance(checkpoint, dict) else checkpoint
        model.load_state_dict(state)
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model = model.to(self._device).eval()
        self._preprocess = preprocess
        self._tokenizer = open_clip.get_tokenizer(self.model_name)
        self._torch = torch

    def _encode_images(self, paths: list[Path]) -> np.ndarray:
        self._load_model()
        vectors = []
        with self._torch.inference_mode():
            for path in paths:
                tensor = self._preprocess(Image.open(path).convert("RGB")).unsqueeze(0).to(self._device)
                vector = self._model.encode_image(tensor)
                vector = vector / vector.norm(dim=-1, keepdim=True)
                vectors.append(vector.cpu().numpy().astype("float32")[0])
        return np.stack(vectors)

    def _encode_text(self, query: str) -> np.ndarray:
        self._load_model()
        with self._torch.inference_mode():
            tokens = self._tokenizer([query]).to(self._device)
            vector = self._model.encode_text(tokens)
            vector = vector / vector.norm(dim=-1, keepdim=True)
        return vector.cpu().numpy().astype("float32")[0]

    def build(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        if not self.available:
            raise RuntimeError("RemoteCLIP checkpoint or runtime is not installed")
        usable = [record for record in records if record.get("after_path") and (self.root / record["after_path"]).is_file()]
        if not usable:
            raise RuntimeError("No local scene imagery is available for indexing")
        vectors = self._encode_images([self.root / record["after_path"] for record in usable])
        self.index_dir.mkdir(parents=True, exist_ok=True)
        ids = [record["id"] for record in usable]
        np.savez_compressed(self.index_path, vectors=vectors)
        self.meta_path.write_text(json.dumps({"ids": ids, "model": self.model_name, "checkpoint": self.checkpoint_name}, indent=2), encoding="utf-8")
        self._ids, self._vectors = ids, vectors
        return {"engine": self.engine_name, "vectors": len(ids), "dimensions": int(vectors.shape[1]), "device": self._device}

    def _load_index(self) -> bool:
        if self._vectors is not None:
            return True
        if not self.index_path.is_file() or not self.meta_path.is_file():
            return False
        metadata = json.loads(self.meta_path.read_text(encoding="utf-8"))
        data = np.load(self.index_path)
        self._ids = list(metadata["ids"])
        self._vectors = data["vectors"].astype("float32")
        return True

    def scores(self, query: str, records: list[dict[str, Any]]) -> dict[str, float]:
        if not self.available:
            return {}
        current_ids = {record["id"] for record in records if record.get("after_path")}
        if not self._load_index() or set(self._ids) != current_ids:
            self.build(records)
        assert self._vectors is not None
        query_vector = self._encode_text(query)
        scores = self._vectors @ query_vector
        return {scene_id: float(score) for scene_id, score in zip(self._ids, scores)}

