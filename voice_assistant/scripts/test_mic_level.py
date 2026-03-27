#!/usr/bin/env python3
"""Interactive microphone level monitor for threshold calibration.

Controls:
    + / =  increase threshold by 0.1%
    - / _  decrease threshold by 0.1%
    ]      increase threshold by 1.0%
    [      decrease threshold by 1.0%
    r      reset peak meter
    q      quit
"""

from __future__ import annotations

import argparse
import select
import sys
import termios
import threading
import time
import tty
from dataclasses import dataclass

import numpy as np
import sounddevice as sd


@dataclass
class MonitorState:
    threshold_pct: float
    level_pct: float = 0.0
    peak_pct: float = 0.0
    clipped: bool = False
    running: bool = True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive microphone threshold monitor")
    parser.add_argument("--threshold", type=float, default=1.0, help="Initial threshold percentage")
    parser.add_argument("--sample-rate", type=int, default=16000, help="Microphone sample rate")
    parser.add_argument("--channels", type=int, default=1, help="Input channels")
    parser.add_argument("--block-ms", type=float, default=100.0, help="Audio block size in milliseconds")
    parser.add_argument("--device", default=None, help="Input device name or index")
    parser.add_argument("--bar-width", type=int, default=60, help="Terminal bar width")
    return parser.parse_args()


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def build_bar(level_pct: float, threshold_pct: float, peak_pct: float, width: int) -> str:
    filled = int(clamp(level_pct, 0.0, 100.0) * width / 100.0)
    threshold_pos = min(width - 1, max(0, int(clamp(threshold_pct, 0.0, 100.0) * width / 100.0)))
    peak_pos = min(width - 1, max(0, int(clamp(peak_pct, 0.0, 100.0) * width / 100.0)))

    chars: list[str] = []
    for i in range(width):
        if i == threshold_pos:
            chars.append("|")
        elif i == peak_pos:
            chars.append("P")
        elif i < filled:
            chars.append("#")
        else:
            chars.append("-")
    return "".join(chars)


def keyboard_loop(state: MonitorState) -> None:
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        while state.running:
            ready, _, _ = select.select([sys.stdin], [], [], 0.1)
            if not ready:
                continue

            char = sys.stdin.read(1)
            if char in {"q", "Q"}:
                state.running = False
            elif char in {"+", "="}:
                state.threshold_pct = clamp(state.threshold_pct + 0.1, 0.0, 100.0)
            elif char in {"-", "_"}:
                state.threshold_pct = clamp(state.threshold_pct - 0.1, 0.0, 100.0)
            elif char == "]":
                state.threshold_pct = clamp(state.threshold_pct + 1.0, 0.0, 100.0)
            elif char == "[":
                state.threshold_pct = clamp(state.threshold_pct - 1.0, 0.0, 100.0)
            elif char in {"r", "R"}:
                state.peak_pct = state.level_pct
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def main() -> int:
    args = parse_args()
    blocksize = int(args.sample_rate * (args.block_ms / 1000.0))
    state = MonitorState(threshold_pct=clamp(args.threshold, 0.0, 100.0))
    lock = threading.Lock()

    def callback(indata, frames, time_info, status) -> None:
        del frames, time_info
        chunk = np.asarray(indata[:, 0], dtype=np.float32)
        rms = float(np.sqrt(np.mean(chunk ** 2))) if chunk.size else 0.0
        peak = float(np.max(np.abs(chunk))) if chunk.size else 0.0
        level_pct = rms * 100.0
        clipped = peak >= 0.99

        with lock:
            state.level_pct = level_pct
            state.peak_pct = max(state.peak_pct * 0.96, level_pct)
            state.clipped = clipped or bool(status)

    key_thread = threading.Thread(target=keyboard_loop, args=(state,), daemon=True)
    key_thread.start()

    print("=== Monitor Interativo do Microfone ===")
    print("Controles: +/- 0.1% | [/] 1.0% | r reset peak | q sair")
    print(f"Sample rate: {args.sample_rate} Hz | block: {args.block_ms:.0f} ms | device: {args.device or 'default'}")
    print()

    try:
        with sd.InputStream(
            samplerate=args.sample_rate,
            channels=args.channels,
            dtype="float32",
            blocksize=blocksize,
            device=args.device,
            callback=callback,
        ):
            while state.running:
                with lock:
                    level_pct = state.level_pct
                    threshold_pct = state.threshold_pct
                    peak_pct = state.peak_pct
                    clipped = state.clipped
                    state.clipped = False

                status = "FALA" if level_pct >= threshold_pct else "silencio"
                clip_label = " CLIP" if clipped else ""
                bar = build_bar(level_pct, threshold_pct, peak_pct, args.bar_width)
                line = (
                    f"\r[{bar}] "
                    f"nivel={level_pct:5.2f}% "
                    f"threshold={threshold_pct:5.2f}% "
                    f"peak={peak_pct:5.2f}% "
                    f"[{status}{clip_label}]   "
                )
                sys.stdout.write(line)
                sys.stdout.flush()
                time.sleep(args.block_ms / 1000.0)
    except KeyboardInterrupt:
        state.running = False
    finally:
        state.running = False
        key_thread.join(timeout=0.2)
        sys.stdout.write("\n")
        sys.stdout.flush()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
