from __future__ import annotations

from pathlib import Path


def main() -> None:
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise SystemExit("Install requirements-remoteclip.txt first.") from exc

    project_root = Path(__file__).resolve().parents[1]
    model_dir = project_root / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    path = hf_hub_download(
        repo_id="chendelong/RemoteCLIP",
        filename="RemoteCLIP-ViT-B-32.pt",
        local_dir=model_dir,
    )
    print(f"RemoteCLIP checkpoint saved to: {path}")


if __name__ == "__main__":
    main()

