# SIH26227 — TerraTrace EO prototype

An offline, evidence-first Earth observation analyst workbench built for an internal hackathon demonstration.

## Start the working prototype

Double-click `start-SIH26227.bat`. The prototype opens at `http://127.0.0.1:8765` and runs entirely on the computer.

Requirements:

- Python 3.11 or newer
- NumPy 2.x
- Pillow 11.x or newer

Install the two Python libraries once, if required:

```powershell
python -m pip install -r requirements.txt
```

The local service creates its SQLite catalogue automatically. It supports:

- Offline natural-language retrieval using a compact 128-dimensional hybrid index
- AOI-quality filtering by sensor and cloud percentage
- Real before/after RGB change measurement
- Local alignment search and robust radiometric normalisation
- Generated pixel-level change-mask overlays
- SHA-256 source-asset verification and processing-run records
- SQLite-backed analyst decisions
- Local image-pair ingestion from the interface
- Static demonstration fallback through `SIH26227.html`

## Optional RemoteCLIP mode

The core prototype deliberately starts without a heavyweight model installation. To enable real RemoteCLIP ViT-B/32 retrieval while internet access is available, double-click `install-RemoteCLIP.bat`. It creates a project-local environment, installs the model runtime, downloads the official checkpoint, and builds an exact local NumPy index.

After setup, `start-SIH26227.bat` automatically uses that environment. The status badge reports `remoteclip-vib32-exact` when the model is active and `offline-hybrid-128d` when the safe fallback is active.

Official sources:

- RemoteCLIP: https://github.com/ChenDelong1999/RemoteCLIP
- OpenCLIP: https://pypi.org/project/open-clip-torch/

Run the test suite:

```powershell
python -m unittest -v
```

## Important demonstration boundary

The included satellite pair and seeded case metadata are synthetic demonstration material. The measured change score and mask are calculated from the actual included pixels, but this MVP is not a trained RemoteCLIP or multispectral Sentinel-2 production pipeline. Do not present the compact retrieval engine as RemoteCLIP or the RGB change proxy as an operational spectral detector.

See `DEMO_GUIDE.md` for the five-minute presentation flow.
