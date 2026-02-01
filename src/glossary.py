"""
Glossary utilities: load/save, parse user inputs, and infer terms from filenames.
"""

import json
import os
import re
from typing import Dict

_WORD_SPLIT_RE = re.compile(r"[^\w]+")
_CAMEL_SPLIT_RE = re.compile(r"(?<=[a-z])(?=[A-Z0-9])|(?<=[A-Z])(?=[A-Z][a-z])")


def load_glossary(path: str) -> Dict[str, str]:
    if not path or not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    if isinstance(data, dict):
        return {str(k): str(v) for k, v in data.items() if str(k).strip()}
    if isinstance(data, list):
        result = {}
        for item in data:
            if isinstance(item, dict):
                src = str(item.get("term", "")).strip()
                tgt = str(item.get("translation", "")).strip()
                if src:
                    result[src] = tgt or src
        return result
    return {}


def save_glossary(path: str, glossary: Dict[str, str]) -> None:
    if not path:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(glossary, f, ensure_ascii=False, indent=2)


def parse_glossary_text(text: str) -> Dict[str, str]:
    if not text:
        return {}
    result: Dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "->" in line:
            src, tgt = line.split("->", 1)
        elif "=" in line:
            src, tgt = line.split("=", 1)
        else:
            continue
        src = src.strip()
        tgt = tgt.strip()
        if src:
            result[src] = tgt or src
    return result


def parse_glossary_file(path: str) -> Dict[str, str]:
    if not path or not os.path.isfile(path):
        return {}
    ext = os.path.splitext(path)[1].lower()
    if ext in (".json", ".jsn"):
        return load_glossary(path)
    # CSV/TXT lines
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return parse_glossary_text(f.read())
    except Exception:
        return {}


def merge_glossaries(*glossaries: Dict[str, str]) -> Dict[str, str]:
    merged: Dict[str, str] = {}
    for glossary in glossaries:
        if not glossary:
            continue
        for term, translation in glossary.items():
            term = str(term).strip()
            if not term:
                continue
            merged[term] = str(translation).strip() or term
    return merged


def infer_glossary_from_filename(filename: str) -> Dict[str, str]:
    if not filename:
        return {}
    base = os.path.splitext(os.path.basename(filename))[0]
    tokens = []
    for chunk in _WORD_SPLIT_RE.split(base):
        if not chunk:
            continue
        parts = _CAMEL_SPLIT_RE.split(chunk)
        tokens.extend([p for p in parts if p])
    stop_words = {"final", "draft", "v1", "v2", "v3", "video", "audio", "sub", "subs"}
    glossary: Dict[str, str] = {}
    for token in tokens:
        clean = token.strip()
        if not clean:
            continue
        if clean.isdigit():
            continue
        if clean.lower() in stop_words:
            continue
        if len(clean) < 2:
            continue
        glossary[clean] = clean
    return glossary
