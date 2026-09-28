"""
Prompt injection guard for untrusted catalog content.

The agent reads product descriptions from the catalog and feeds them into
the LLM context. That content is untrusted (it originates from seller
uploads, catalog syncs, or scraped data). This module applies a lightweight
pattern-based filter before the content reaches the model.

This is a defense-in-depth layer, not a complete solution. Production-grade
LLM serving should pair this with output validation and a dedicated
classifier. See docs/DECISIONS.md ADR-010.
"""
from __future__ import annotations

import re
from typing import Iterable

INJECTION_PATTERNS = (
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)", re.I),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|above)", re.I),
    re.compile(r"forget\s+(all\s+)?(previous|prior|your)\s+(instructions|rules)", re.I),
    re.compile(r"you\s+are\s+(now|no\s+longer)", re.I),
    re.compile(r"new\s+(instructions|system\s*prompt|persona)", re.I),
    re.compile(r"system\s*(prompt|message|role)", re.I),
    re.compile(r"<\s*/?\s*(system|assistant|user)\s*>", re.I),
    re.compile(r"\{\{\s*.*?\s*\}\}"),
    re.compile(r"<\s*script.*?>", re.I),
    re.compile(r"\{\s*\"role\"\s*:", re.I),
    re.compile(r"BEGIN\s+(SYSTEM|INSTRUCTIONS?)", re.I),
    re.compile(r"\[\s*INST\s*\]"),
    re.compile(r"<\|.*?\|>"),
)

SUSPICIOUS_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def is_suspicious(text: str) -> bool:
    """Return True if the text matches any known injection pattern."""
    if not text:
        return False
    for pat in INJECTION_PATTERNS:
        if pat.search(text):
            return True
    return bool(SUSPICIOUS_CHARS.search(text))


def sanitize(text: str, replacement: str = "[REDACTED: suspicious content removed]") -> str:
    """Replace the whole string if any injection pattern matches.

    Partial redaction is intentionally avoided: a partially-redacted string
    can still carry enough of the original instruction for the model to
    reconstruct it.
    """
    if not text:
        return text
    if is_suspicious(text):
        return replacement
    return SUSPICIOUS_CHARS.sub("", text)


def sanitize_chunks(chunks: Iterable) -> list:
    """Apply sanitize() to the .content of each RetrievedChunk-like object.

    Preserves the original objects; returns copies with sanitized content.
    """
    out = []
    for c in chunks:
        safe_content = sanitize(getattr(c, "content", "") or "")
        try:
            out.append(c.model_copy(update={"content": safe_content}))
        except AttributeError:
            out.append(c)
    return out
