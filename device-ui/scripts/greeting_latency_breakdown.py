"""Break wake-to-first-sound latency into its segments, per wake.

Usage:
    python scripts/greeting_latency_breakdown.py /path/to/kivy.log

Answers one question: when the greeting feels slow, WHICH part was slow?
Swapping the Realtime model only changes segment C. If A, B or D dominate,
a faster model cannot help and the fix is elsewhere.

Segments (from the VOICE_EVENT mono_ms timeline, per wake_id):

    A  wake_activate      -> session_ready         session setup
       Cold: mint + WebSocket + session config. Warm standby should make
       this ~0 by doing it ahead of the wake. If it is NOT ~0 with
       REALTIME_WARM_STANDBY=1, standby is not actually engaging.

    B  session_ready      -> response_created      request turnaround
       Our code deciding to ask for the greeting, plus one round trip.

    C  response_created   -> first_inbound_audio   MODEL INFERENCE  <-- 2.1 helps here
       OpenAI reading ~9.9k tokens of tool definitions + instructions and
       generating the first audio token. The only model-dependent segment.

    D  first_inbound_audio-> first_speaker_write   local playback
       Our aplay path. d8750c5 pre-warms this; should be small.

Read-only. Never connects to the device.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean, median

MARKER = "VOICE_EVENT "

# Ordered checkpoints; each consecutive pair forms a segment.
CHECKPOINTS = [
    "wake_activate",
    "session_ready",
    "response_created",
    "first_inbound_audio",
    "first_speaker_write",
]

SEGMENTS = [
    ("A setup      ", "wake_activate", "session_ready", "warm standby should zero this"),
    ("B turnaround ", "session_ready", "response_created", "our code + 1 round trip"),
    ("C inference  ", "response_created", "first_inbound_audio", "MODEL - 2.1 helps here"),
    ("D playback   ", "first_inbound_audio", "first_speaker_write", "our aplay path"),
]


def iter_events(path: Path):
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            idx = line.find(MARKER)
            if idx < 0:
                continue
            try:
                yield json.loads(line[idx + len(MARKER):].strip())
            except (ValueError, TypeError):
                continue


def collect(path: Path) -> dict[str, dict]:
    """Group checkpoint timestamps by wake_id, keeping the FIRST of each."""
    wakes: dict[str, dict] = defaultdict(dict)
    for ev in iter_events(path):
        name = ev.get("event")
        if name not in CHECKPOINTS:
            continue
        wake = str(ev.get("wake_id") or "")
        if not wake:
            continue
        # First occurrence wins: a barge-in can create later response_created
        # events in the same wake, which are not part of the greeting path.
        wakes[wake].setdefault(name, ev.get("mono_ms"))
        if name == "wake_activate":
            wakes[wake]["_prewarm"] = ev.get("prewarm")
    return wakes


def fmt(ms: float) -> str:
    return f"{ms:8.0f} ms"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("logfile", type=Path)
    ap.add_argument("--per-wake", action="store_true", help="show every wake, not just the summary")
    args = ap.parse_args()

    if not args.logfile.exists():
        print(f"No such file: {args.logfile}")
        return 1

    wakes = collect(args.logfile)
    complete = {
        w: d for w, d in wakes.items()
        if all(isinstance(d.get(c), (int, float)) for c in CHECKPOINTS)
    }

    print(f"\nwakes seen: {len(wakes)}   complete timelines: {len(complete)}")
    if not complete:
        print(
            "\nNo complete wake->speaker timelines found.\n"
            "Either the log predates this instrumentation, or sessions are not\n"
            "reaching first_speaker_write. Check for errors around wake_activate."
        )
        return 1

    if args.per_wake:
        print()
        for wake, d in sorted(complete.items(), key=lambda kv: kv[1]["wake_activate"]):
            total = d["first_speaker_write"] - d["wake_activate"]
            parts = " ".join(
                f"{label.strip()}={d[end] - d[start]:.0f}"
                for label, start, end, _ in SEGMENTS
            )
            warm = " warm" if d.get("_prewarm") else " cold"
            print(f"  {wake[:12]:<12}{warm}  total={total:6.0f} ms   {parts}")

    print("\n" + "=" * 72)
    print(f"{'segment':<14}{'median':>12}{'mean':>12}{'worst':>12}   note")
    print("=" * 72)

    totals = [d["first_speaker_write"] - d["wake_activate"] for d in complete.values()]
    seg_medians = []
    for label, start, end, note in SEGMENTS:
        vals = [d[end] - d[start] for d in complete.values()]
        seg_medians.append(median(vals))
        print(f"{label:<14}{fmt(median(vals))}{fmt(mean(vals))}{fmt(max(vals))}   {note}")

    print("-" * 72)
    print(f"{'TOTAL':<14}{fmt(median(totals))}{fmt(mean(totals))}{fmt(max(totals))}")
    print("=" * 72)

    # The actual verdict.
    total_med = median(totals)
    inference_med = seg_medians[2]
    share = (inference_med / total_med * 100.0) if total_med > 0 else 0.0
    print(
        f"\nModel inference is {share:.0f}% of median wake-to-sound "
        f"({inference_med:.0f} of {total_med:.0f} ms)."
    )
    print(
        f"A 25% cut there saves ~{inference_med * 0.25:.0f} ms, i.e. "
        f"{inference_med * 0.25 / total_med * 100.0:.0f}% off the total."
    )
    if share < 40:
        print(
            "\n=> The model is NOT your bottleneck. Look at the largest segment\n"
            "   above; a faster model cannot fix it."
        )
    else:
        print(
            "\n=> The model dominates. 2.1 should be felt, and prompt-caching the\n"
            "   tool definitions would cut this segment further."
        )

    cold = [d for d in complete.values() if not d.get("_prewarm")]
    if cold:
        print(
            f"\nNote: {len(cold)} of {len(complete)} wakes were COLD (no warm standby).\n"
            "   With REALTIME_WARM_STANDBY=1 these should be rare — if most wakes\n"
            "   are cold, standby is not engaging and segment A stays on the path."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
