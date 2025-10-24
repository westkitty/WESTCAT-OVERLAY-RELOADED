# Cat Animation – Frame↔Cluster Sync (Quick Guide)

The cat now swaps frames by *cluster* instead of a single static PNG. Each cluster describes:

- `frames`: ordered list or glob of PNGs.
- `fps`: playback speed.
- `loop`: whether to loop or run once.
- `hold_last_ms`: extra time to linger on the final frame (one-shot only).
- `easing`: optional (`linear`, `out_cubic`, `out_back`) easing for one-shots.

The animator keeps track of elapsed milliseconds:

- **Loops:** `frame = floor((elapsed_ms * fps / 1000)) % len(frames)`
- **One-shots:** `p = clamp(elapsed_ms / duration_ms)` → easing → `frame = floor(p * (len(frames) - 1))`

## Operator Workflow

1. Launch the overlay (`Run Task → run:app`). The cat plays `open` then `idle`.
2. Trigger UI states in the bubble:
   - question shown → cat stays in an idle/attentive loop
   - waiting for responses → `idle`
   - exporting/results → `celebrate`
   - finish card → `finish_hold`
3. Open the Dev Menu and use **Play/Pause**, **Step**, or the **Cluster** dropdown to debug animation timing.
4. Capture evidence: `Run Task → run:probe` writes `artifacts/sync/probe.tsv` showing frame indices over time.
5. Adjust `assets/cat/clusters.json` (fps, hold, easing) as needed, rerun the probe, then commit.

Policy: the cat never plays a "speaking" cluster—while the bubble types, remain on idle.

👍 Wayland drag, Dev Menu shortcut, and bubble logic stay untouched. The animator is optional—if assets are missing we fall back to a single idle frame.
