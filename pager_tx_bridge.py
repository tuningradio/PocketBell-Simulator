#!/usr/bin/env python3
# =================================
# PocketBell Simulator Ver 1.1.1 by JA1XPM 2026/05/07
# =================================

import argparse
import asyncio
import json
import re
import threading
import time
from functools import lru_cache
from typing import Optional

import numpy as np
import sounddevice as sd
import websockets

import dtmftest_pager as dtmf

_ALLOWED_TX = re.compile(r'^[0-9A-D\*\#]+$')

CALL_REV = {
    "111":"A","112":"B","113":"C","114":"D","115":"E",
    "121":"F","122":"G","123":"H","124":"I","125":"J",
    "131":"K","132":"L","133":"M","134":"N","135":"O",
    "141":"P","142":"Q","143":"R","144":"S","145":"T",
    "151":"U","152":"V","153":"W","154":"X","155":"Y","156":"Z",
}
LEGACY_KANA_REV = {
    "11":"あ","12":"い","13":"う","14":"え","15":"お",
    "21":"か","22":"き","23":"く","24":"け","25":"こ",
    "31":"さ","32":"し","33":"す","34":"せ","35":"そ",
    "41":"た","42":"ち","43":"つ","44":"て","45":"と",
    "51":"な","52":"に","53":"ぬ","54":"ね","55":"の",
    "61":"は","62":"ひ","63":"ふ","64":"へ","65":"ほ",
    "71":"ま","72":"み","73":"む","74":"め","75":"も",
    "81":"や","82":"ゆ","83":"よ",
    "84":"ゃ","85":"ゅ","86":"ょ","87":"っ",
    "91":"ら","92":"り","93":"る","94":"れ","95":"ろ",
    "01":"わ","02":"を","03":"ん",
}
LEGACY_DAKUTEN = {
    "か":"が","き":"ぎ","く":"ぐ","け":"げ","こ":"ご",
    "さ":"ざ","し":"じ","す":"ず","せ":"ぜ","そ":"ぞ",
    "た":"だ","ち":"ぢ","つ":"づ","て":"で","と":"ど",
    "は":"ば","ひ":"び","ふ":"ぶ","へ":"べ","ほ":"ぼ",
    "う":"ゔ",
}
LEGACY_HANDAKUTEN = {"は":"ぱ","ひ":"ぴ","ふ":"ぷ","へ":"ぺ","ほ":"ぽ"}

FREEWORD_REV = {
    "01":"ワ","02":"ヲ","03":"ン",
    "11":"ア","12":"イ","13":"ウ","14":"エ","15":"オ","16":"A","17":"B","18":"C","19":"D","10":"E",
    "21":"カ","22":"キ","23":"ク","24":"ケ","25":"コ","26":"F","27":"G","28":"H","29":"I","20":"J",
    "31":"サ","32":"シ","33":"ス","34":"セ","35":"ソ","36":"K","37":"L","38":"M","39":"N","30":"O",
    "41":"タ","42":"チ","43":"ツ","44":"テ","45":"ト","46":"P","47":"Q","48":"R","49":"S","40":"T",
    "51":"ナ","52":"ニ","53":"ヌ","54":"ネ","55":"ノ","56":"U","57":"V","58":"W","59":"X","50":"Y",
    "61":"ハ","62":"ヒ","63":"フ","64":"ヘ","65":"ホ","66":"Z","67":"?","68":"!","69":"ー","60":"/",
    "71":"マ","72":"ミ","73":"ム","74":"メ","75":"モ","76":"*","77":"&",
    "81":"ヤ","82":"ユ","83":"ヨ","84":"ャ","85":"ュ","86":"ョ","87":"ッ","88":" ",
    "91":"ラ","92":"リ","93":"ル","94":"レ","95":"ロ",
    "00":"0","96":"1","97":"2","98":"3","99":"4","90":"5","06":"6","07":"7","08":"8","09":"9",
}
FREEWORD_DAKUTEN = {
    "カ":"ガ","キ":"ギ","ク":"グ","ケ":"ゲ","コ":"ゴ",
    "サ":"ザ","シ":"ジ","ス":"ズ","セ":"ゼ","ソ":"ゾ",
    "タ":"ダ","チ":"ヂ","ツ":"ヅ","テ":"デ","ト":"ド",
    "ハ":"バ","ヒ":"ビ","フ":"ブ","ヘ":"ベ","ホ":"ボ",
    "ウ":"ヴ",
}
FREEWORD_HANDAKUTEN = {"ハ":"パ","ヒ":"ピ","フ":"プ","ヘ":"ペ","ホ":"ポ"}

FIXED_MESSAGE_MAP = {
    "01":"キンキュウ",
    "02":"TELセヨ",
    "03":"スグカエレ",
    "04":"シュウゴウ",
    "05":"サキニイッテクダサイ",
    "06":"スグニイッテクダサイ",
    "07":"チュウシスル",
    "08":"ヘンコウスル",
    "09":"FAXセヨ",
    "10":"シジヲマテ",
    "11":"サキニイキマス",
    "12":"サキニカエリマス",
    "13":"オクレマス",
    "14":"キャクアリ",
    "15":"トラブル",
    "16":"ヨヤクOK",
    "17":"スグニイキマス",
    "18":"OK",
    "19":"NO",
    "20":"リョウカイ",
    "21":"カイシャニTELシテクダサイ",
    "22":"ルスバンデンワ",
    "23":"ジタクニTELシテクダサイ",
    "24":"イツモノトオリ",
    "25":"キテクダサイ",
    "26":"ゴメンナサイ",
    "27":"ヨテイ",
    "28":"アリガトウ",
    "29":"オツカレサマ",
    "30":"？",
}

clients = set()
state_lock = threading.Lock()
current_my_call = ""
loop_ref = None

def validate_seq(seq: str) -> str:
    seq = (seq or "").strip().upper()
    if not seq:
        raise ValueError("empty")
    if not _ALLOWED_TX.match(seq):
        raise ValueError("invalid chars")
    return seq

def decode_callsign(encoded: str) -> str:
    encoded = encoded or ""

    @lru_cache(maxsize=None)
    def expand(pos: int):
        if pos >= len(encoded):
            return {""}
        out = set()
        ch = encoded[pos]
        if ch.isdigit():
            for tail in expand(pos + 1):
                out.add(ch + tail)
        if pos + 3 <= len(encoded):
            token = encoded[pos:pos+3]
            if token in CALL_REV:
                for tail in expand(pos + 3):
                    out.add(CALL_REV[token] + tail)
        return out

    candidates = [c for c in expand(0) if c]
    if not candidates:
        return ""
    if "CQ" in candidates:
        return "CQ"

    def score(text: str):
        digit_count = sum(ch.isdigit() for ch in text)
        alpha_count = sum(ch.isalpha() for ch in text)
        jp_standard = bool(re.fullmatch(r"[A-Z]{2}\d[A-Z]{2,4}", text))
        jp_special = bool(re.fullmatch(r"\d[A-Z]\d[A-Z]{1,4}", text))
        jp_special_long = bool(re.fullmatch(r"\d[A-Z]{2}\d[A-Z]{1,4}", text))
        generic_call = bool(re.fullmatch(r"[A-Z0-9]{4,8}", text))
        mixed_like = bool(re.fullmatch(r"[A-Z]{1,3}\d[A-Z0-9]{1,4}", text))
        digits_only = text.isdigit()
        leading_digit = text[0].isdigit() if text else False
        return (
            0 if jp_standard else 1 if jp_special else 2 if jp_special_long else 3 if mixed_like else 4 if generic_call else 5 if digits_only else 6,
            abs(digit_count - (2 if leading_digit else 1)),
            -alpha_count,
            0 if 5 <= len(text) <= 8 else 1,
            abs(len(text) - 6),
            text,
        )

    return min(candidates, key=score)

def apply_mark(chars, mark: str, dakuten_map: dict, handakuten_map: dict):
    if not chars:
      return
    last = chars[-1]
    if mark == "04" and last in dakuten_map:
        chars[-1] = dakuten_map[last]
    elif mark == "05" and last in handakuten_map:
        chars[-1] = handakuten_map[last]

def decode_legacy_body(encoded: str) -> str:
    chars = []
    i = 0
    encoded = encoded or ""
    while i + 1 < len(encoded):
        token = encoded[i:i+2]
        if token in LEGACY_KANA_REV:
            chars.append(LEGACY_KANA_REV[token])
        elif token == "98" or token == "99":
            # v30 compatibility
            last = chars[-1] if chars else None
            if token == "98" and last in LEGACY_DAKUTEN:
                chars[-1] = LEGACY_DAKUTEN[last]
            elif token == "99" and last in LEGACY_HANDAKUTEN:
                chars[-1] = LEGACY_HANDAKUTEN[last]
        i += 2
    return "".join(chars)

def decode_freeword_body(encoded: str) -> str:
    chars = []
    i = 0
    encoded = encoded or ""
    while i + 1 < len(encoded):
        token = encoded[i:i+2]
        if token in FREEWORD_REV:
            chars.append(FREEWORD_REV[token])
        elif token == "04" or token == "05":
            apply_mark(chars, token, FREEWORD_DAKUTEN, FREEWORD_HANDAKUTEN)
        i += 2
    return "".join(chars)

def decode_payload(payload: str) -> str:
    payload = payload or ""
    if payload.startswith("*4*4"):
        code = payload[4:6]
        return FIXED_MESSAGE_MAP.get(code, payload[:6])
    if payload.startswith("*2*2"):
        return decode_freeword_body(payload[4:])
    return decode_legacy_body(payload)

def parse_document(doc: str):
    if not doc.startswith("*2*2"):
        return None
    body = doc[4:]
    parts = body.split("A0A")
    if len(parts) != 3:
        return None
    dest_call = decode_callsign(parts[0]) or "CQ"
    from_call = decode_callsign(parts[1])
    text = decode_payload(parts[2])
    if not text:
        return None
    with state_lock:
        my_call = current_my_call
    if dest_call != "CQ":
        if not my_call:
            return None
        if dest_call.upper() != my_call.upper():
            return None
    return {"from": from_call, "to": dest_call, "body": text}

async def broadcast(payload: dict):
    if not clients:
        return
    data = json.dumps(payload, ensure_ascii=False)
    dead = []
    for ws in list(clients):
        try:
            await ws.send(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        clients.discard(ws)

def start_rx_thread(in_dev: int, cfg: dtmf.DetectConfig):
    def runner():
        global loop_ref
        block_n = int(cfg.sample_rate * (cfg.block_ms / 1000.0))
        min_blocks = max(1, int(np.ceil(cfg.min_tone_ms / cfg.block_ms)))

        stable_digit = None
        stable_count = 0
        stream_buf = ""

        def cb(indata, frames, time_info, status):
            nonlocal stable_digit, stable_count, stream_buf
            x = indata[:, 0].copy()
            d = dtmf.detect_digit(x, cfg)

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
                stream_buf += d
                while "##" in stream_buf:
                    one, stream_buf = stream_buf.split("##", 1)
                    parsed = parse_document(one)
                    if parsed and loop_ref is not None:
                        asyncio.run_coroutine_threadsafe(
                            broadcast({"type": "rx_message", **parsed}),
                            loop_ref
                        )
                stable_digit = None
                stable_count = 0

        with sd.InputStream(
            device=in_dev,
            channels=1,
            samplerate=cfg.sample_rate,
            blocksize=block_n,
            dtype="float32",
            callback=cb
        ):
            while True:
                time.sleep(0.25)

    th = threading.Thread(target=runner, daemon=True)
    th.start()
    return th

async def run_server(host: str, port: int, out_dev: int, in_dev: int,
                     sr: int, tone_ms: int, gap_ms: int, com: Optional[str]):
    global loop_ref, current_my_call
    loop_ref = asyncio.get_running_loop()
    cfg = dtmf.DetectConfig(sample_rate=sr, block_ms=20, min_tone_ms=120, energy_floor=2e-5, ratio_thresh=3.0)
    start_rx_thread(in_dev, cfg)

    async def handler(ws):
        global current_my_call
        clients.add(ws)
        await ws.send(json.dumps({"type":"hello","status":"ok"}, ensure_ascii=False))
        try:
            async for msg in ws:
                data = json.loads(msg)
                mtype = data.get("type")
                if mtype == "tx":
                    seq = validate_seq(data.get("seq", ""))
                    await asyncio.to_thread(dtmf.do_tx, seq, out_dev, sr, tone_ms, gap_ms, com)
                    await ws.send(json.dumps({"type":"tx_done","seq":seq}, ensure_ascii=False))
                elif mtype == "set_my_call":
                    with state_lock:
                        current_my_call = (data.get("my_call") or "").strip().upper()
        finally:
            clients.discard(ws)

    async with websockets.serve(handler, host, port):
        await asyncio.Future()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--out", type=int, required=True)
    ap.add_argument("--in", dest="in_dev", type=int, required=True)
    ap.add_argument("--sr", type=int, default=8000)
    ap.add_argument("--tone-ms", type=int, default=130)
    ap.add_argument("--gap-ms", type=int, default=90)
    ap.add_argument("--com", type=str, default=None)
    args = ap.parse_args()
    asyncio.run(run_server(args.host, args.port, args.out, args.in_dev, args.sr, args.tone_ms, args.gap_ms, args.com))

if __name__ == "__main__":
    main()
