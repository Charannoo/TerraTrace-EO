# SIH26227 five-minute demo guide

## 0:00–0:35 — Set the problem

“TerraTrace EO is an offline analyst workbench. It helps an analyst discover relevant places, reject weak observations, identify the earliest defensible change interval, and preserve the evidence behind every decision.”

State clearly that the included imagery and case metadata are synthetic demo material. The retrieval, pixel analysis, hashes, SQLite records, and analyst decisions run locally.

## 0:35–1:25 — Search

1. Start with `industrial construction near a river`.
2. Keep Sentinel-2 L2A and the 15% cloud limit selected.
3. Click **Run search**.
4. Explain that the hackathon engine is a compact offline hybrid index. RemoteCLIP is the next model adapter, not a feature being faked in this build.

## 1:25–2:05 — Temporal reasoning

1. Open the highest-ranked candidate.
2. Move to **Change timeline**.
3. Point out the rejected cloudy observation.
4. Explain that the answer is an interval—not a falsely exact event date.

## 2:05–3:10 — Measured evidence

1. Open **Evidence viewer**.
2. Click **Run measured analysis**.
3. Drag the before/after divider.
4. Toggle the measured change mask and registration grid.
5. Show the changed-pixel fraction, estimated area, alignment shift, threshold, source hashes, and processing-run ID.

## 3:10–3:50 — Analyst decision

1. Confirm the candidate.
2. Open **Review queue**.
3. Show that the queue and daily counters changed.
4. Explain that the decision was appended to SQLite together with the evidence snapshot.

## 3:50–4:35 — Local ingestion

1. Click **Ingest local image pair** in the sidebar.
2. Select an aligned before image and after image.
3. Enter dates, sensor, AOI name and estimated AOI area.
4. Click **Ingest and analyse**.
5. The new record is stored, measured and added to search without rebuilding existing records.

## 4:35–5:00 — Close

“This prototype does not replace the analyst. It narrows where they look, measures change over usable evidence, and keeps the result reproducible. The next engineering step replaces the compact retrieval adapter with RemoteCLIP and the RGB proxy with Sentinel-2 multispectral processing.”

## Judge-safe answers

- **Is this RemoteCLIP?** Not yet. The prototype uses a real compact offline hybrid index so the workflow is testable without downloading a large model. The model boundary is explicit.
- **Is this real Sentinel-2 processing?** The seeded pair is synthetic RGB demo imagery. Pixel change, alignment, thresholding, masks, hashes and records are computed live. Multispectral B02/B03/B04/B08/B11/SCL ingestion is the next adapter.
- **Can it run without internet?** Yes, after the two small Python dependencies are installed.
- **Why report an interval?** Satellite acquisitions bound the event; they do not prove the exact moment it happened.
