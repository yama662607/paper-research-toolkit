#!/usr/bin/env python3
"""
Resolve an Open-Access PDF URL for a DOI via Unpaywall.

Prefer OA before touching EZproxy: OA papers download with no login and no
Cloudflare friction, so this makes the common case fast and reliable.

Usage:
  resolve_oa_pdf.py --doi 10.1103/PhysRevX.13.041043 [--email you@kyoto-u.ac.jp]

Email: Unpaywall requires a contact email (not an API key). Pass --email or set
UNPAYWALL_EMAIL. Any valid mailbox works.

Output (JSON on stdout):
  {"doi": "...", "is_oa": true, "pdf_url": "https://...", "host_type": "publisher|repository", "version": "publishedVersion"}
Exit codes: 0 = OA PDF found, 3 = no OA PDF (fall back to authenticated browser), 1 = error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


def fetch_unpaywall(doi: str, email: str, timeout: float = 20.0) -> dict:
    doi = doi.strip().removeprefix("https://doi.org/").removeprefix("doi:").strip()
    url = f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi)}?email={urllib.parse.quote(email)}"
    req = urllib.request.Request(url, headers={"User-Agent": "paper-research-toolkit/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def best_oa_pdf(record: dict) -> dict | None:
    # Prefer the record's own best_oa_location, then scan all locations for a PDF.
    candidates = []
    best = record.get("best_oa_location")
    if isinstance(best, dict):
        candidates.append(best)
    locs = record.get("oa_locations")
    if isinstance(locs, list):
        candidates.extend(x for x in locs if isinstance(x, dict))
    for loc in candidates:
        pdf = loc.get("url_for_pdf") or (loc.get("url") if str(loc.get("url", "")).lower().endswith(".pdf") else None)
        if pdf:
            return {
                "pdf_url": pdf,
                "host_type": loc.get("host_type"),
                "version": loc.get("version"),
            }
    return None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Resolve an OA PDF URL for a DOI via Unpaywall.")
    p.add_argument("--doi", required=True)
    p.add_argument("--email", default=os.environ.get("UNPAYWALL_EMAIL", ""))
    p.add_argument("--timeout", type=float, default=20.0)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if not args.email:
        print("error: provide --email or set UNPAYWALL_EMAIL (Unpaywall requires a contact email).", file=sys.stderr)
        return 1
    try:
        record = fetch_unpaywall(args.doi, args.email, timeout=args.timeout)
    except urllib.error.HTTPError as exc:
        if getattr(exc, "code", None) == 404:
            print(json.dumps({"doi": args.doi, "is_oa": False, "pdf_url": None, "note": "not in Unpaywall"}))
            return 3
        print(f"error: Unpaywall HTTP {getattr(exc,'code',None)}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    hit = best_oa_pdf(record) if record.get("is_oa") else None
    out = {
        "doi": args.doi,
        "is_oa": bool(record.get("is_oa")),
        "pdf_url": hit["pdf_url"] if hit else None,
        "host_type": hit["host_type"] if hit else None,
        "version": hit["version"] if hit else None,
    }
    print(json.dumps(out))
    return 0 if hit else 3


if __name__ == "__main__":
    raise SystemExit(main())
