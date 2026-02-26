from __future__ import annotations

import math
import os
import re
from typing import List, Tuple


# def _db_filter_from_profile_id(profile_id: str):
#     """
#     New models.py: LovedOne has user FK.
#     Backward-compat: treat numeric profile_id as user_id; otherwise anonymous rows (user is NULL).
#     Returns: (django filter dict, rag_profile_key)
#     """
#     pid = (profile_id or "").strip()
#     if pid.isdigit():
#         return {"user_id": int(pid)}, pid
#     return {"user__isnull": True}, "default"


def _debug_enabled() -> bool:
    return os.getenv("VOICE_DEBUG", "0") == "1"


def _pcm16_stats_le(pcm_bytes: bytes) -> dict:
    if not pcm_bytes:
        return {"n": 0}

    n = len(pcm_bytes) // 2
    if n <= 0:
        return {"n": 0, "note": "odd_len"}

    mn = 32767
    mx = -32768
    s2 = 0.0

    step = max(1, n // 4000)
    count = 0

    for i in range(0, n, step):
        lo = pcm_bytes[2 * i]
        hi = pcm_bytes[2 * i + 1]
        v = (hi << 8) | lo
        if v >= 32768:
            v -= 65536

        mn = v if v < mn else mn
        mx = v if v > mx else mx
        s2 += float(v) * float(v)
        count += 1

    rms = math.sqrt(s2 / max(1, count))
    return {"n": n, "min": mn, "max": mx, "rms": round(rms, 2), "bytes": len(pcm_bytes), "step": step}


def _silence_pcm16(duration_sec: float, sample_rate: int = 24000) -> bytes:
    if duration_sec <= 0:
        return b""
    n_samples = int(sample_rate * duration_sec)
    if n_samples <= 0:
        return b""
    return b"\x00\x00" * n_samples


def _normalize_text_for_tts(t: str) -> str:
    t = (t or "").strip()
    if not t:
        return t
    t = t.replace("...", "…")
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"([.?!,;:])(?=\S)", r"\1 ", t)
    return t.strip()


def _chunk_text_for_cadence(text: str, max_words_per_chunk: int = 10) -> List[Tuple[str, float]]:
    t = _normalize_text_for_tts(text)
    if not t:
        return []

    parts: List[str] = []
    buf = ""
    for ch in t:
        buf += ch
        if ch in ".?!":
            parts.append(buf.strip())
            buf = ""
    if buf.strip():
        parts.append(buf.strip())

    out: List[Tuple[str, float]] = []

    def add(seg: str, pause: float):
        seg = (seg or "").strip()
        if seg:
            out.append((seg, pause))

    for sent in parts:
        sent = sent.strip()
        if not sent:
            continue

        phrases: List[str] = []
        pbuf = ""
        for ch in sent:
            pbuf += ch
            if ch in ",;:":
                phrases.append(pbuf.strip())
                pbuf = ""
        if pbuf.strip():
            phrases.append(pbuf.strip())

        for ph in phrases:
            words = ph.split()
            if len(words) <= max_words_per_chunk:
                end = ph[-1] if ph else ""
                if end in ",;:":
                    add(ph, 0.14)
                elif end in ".?!":
                    add(ph, 0.30)
                else:
                    add(ph, 0.18)
            else:
                for i in range(0, len(words), max_words_per_chunk):
                    seg = " ".join(words[i : i + max_words_per_chunk]).strip()
                    if i + max_words_per_chunk >= len(words):
                        if ph and ph[-1] in ".?!,;:" and seg and seg[-1] not in ".?!,;:":
                            seg = seg + ph[-1]
                    end = seg[-1] if seg else ""
                    if end in ",;:":
                        add(seg, 0.14)
                    elif end in ".?!":
                        add(seg, 0.30)
                    else:
                        add(seg, 0.16)

    if out:
        last_text, last_pause = out[-1]
        out[-1] = (last_text, min(last_pause, 0.22))

    return out
