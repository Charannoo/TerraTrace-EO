# SIH26227 — 70-hour prototype sprint

The repository already provides the working baseline: local search, SQLite metadata, measured RGB change, change-mask generation, evidence hashes, processing runs, pair ingestion, review persistence, offline fallback, tests, and an optional RemoteCLIP adapter.

## Hours 0–10 — Working vertical slice — complete

- Local application and one-click Windows launcher
- Seeded offline catalogue and quality-filtered retrieval
- Real before/after pixel measurement and mask generation
- Evidence, provenance, timeline, similar-site and review interfaces
- SQLite audit records and automated tests

Acceptance: the five-minute workflow runs without internet or external services.

## Hours 10–24 — Freeze representative imagery

- Add one construction case, one water-change case and one hard no-change case
- Use genuinely aligned public/organizer imagery where licensing permits
- Record source, acquisition dates, sensor, CRS, AOI and licence
- Preserve a prepared synthetic fallback in case venue data fails

Acceptance: every demo case has a source record and one case intentionally abstains or returns no change.

## Hours 24–36 — RemoteCLIP retrieval

- Run `install-RemoteCLIP.bat` while network access is available
- Confirm ViT-B/32 inference on the GTX 1650; use CPU if VRAM is unstable
- Build the exact local vector index
- Test 10–20 held-out natural-language queries
- Keep `offline-hybrid-128d` as the guaranteed fallback

Acceptance: model status reports `remoteclip-vib32-exact` and the prepared queries return sensible Top-5 results.

## Hours 36–50 — Quality and change hardening

- Add SCL/cloud-mask ingestion if Sentinel-2 L2A bands are available
- Reject low-overlap or poorly aligned pairs
- Validate the dominant-region mask on construction and no-change cases
- Add an explicit `INSUFFICIENT EVIDENCE` result
- Confirm temporal persistence using a third observation where available

Acceptance: cloud/shadow and one seasonal hard negative are not presented as confident change.

## Hours 50–60 — Metrics and reliability

- Measure search latency, analysis latency, index size and database size
- Record precision on the small prepared validation set
- Run the complete test suite from a fresh copy
- Test with Wi-Fi disabled
- Test on the actual presentation laptop and screen resolution

Acceptance: a reproducible metrics table exists and the complete demo restarts cleanly three times.

## Hours 60–66 — Judge package

- Freeze code and demo data
- Export one example GeoJSON/audit record
- Add architecture and false-alarm-suppression slides
- Capture backup screenshots and a short backup screen recording
- Prepare exact answers for resolution limits, confidence calibration and event-date wording

Acceptance: the team can explain every number shown in the interface.

## Hours 66–70 — Rehearsal and contingency

- Rehearse the five-minute script at least three times
- Give one teammate the “hostile judge” role
- Copy the complete folder to a USB drive and a second laptop
- Do not add new models or architectural features
- Use the final hour only for blocking defects

Acceptance: two people can independently start and deliver the demo without developer assistance.

## Deferred until after the hackathon

- Large-area FAISS sharding
- Full B02/B03/B04/B08/B11/SCL GeoTIFF/COG production ingestion
- BIT/ChangeFormer or other learned change models
- Sentinel-1 fusion
- Authentication, multi-user roles and production deployment
