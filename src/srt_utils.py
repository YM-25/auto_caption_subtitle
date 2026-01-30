"""
SRT parsing utilities for translating existing subtitle files.
"""

import re

_TIME_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})")


def timestamp_to_seconds(timestamp):
    match = _TIME_RE.match(timestamp.strip())
    if not match:
        return 0.0
    hours, minutes, seconds, millis = map(int, match.groups())
    return hours * 3600 + minutes * 60 + seconds + (millis / 1000.0)


def parse_srt_content(content):
    blocks = re.split(r"\n\s*\n", content.strip()) if content.strip() else []
    segments = []

    for block in blocks:
        lines = [line.rstrip() for line in block.splitlines() if line.strip() != ""]
        if len(lines) < 2:
            continue

        if "-->" in lines[0]:
            time_line = lines[0]
            text_lines = lines[1:]
        else:
            if len(lines) < 3:
                continue
            time_line = lines[1]
            text_lines = lines[2:]

        if "-->" not in time_line:
            continue

        start_str, end_str = [part.strip() for part in time_line.split("-->")]
        start = timestamp_to_seconds(start_str)
        end = timestamp_to_seconds(end_str)
        text = "\n".join(text_lines).strip()

        segments.append({"start": start, "end": end, "text": text, "lines": text_lines})

    return segments


def parse_srt_file(file_path):
    with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
        return parse_srt_content(file.read())


def detect_script(text):
    counts = {"han": 0, "kana": 0, "hangul": 0, "cyrillic": 0, "latin": 0}
    for char in text:
        code = ord(char)
        if 0x4E00 <= code <= 0x9FFF or 0x3400 <= code <= 0x4DBF:
            counts["han"] += 1
        elif 0x3040 <= code <= 0x30FF:
            counts["kana"] += 1
        elif 0xAC00 <= code <= 0xD7AF:
            counts["hangul"] += 1
        elif 0x0400 <= code <= 0x04FF:
            counts["cyrillic"] += 1
        elif (0x41 <= code <= 0x5A) or (0x61 <= code <= 0x7A):
            counts["latin"] += 1

    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else "unknown"


def detect_bilingual_segments(segments, threshold=0.6):
    if not segments:
        return False
    bilingual_hits = 0
    total = 0
    for seg in segments:
        lines = seg.get("lines") or []
        if len(lines) < 2:
            continue
        first_line = lines[0]
        last_line = lines[-1]
        if not first_line or not last_line:
            continue
        script_a = detect_script(first_line)
        script_b = detect_script(last_line)
        total += 1
        if script_a != "unknown" and script_b != "unknown" and script_a != script_b:
            bilingual_hits += 1

    if total == 0:
        return False
    return (bilingual_hits / total) >= threshold


def extract_source_segments(segments, bilingual=False):
    source_segments = []
    for seg in segments:
        lines = seg.get("lines") or []
        if bilingual and len(lines) >= 2:
            source_text = lines[-1].strip()
        else:
            source_text = seg.get("text", "").strip()
        source_segments.append({"start": seg["start"], "end": seg["end"], "text": source_text})
    return source_segments


def detect_language_from_text(text):
    script = detect_script(text)
    if script == "kana":
        return "ja"
    if script == "hangul":
        return "ko"
    if script == "han":
        return "zh-CN"
    if script == "cyrillic":
        return "ru"
    if script == "latin":
        return "en"
    return ""
