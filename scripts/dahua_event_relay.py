#!/usr/bin/env python3
"""Relay Dahua EventHttpUpload POSTs to Home Assistant webhook.

Dahua may send Content-Encoding: deflate; HA webhook cannot decode it.
This relay decompresses the body and forwards plain JSON to HA.

Usage:
  DAHUA_HA_WEBHOOK=http://192.168.1.11:8123/api/webhook/dahua_acs_events \
    python3 dahua_event_relay.py --port 8818
"""

from __future__ import annotations

import argparse
import json
import sys
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import URLError
from urllib.request import Request, urlopen

HA_WEBHOOK_DEFAULT = "http://192.168.1.11:8123/api/webhook/dahua_acs_events"


def parse_dahua_event_text(text: str) -> dict:
    """Parse Code=AccessControl;action=Pulse;data={...} from Dahua HTTP upload."""
    out: dict = {}
    data_blob = ""
    if ";data=" in text:
        text, data_blob = text.split(";data=", 1)
    for part in text.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    if data_blob:
        try:
            out["Data"] = json.loads(data_blob)
        except json.JSONDecodeError:
            out["Data"] = data_blob
    if "action" in out and "Action" not in out:
        out["Action"] = out.pop("action")
    if "index" in out and "Index" not in out:
        out["Index"] = int(out.pop("index") or 0)
    return out


def decode_body(raw: bytes, encoding: str | None) -> bytes:
    enc = (encoding or "").lower().strip()
    if not enc:
        return raw
    if enc == "gzip":
        return zlib.decompress(raw, zlib.MAX_WBITS | 16)
    if enc == "deflate":
        if raw.lstrip()[:1] in (b"{", b"C"):
            return raw
        for wbits in (zlib.MAX_WBITS, -zlib.MAX_WBITS, zlib.MAX_WBITS | 16):
            try:
                return zlib.decompress(raw, wbits)
            except zlib.error:
                continue
        raise ValueError("deflate decompress failed")
    return raw


class DahuaRelayHandler(BaseHTTPRequestHandler):
    ha_webhook: str = HA_WEBHOOK_DEFAULT

    def log_message(self, fmt: str, *args) -> None:
        print(f"[relay] {self.address_string()} - {fmt % args}", flush=True)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b""
        enc = self.headers.get("Content-Encoding")
        try:
            body = decode_body(raw, enc)
            text = body.decode("utf-8", errors="replace").strip()
            print(f"[relay] {self.path} enc={enc!r} len={len(raw)} -> {text[:500]}", flush=True)
            if text and not text.startswith("{"):
                payload = parse_dahua_event_text(text)
                body = json.dumps(payload).encode("utf-8")
                content_type = "application/json"
            else:
                content_type = self.headers.get("Content-Type", "application/json")
            req = Request(
                self.ha_webhook,
                data=body,
                headers={"Content-Type": content_type},
                method="POST",
            )
            with urlopen(req, timeout=10) as resp:
                ha_body = resp.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
            print(f"[relay] -> HA {resp.status} {ha_body!r}", flush=True)
        except URLError as exc:
            print(f"[relay] HA forward error: {exc}", file=sys.stderr, flush=True)
            self.send_response(502)
            self.end_headers()
        except Exception as exc:
            print(f"[relay] error: {exc}", file=sys.stderr, flush=True)
            self.send_response(400)
            self.end_headers()

    def do_GET(self) -> None:
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")


def main() -> int:
    parser = argparse.ArgumentParser(description="Dahua EventHttpUpload -> HA webhook relay")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8818)
    parser.add_argument("--ha-webhook", default=HA_WEBHOOK_DEFAULT)
    args = parser.parse_args()

    handler = type("H", (DahuaRelayHandler,), {"ha_webhook": args.ha_webhook})
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Listening on {args.host}:{args.port} -> {args.ha_webhook}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
