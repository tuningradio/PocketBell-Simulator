#!/usr/bin/env python3
# =================================
# PocketBell Simulator Ver 1.1.1 by JA1XPM 2026/05/07
# =================================

# dtmftest_pager.py
# Raw DTMF TX/RX with minimal control logic
#
# Behavior:
# - TX sends the raw DTMF sequence as provided
# - RX outputs raw DTMF digits (as-is)
#
# Notes:
# - No UTF-8 conversion, no framing/decoding, no EOF handling.
# - Tail/hold tone (1800 Hz) is kept after TX.
# - All digits have the same duration (no "last digit longer").

import argparse
import time
from dataclasses import dataclass
from typing import Optional, List

import numpy as np
import sounddevice as sd
import serial


DTMF_LOWS = np.array([697, 770, 852, 941], dtype=float)
DTMF_HIGHS = np.array([1209, 1336, 1477, 1633], dtype=float)

DTMF_KEYS = [
    ['1', '2', '3', 'A'],
    ['4', '5', '6', 'B'],
    ['7', '8', '9', 'C'],
    ['*', '0', '#', 'D'],
]

KEY_TO_FREQ = {}
for r, low in enumerate(DTMF_LOWS):
    for c, high in enumerate(DTMF_HIGHS):
        KEY_TO_FREQ[DTMF_KEYS[r][c]] = (float(low), float(high))


def _apply_ramp(x: np.ndarray, sr: int, ramp_ms: int) -> np.ndarray:
    n = len(x)
    ramp_n = int(sr * ramp_ms / 1000)
    ramp_n = max(1, min(ramp_n, n // 2)) if n >= 2 else 0
    if ramp_n > 0:
        ramp = np.linspace(0.0, 1.0, ramp_n, dtype=np.float32)
        x[:ramp_n] *= ramp
        x[-ramp_n:] *= ramp[::-1]
    return x


def generate_dtmf_tone(key: str, sr: int, tone_ms: int,
                       ramp_ms: int = 5, level: float = 0.6) -> np.ndarray:
    low, high = KEY_TO_FREQ[key]
    n = max(1, int(sr * tone_ms / 1000))
    t = np.arange(n, dtype=np.float32) / float(sr)
    tone = 0.5 * (np.sin(2*np.pi*low*t) + np.sin(2*np.pi*high*t))
    tone = _apply_ramp(tone.astype(np.float32), sr, ramp_ms)
    return (level * tone).astype(np.float32)


def generate_sine(freq_hz: float, sr: int, dur_s: float,
                  ramp_ms: int = 10, level: float = 0.12) -> np.ndarray:
    n = max(1, int(sr * dur_s))
    t = np.arange(n, dtype=np.float32) / float(sr)
    tone = np.sin(2*np.pi*freq_hz*t).astype(np.float32)
    tone = _apply_ramp(tone, sr, ramp_ms)
    return (level * tone).astype(np.float32)


def generate_sequence(keys: List[str], sr: int, tone_ms: int, gap_ms: int) -> np.ndarray:
    """Generate a DTMF tone sequence; all digits have the same duration (tone_ms)."""
    gap_n = int(sr * gap_ms / 1000)
    gap = np.zeros(gap_n, dtype=np.float32)
    parts: List[np.ndarray] = []
    for k in keys:
        parts.append(generate_dtmf_tone(k, sr, tone_ms))
        if gap_n > 0:
            parts.append(gap)
    return np.concatenate(parts) if parts else np.zeros(0, dtype=np.float32)


@dataclass
class DetectConfig:
    sample_rate: int = 8000
    block_ms: int = 20
    min_tone_ms: int = 120
    energy_floor: float = 2e-5
    ratio_thresh: float = 3.0


def goertzel_power(x: np.ndarray, sr: int, freq: float) -> float:
    n = len(x)
    if n <= 0:
        return 0.0
    k = int(0.5 + (n * freq) / sr)
    w = (2.0 * np.pi / n) * k
    coeff = 2.0 * np.cos(w)
    s0 = s1 = s2 = 0.0
    for sample in x:
        s0 = float(sample) + coeff * s1 - s2
        s2 = s1
        s1 = s0
    return s1*s1 + s2*s2 - coeff*s1*s2


def detect_digit(block: np.ndarray, cfg: DetectConfig) -> Optional[str]:
    x = block.astype(np.float32)
    x = x - float(np.mean(x))

    energy = float(np.mean(x * x))
    if energy < cfg.energy_floor:
        return None

    low_p = np.array([goertzel_power(x, cfg.sample_rate, f) for f in DTMF_LOWS])
    high_p = np.array([goertzel_power(x, cfg.sample_rate, f) for f in DTMF_HIGHS])

    li = int(np.argmax(low_p))
    hi = int(np.argmax(high_p))

    low_sorted = np.sort(low_p)
    high_sorted = np.sort(high_p)

    if low_sorted[-2] > 0 and low_sorted[-1] / low_sorted[-2] < cfg.ratio_thresh:
        return None
    if high_sorted[-2] > 0 and high_sorted[-1] / high_sorted[-2] < cfg.ratio_thresh:
        return None

    return DTMF_KEYS[li][hi]


def do_tx(seq: str, out_dev: int, sr: int,
          tone_ms: int, gap_ms: int,
          com: Optional[str]):

    keys = list(seq)
    print("TX DTMF:", "".join(keys), flush=True)

    ser = None
    if com is not None:
        ser = serial.Serial(com)
        ser.dtr = True  # DTR ON before TX

    try:
        head = generate_sine(1800.0, sr, dur_s=1.0, ramp_ms=10, level=0.12)
        dtmf = generate_sequence(keys, sr, tone_ms, gap_ms)
        tail = generate_sine(1800.0, sr, dur_s=1.0, ramp_ms=10, level=0.12)
        audio = np.concatenate([head, dtmf, tail])
        # --- output channel adaptation (some devices reject mono) ---
        # play audio (channel-safe)
        devinfo = sd.query_devices(out_dev, 'output')
        maxch = int(devinfo.get('max_output_channels', 0) or 0)
        if maxch >= 2 and audio.ndim == 1:
            audio = np.column_stack([audio, audio])
        elif maxch == 1 and audio.ndim == 2:
            audio = audio[:, 0]
        sd.play(audio, samplerate=sr, device=out_dev, blocking=True)

    finally:
        if ser is not None:
            ser.dtr = False  # DTR OFF after TX
            ser.close()


def do_rx(in_dev: int, cfg: DetectConfig):
    block_n = int(cfg.sample_rate * (cfg.block_ms / 1000.0))
    min_blocks = max(1, int(np.ceil(cfg.min_tone_ms / cfg.block_ms)))

    stable_digit: Optional[str] = None
    stable_count = 0

    print("Listening for raw DTMF... Ctrl+C to stop.", flush=True)

    def cb(indata, frames, time_info, status):
        nonlocal stable_digit, stable_count
        x = indata[:, 0].copy()
        d = detect_digit(x, cfg)

        if d is None:
            stable_digit = None
            stable_count = 0
            return

        if d == stable_digit:
            stable_count += 1
        else:
            stable_digit = d
            stable_count = 1

        if stable_count >= min_blocks:
            print(d, end="", flush=True)
            stable_digit = None
            stable_count = 0

    with sd.InputStream(device=in_dev, channels=1,
                        samplerate=cfg.sample_rate,
                        blocksize=block_n,
                        dtype="float32",
                        callback=cb):
        while True:
            time.sleep(0.25)


def list_devices():
    print(sd.query_devices())


def main():
    ap = argparse.ArgumentParser(prog="dtmftest_pager.py")
    sp = ap.add_subparsers(dest="cmd", required=True)

    sp_dev = sp.add_parser("devices")
    sp_dev.set_defaults(fn=lambda a: list_devices())

    sp_tx = sp.add_parser("tx")
    sp_tx.add_argument("seq")
    sp_tx.add_argument("-out", type=int, required=True)
    sp_tx.add_argument("--sr", type=int, default=8000)
    sp_tx.add_argument("--tone-ms", type=int, default=130)
    sp_tx.add_argument("--gap-ms", type=int, default=90)
    sp_tx.add_argument("--com", type=str, default=None)
    sp_tx.set_defaults(fn=lambda a: do_tx(
        a.seq, a.out, a.sr, a.tone_ms, a.gap_ms, a.com
    ))

    sp_rx = sp.add_parser("rx")
    sp_rx.add_argument("-in", dest="in_", type=int, required=True)
    sp_rx.add_argument("--sr", type=int, default=8000)
    sp_rx.add_argument("--block-ms", type=int, default=20)
    sp_rx.add_argument("--min-tone-ms", type=int, default=120)
    sp_rx.add_argument("--energy-floor", type=float, default=2e-5)
    sp_rx.add_argument("--ratio", type=float, default=3.0)
    sp_rx.set_defaults(fn=lambda a: do_rx(
        a.in_,
        DetectConfig(
            sample_rate=a.sr,
            block_ms=a.block_ms,
            min_tone_ms=a.min_tone_ms,
            energy_floor=a.energy_floor,
            ratio_thresh=a.ratio,
        )
    ))

    args = ap.parse_args()
    try:
        args.fn(args)
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)


if __name__ == "__main__":
    main()
