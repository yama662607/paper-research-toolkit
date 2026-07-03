#!/usr/bin/env python3
"""
Save a paper and its PDF to Zotero via the local Connector HTTP API.

Workflow:
  1) POST /connector/saveItems
  2) obtain PDF bytes (from --pdf-file, or download --pdf-url)
  3) POST /connector/saveAttachment
  4) verify via local /api read endpoint

PDF source (choose exactly one):
  --pdf-file <path>   Attach a local PDF (preferred for paywalled / EZproxy /
                      Cloudflare-protected papers: fetch the bytes with the
                      *authenticated browser* via playwright-extension, save to a
                      temp file, then pass it here). Uses no network of its own.
  --pdf-url  <url>    Download the PDF with urllib (only works for openly
                      reachable PDFs, e.g. Open Access / arXiv / direct links —
                      no cookies, no auth, cannot pass Cloudflare/EZproxy).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import string
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit


class ConnectorError(RuntimeError):
    """Raised when connector operations fail with a terminal error."""


def random_id(prefix: str, length: int = 12) -> str:
    suffix = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(length))
    return f"{prefix}-{int(time.time())}-{suffix}"


def post_json(url: str, payload: dict, timeout: float = 30.0) -> tuple[int, str]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Content-Length", str(len(data)))
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8", errors="ignore")


def post_binary(url: str, body: bytes, metadata: dict, timeout: float = 60.0) -> tuple[int, str]:
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/pdf")
    req.add_header("Content-Length", str(len(body)))
    req.add_header("X-Metadata", json.dumps(metadata))
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8", errors="ignore")


def get_json(url: str, timeout: float = 20.0):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download_pdf(url: str, timeout: float = 60.0) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read()


def read_pdf_file(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


def looks_like_pdf(data: bytes) -> bool:
    # Guard against saving an HTML error / login / Cloudflare page as a PDF.
    head = data[:1024].lstrip()
    return head[:5] == b"%PDF-"


def obtain_pdf_bytes(args: argparse.Namespace) -> bytes:
    """Return PDF bytes from a local file (preferred) or a URL download."""
    if args.pdf_file:
        data = read_pdf_file(args.pdf_file)
        if not looks_like_pdf(data):
            raise ConnectorError(
                f"--pdf-file does not look like a PDF (magic bytes mismatch): {args.pdf_file}"
            )
        return data
    data = download_pdf(args.pdf_url, timeout=args.pdf_timeout)
    if not looks_like_pdf(data):
        # Most common cause: paywall / Cloudflare / login HTML returned for a
        # paywalled URL. Signal the caller to retry via the authenticated browser.
        raise ConnectorError(
            "downloaded content is not a PDF (likely paywall/Cloudflare/login page). "
            "Fetch via the authenticated browser (playwright-extension) and pass --pdf-file."
        )
    return data


def find_parent_item(items, title: str, doi: str | None):
    if not isinstance(items, list):
        return None
    for item in items:
        if not isinstance(item, dict):
            continue
        data = item.get("data", {})
        if data.get("itemType") != "journalArticle":
            continue
        if data.get("title") != title:
            continue
        if doi is not None and data.get("DOI") != doi:
            continue
        return item
    return None


def find_attachment_key_from_parent_item(parent_item: dict) -> str | None:
    link = parent_item.get("links", {}).get("attachment", {}).get("href")
    if not link:
        return None
    parts = link.rstrip("/").split("/")
    if parts[-1] == "file" and len(parts) >= 2:
        return parts[-2]
    return parts[-1]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Save a paper+PDF to local Zotero via Connector API.")
    p.add_argument("--article-url", required=True)
    p.add_argument("--article-title", required=True)
    p.add_argument("--pdf-url", default="", help="Publicly reachable PDF URL (urllib download; OA only)")
    p.add_argument("--pdf-file", default="", help="Local PDF path (preferred for paywalled/EZproxy; from authenticated browser)")
    p.add_argument("--doi", default="", help="Optional DOI")
    p.add_argument("--connector-base", default="http://127.0.0.1:23119")
    p.add_argument("--connector-timeout", type=float, default=30.0)
    p.add_argument("--pdf-timeout", type=float, default=60.0)
    p.add_argument("--verify-timeout", type=float, default=20.0)
    p.add_argument("--verify-limit", type=int, default=20)
    p.add_argument("--verify-retries", type=int, default=5)
    p.add_argument("--poll-interval", type=float, default=1.0)
    p.add_argument("--saveitems-retries", type=int, default=2)
    p.add_argument("--saveitems-retry-delay", type=float, default=1.0)
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args()
    if bool(args.pdf_file) == bool(args.pdf_url):
        p.error("provide exactly one of --pdf-file or --pdf-url")
    return args


def post_json_with_retry(
    url: str,
    payload: dict,
    retries: int,
    timeout: float,
    retry_delay: float,
    operation: str,
    retriable_statuses: tuple[int, ...] = (429, 500, 502, 503, 504),
) -> tuple[int, str]:
    attempt = 0
    while True:
        try:
            status, body = post_json(url, payload, timeout=timeout)
            if status < 400:
                return status, body
            if status in retriable_statuses and attempt < retries:
                attempt += 1
                time.sleep(retry_delay * attempt)
                continue
            raise ConnectorError(f"{operation} failed after {attempt + 1} attempts: HTTP {status}")
        except urllib.error.HTTPError as exc:
            if getattr(exc, "code", None) in retriable_statuses and attempt < retries:
                attempt += 1
                time.sleep(retry_delay * attempt)
                continue
            raise ConnectorError(f"{operation} failed after {attempt + 1} attempts: HTTP {getattr(exc,'code',None)}") from exc
        except urllib.error.URLError as exc:
            if attempt < retries:
                attempt += 1
                time.sleep(retry_delay * attempt)
                continue
            raise ConnectorError(f"{operation} failed after {attempt + 1} attempts: {exc}") from exc


def main() -> int:
    args = parse_args()
    if not args.doi:
        args.doi = None

    session_id = random_id("session")
    connector_item_id = random_id("item", 10)

    payload = {
        "sessionID": session_id,
        "uri": args.article_url,
        "items": [
            {
                "id": connector_item_id,
                "itemType": "journalArticle",
                "title": args.article_title,
            }
        ],
    }
    if args.doi:
        payload["items"][0]["DOI"] = args.doi
    save_items_url = f"{args.connector_base.rstrip('/')}/connector/saveItems"

    try:
        status, _ = post_json_with_retry(
            save_items_url,
            payload,
            retries=args.saveitems_retries,
            timeout=args.connector_timeout,
            retry_delay=args.saveitems_retry_delay,
            operation="saveItems",
        )
    except ConnectorError as exc:
        print(f"saveItems failed: {exc}", file=sys.stderr)
        return 1
    if status != 201:
        print(f"saveItems failed: status {status}", file=sys.stderr)
        return 1

    try:
        pdf_data = obtain_pdf_bytes(args)
    except ConnectorError as exc:
        # return 2 = "PDF unreachable, retry via authenticated browser (--pdf-file)"
        print(f"PDF acquisition failed: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"PDF acquisition failed: {exc}", file=sys.stderr)
        return 2

    src_name = args.pdf_file or args.pdf_url
    pdf_name = os.path.basename(urlsplit(src_name).path) or os.path.basename(src_name) or "paper.pdf"
    if not pdf_name.lower().endswith(".pdf"):
        pdf_name += ".pdf"
    save_attachment_url = f"{args.connector_base.rstrip('/')}/connector/saveAttachment"
    metadata = {
        "sessionID": session_id,
        "parentItemID": connector_item_id,
        "title": pdf_name,
        "url": args.article_url,
    }
    try:
        status2, _ = post_binary(save_attachment_url, pdf_data, metadata, timeout=args.pdf_timeout)
    except urllib.error.HTTPError as exc:
        print(f"saveAttachment failed: HTTP {exc.code}", file=sys.stderr)
        return 1
    if status2 not in (200, 201):
        print(f"saveAttachment failed: status {status2}", file=sys.stderr)
        return 1

    # Verify created items.
    parent_key = None
    attachment_key = None
    try:
        verify_retries = int(args.verify_retries)
        verify_interval = float(args.poll_interval)
    except (TypeError, ValueError):
        print("Invalid verify parameters.", file=sys.stderr)
        return 1
    if verify_retries < 0 or verify_interval < 0:
        print("Invalid verify parameters.", file=sys.stderr)
        return 1

    for _ in range(verify_retries + 1):
        try:
            items = get_json(
                f"{args.connector_base.rstrip('/')}/api/users/0/items?sort=dateAdded&direction=desc&limit={args.verify_limit}",
                timeout=args.verify_timeout,
            )
        except Exception:
            items = []
            time.sleep(verify_interval)
            continue

        parent_item = find_parent_item(items, args.article_title, args.doi)
        if parent_item:
            parent_key = parent_item.get("key")
            attachment_key = find_attachment_key_from_parent_item(parent_item)
            break
        time.sleep(verify_interval)

    out = {
        "status": "success" if parent_key else "warning",
        "session_id": session_id,
        "connector_item_id": connector_item_id,
        "parent_key": parent_key,
        "attachment_key": attachment_key,
        "pdf_source": "file" if args.pdf_file else "url",
    }

    if args.quiet:
        print(json.dumps(out))
    else:
        print(json.dumps(out, indent=2))

    if not parent_key:
        print("Verification warning: parent item not found in recent items.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
