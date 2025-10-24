# WESTCAT Overlay Reloaded

Phase 1 bootstrap scaffold. Activate the local environment and run the stub app to verify setup.

## Quick Start

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m app
```

The stub prints `BOOTSTRAP_OK` and environment metadata. Use the provided VS Codium task for the same command.

## Phase 2 — Overlay Window (no animation yet)
- Task: **Run: WESTCAT overlay (window)**
- Keys: [Esc]=Quit, [T]=Toggle click-through, [S]=Size S/M/L, [O]=Cycle opacity, [R]=Re-center.
- Settings: Stored via QSettings (per-user). Window is translucent, always-on-top, frameless.

## Phase 2.5 — Player Demo (no assets)
- Task: **Run: WESTCAT overlay (player demo)**
- Purpose: Full lifecycle test without PNG/SVG assets.
- Hotkeys: Space=Play/Pause, H=HUD, [ / ]=FPS, N=Step (paused). Inherited: Esc, T, S, O, R.
- Tip: Press **?** anytime to see the key list and a short description on screen.

## Phase 3A — Poll Overlay (no assets)
- Task: **Run: WESTCAT overlay (poll demo)**
- How to answer: click an option, or press **1/2/3…**. Press **Enter** to advance if needed, **Esc** to quit.
- A small “Thanks” screen appears at the end. Answers are saved to `./data/poll_responses.json`.

## Phase 3B — Bryan Demo Integration
- Task: **Run: WESTCAT overlay (Bryan demo)**
- Types supported: Acknowledge (auto-advance), Multiple Choice (click or 1/2/3/4 or A–D), Short Text (type + Enter), Final Trigger (five rapid clicks).
- Finish: At the final step, click five times quickly anywhere in the window to play a sneeze and export results to your Desktop as `WestCat_Poll_Results_YYYYMMDD_HHMMSS.txt`.
- Optional audio: If `assets/sfx/sneeze.wav` exists, it will play; otherwise a system beep is used.

## Phase 3C — Bryan Duo Demo (Cat + Bubble)
- Task: **Run: WESTCAT overlay (Bryan duo demo)**
- Two windows: a transparent **Cat** and a **Speech Bubble** (questions).
- Cat appears first; the Bubble appears slightly later **beside** the Cat (no overlap).
- Drag either window by holding the left mouse button anywhere that isn't a button/choice.
- Answer MCQs by clicking or pressing **1–4**. For text, **type in the box and press Enter**.
- At the final screen, **click the Cat five times quickly** to open the **Dev Menu**.
- Export path: **Desktop** (fallback `./data/WestCat_Poll_Results_*.txt`).

**Right-click menu (both windows):**
- **Size (Cat):** S / M / L (applies to the Cat only)
- **Opacity (Cat):** slider that fades the Cat only (Bubble stays readable)
- **Flip Cat (Mirror)**
- **Open Dev Menu**
- **Close:** shuts both windows and exits

In the **Dev Menu**, use **Edit Questions** for Add/Remove, drag-to-reorder, and Import/Export (no raw JSON shown).
