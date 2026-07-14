"""Parse EventHttpUpload bodies from Dahua ACS panels.

ASI1212 often sends Content-Encoding: deflate and a semicolon-separated
text form (Code=...;action=...;data={...}) instead of JSON. Native HA
webhook handlers must decode and normalize that payload.
"""

from __future__ import annotations

import json
import zlib
from typing import Any


def decode_body(raw: bytes, encoding: str | None) -> bytes:
    """Decompress body if Content-Encoding is gzip/deflate."""
    enc = (encoding or "").lower().strip()
    if not enc:
        return raw
    if enc == "gzip":
        return zlib.decompress(raw, zlib.MAX_WBITS | 16)
    if enc == "deflate":
        # Already plain text/JSON
        if raw.lstrip()[:1] in (b"{", b"C"):
            return raw
        for wbits in (zlib.MAX_WBITS, -zlib.MAX_WBITS, zlib.MAX_WBITS | 16):
            try:
                return zlib.decompress(raw, wbits)
            except zlib.error:
                continue
        raise ValueError("deflate decompress failed")
    return raw


def parse_dahua_event_text(text: str) -> dict[str, Any]:
    """Parse Code=AccessControl;action=Pulse;data={...} from Dahua HTTP upload."""
    out: dict[str, Any] = {}
    data_blob = ""
    if ";data=" in text:
        text, data_blob = text.split(";data=", 1)
    for part in text.split(";"):
        if "=" in part:
            key, value = part.split("=", 1)
            out[key.strip()] = value.strip()
    if data_blob:
        try:
            out["Data"] = json.loads(data_blob)
        except json.JSONDecodeError:
            out["Data"] = data_blob
    if "action" in out and "Action" not in out:
        out["Action"] = out.pop("action")
    if "index" in out and "Index" not in out:
        try:
            out["Index"] = int(out.pop("index") or 0)
        except ValueError:
            out["Index"] = out.pop("index")
    return out


def parse_webhook_body(
    raw: bytes,
    *,
    content_encoding: str | None = None,
    content_type: str = "",
) -> dict[str, Any]:
    """Decode and parse a Dahua EventHttpUpload POST body into a dict."""
    try:
        body = decode_body(raw, content_encoding)
    except ValueError:
        body = raw

    text = body.decode("utf-8", errors="replace").strip()
    if not text:
        return {"raw": ""}

    if text.startswith("{"):
        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                return payload
            return {"raw": text[:500], "parsed": payload}
        except json.JSONDecodeError:
            return {"raw": text[:500]}

    # Semicolon form or unknown text
    if "Code=" in text or "code=" in text or ";data=" in text.lower():
        return parse_dahua_event_text(text)

    if "json" in (content_type or "").lower():
        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass

    return {"raw": text[:500]}
