#!/usr/bin/env python3
"""
edhrec_usage_percent.py (v2)

- Scrapes EDHREC card page HTML and extracts:
    * edh_usage_pct   -> e.g., "0.09% of 6886184 decks"  => 0.09
    * edh_num_decks   -> e.g., "In 6365 decks"           => 6365
    * edh_total_decks -> e.g., "... of 6886184 decks"    => 6886184
- Sorts by edh_usage_pct (desc) by default.
- Marks top 10% by % and top 10% by numerator with boolean columns and a combined "highlight" column.

Usage:
  py -3.10 edhrec_usage_percent.py --in "Large Boxes.csv" --out ranked_usage.csv --flush_every 50 --sleep 0.2

Dependencies:
  pip install requests pandas beautifulsoup4
"""

import argparse
import json
import os
import re
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

import requests
import pandas as pd
from bs4 import BeautifulSoup

SCRYFALL_ID_URL = "https://api.scryfall.com/cards/{id}"
SCRYFALL_NAMED_URL = "https://api.scryfall.com/cards/named"
EDHREC_CARD_URL = "https://edhrec.com/cards/{slug}"

CACHE_DIR = ".cache"
os.makedirs(CACHE_DIR, exist_ok=True)

@dataclass
class CardRow:
    name: str
    set_code: Optional[str]
    qty: int
    scryfall_id: Optional[str]

@dataclass
class Enriched:
    name: str
    set_code: Optional[str]
    qty: int
    color_identity: str  # 'r', 'wubrg', 'colorless'
    edh_usage_pct: Optional[float]     # 0..100
    edh_usage_rate: Optional[float]    # 0..1
    edh_num_decks: Optional[int]       # numerator
    edh_total_decks: Optional[int]     # denominator
    notes: str

def log(msg: str, enabled: bool=True):
    if enabled:
        print(msg, flush=True)

def detect_columns(df: pd.DataFrame) -> Tuple[str, Optional[str], Optional[str], Optional[str]]:
    cols = {c.lower().strip(): c for c in df.columns}
    def pick(cands):
        for cand in cands:
            if cand.lower() in cols:
                return cols[cand.lower()]
        return None

    name_col = pick(["name","card","card name","card_name","Name","Card Name"])
    set_col  = pick(["set","set code","edition","set_code","Set code","Set"])
    qty_col  = pick(["qty","quantity","count","Quantity","Count"])
    sfid_col = pick(["scryfall id","scryfall_id","Scryfall ID"])

    if not name_col:
        raise ValueError("Couldn't detect a card name column. Include 'Name' or 'Card Name'.")
    return name_col, set_col, qty_col, sfid_col

def read_inventory(path: str, verbose: bool) -> List[CardRow]:
    encodings = ["utf-8-sig","latin-1"]
    df = None
    for enc in encodings:
        try:
            df = pd.read_csv(path, dtype=str, encoding=enc)
            break
        except Exception:
            continue
    if df is None:
        raise RuntimeError("Failed to read CSV; try saving as UTF-8.")
    name_col, set_col, qty_col, sfid_col = detect_columns(df)

    rows: List[CardRow] = []
    for _, r in df.iterrows():
        name = str(r[name_col]).strip() if pd.notna(r.get(name_col)) else ""
        if not name:
            continue
        set_code = None
        if set_col and pd.notna(r.get(set_col)):
            set_code = str(r[set_col]).strip() or None
        qty = 1
        if qty_col and pd.notna(r.get(qty_col)):
            try:
                qty = int(str(r[qty_col]).strip())
            except Exception:
                qty = 1
        scryfall_id = None
        if sfid_col and pd.notna(r.get(sfid_col)):
            sid = str(r[sfid_col]).strip()
            scryfall_id = sid if sid else None
        rows.append(CardRow(name=name, set_code=set_code, qty=qty, scryfall_id=scryfall_id))

    log(f"[load] Detected columns: name='{name_col}', set='{set_col}', qty='{qty_col}', scryfall_id='{sfid_col}'", verbose)
    log(f"[load] Loaded {len(rows)} rows from {path}", verbose)
    return rows

def slugify_card_name(name: str) -> str:
    slug = name.lower()
    replacements = {
        "'": "", ",": "", ":": "", ";": "", "—": "-", "–": "-",
        " // ": " ", "//": " ", "  ": " "
    }
    for a,b in replacements.items():
        slug = slug.replace(a,b)
    slug = "-".join(slug.strip().split())
    return slug

def cache_get(key: str) -> Optional[dict]:
    fp = os.path.join(CACHE_DIR, key + ".json")
    if os.path.exists(fp):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None

def cache_set(key: str, data: dict) -> None:
    fp = os.path.join(CACHE_DIR, key + ".json")
    try:
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass

def scryfall_get_by_id(sid: str) -> Optional[dict]:
    key = f"scry_{sid}"
    data = cache_get(key)
    if data is None:
        url = SCRYFALL_ID_URL.format(id=sid)
        r = requests.get(url, timeout=20)
        if r.status_code != 200:
            return None
        data = r.json()
        cache_set(key, data)
    return data

def scryfall_resolve(name: str, set_code: Optional[str]) -> Optional[dict]:
    params = {"exact": name}
    if set_code:
        params["set"] = set_code
    r = requests.get(SCRYFALL_NAMED_URL, params=params, timeout=20)
    if r.status_code == 200:
        return r.json()
    r = requests.get(SCRYFALL_NAMED_URL, params={"exact": name}, timeout=20)
    if r.status_code == 200:
        return r.json()
    r = requests.get(SCRYFALL_NAMED_URL, params={"fuzzy": name}, timeout=20)
    if r.status_code == 200:
        return r.json()
    return None

def parse_usage_from_html(html: str):
    """Return (pct, numerator, denominator) from EDHREC card page HTML."""
    soup = BeautifulSoup(html, "html.parser")

    # Grab all text nodes that mention "deck"
    texts = [t for t in soup.stripped_strings if "deck" in t.lower()]
    combined = " ".join(texts)

    pct = None
    num = None
    denom = None

    # Look for patterns like "0.09% of 6886184 decks"
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*%\s*of\s*([0-9,]+)\s*decks", combined, re.IGNORECASE)
    if m:
        try:
            pct = float(m.group(1))
        except:
            pass
        try:
            denom = int(m.group(2).replace(",", ""))
        except:
            pass

    # Look for patterns like "In 6365 decks"
    m2 = re.search(r"In\s+([0-9,]+)\s+decks", combined, re.IGNORECASE)
    if m2:
        try:
            num = int(m2.group(1).replace(",", ""))
        except:
            pass

    # Debug logging if nothing found
    if pct is None and num is None and denom is None:
        print("[debug] parse_usage_from_html failed. Snippet:", combined[:200])

    return pct, num, denom


def fetch_edhrec_usage(card_name: str, sleep: float, verbose: bool) -> Tuple[Optional[float], Optional[int], Optional[int]]:
    slug = slugify_card_name(card_name)
    key = f"card_html_{slug}"
    data = cache_get(key)
    html = None
    if data is None:
        url = EDHREC_CARD_URL.format(slug=slug)
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        log(f"[edhrec] GET {url}", verbose)
        r = requests.get(url, timeout=25, headers=headers)
        if r.status_code != 200:
            log(f"[edhrec] HTTP {r.status_code} for {card_name}", verbose)
            return None, None, None
        html = r.text
        cache_set(key, {"html": html})
        time.sleep(sleep)
    else:
        html = data.get("html")

    if not html:
        return None, None, None

    pct, num, denom = parse_usage_from_html(html)
    if pct is None and num is None and denom is None:
        log("  ! usage stats not found", verbose)
    return pct, num, denom

def to_row_dict(e: Enriched) -> dict:
    return {
        "name": e.name,
        "set": e.set_code,
        "qty": e.qty,
        "color_identity": e.color_identity,
        "edh_usage_pct": e.edh_usage_pct,
        "edh_usage_rate": e.edh_usage_rate,
        "edh_num_decks": e.edh_num_decks,
        "edh_total_decks": e.edh_total_decks,
        "top10_by_pct": e.notes.find("[TOP10_PCT]") != -1,
        "top10_by_num": e.notes.find("[TOP10_NUM]") != -1,
        "highlight": e.notes.find("[HIGHLIGHT]") != -1,
        "notes": e.notes.replace("[TOP10_PCT]","").replace("[TOP10_NUM]","").replace("[HIGHLIGHT]","").strip()
    }

def write_partial_csv(outp: str, rows: List[Enriched], sort: bool, verbose: bool):
    df = pd.DataFrame([to_row_dict(e) for e in rows])
    if sort and not df.empty:
        df = df.sort_values(by=["edh_usage_pct","edh_num_decks"], ascending=[False, False], na_position="last")
    df.to_csv(outp, index=False)
    log(f"[write] {len(df)} rows -> {outp}", verbose)

def main():
    ap = argparse.ArgumentParser(description="Rank cards by EDHREC usage (%, numerator, denominator). Marks top 10% by % and numerator.")
    ap.add_argument("--in", dest="inp", required=True, help="Input CSV")
    ap.add_argument("--out", dest="outp", required=True, help="Output ranked CSV")
    ap.add_argument("--sleep", type=float, default=0.2, help="Delay between web requests (seconds)")
    ap.add_argument("--flush_every", type=int, default=50, help="Write partial CSV every N cards processed (0=only at end)")
    ap.add_argument("--no_sort", action="store_true", help="Skip final sorting to save time")
    ap.add_argument("--quiet", action="store_true", help="Reduce console output")
    args = ap.parse_args()

    verbose = not args.quiet
    t0 = time.time()

    rows = read_inventory(args.inp, verbose)
    total_cards = len(rows)

    enriched: List[Enriched] = []
    processed = 0

    for row in rows:
        processed += 1
        log(f"\n[card {processed}/{total_cards}] {row.name} (set={row.set_code or '-'}, qty={row.qty})", verbose)

        notes = []
        # Resolve via Scryfall for canonical name & colors
        scry = None
        if row.scryfall_id:
            log(f"  - Scryfall by ID: {row.scryfall_id}", verbose)
            scry = scryfall_get_by_id(row.scryfall_id)
            if scry is None:
                notes.append("scryfall_id_lookup_failed")
        if scry is None:
            log(f"  - Scryfall resolve: name='{row.name}', set='{row.set_code or ''}'", verbose)
            scry = scryfall_resolve(row.name, row.set_code)
        if scry is None:
            log("  ! Scryfall resolution failed", verbose)
            enriched.append(Enriched(
                name=row.name, set_code=row.set_code, qty=row.qty,
                color_identity="unknown", edh_usage_pct=None, edh_usage_rate=None,
                edh_num_decks=None, edh_total_decks=None,
                notes="scryfall_resolve_failed"
            ))
            if args.flush_every and (processed % args.flush_every == 0):
                write_partial_csv(args.outp, enriched, sort=not args.no_sort, verbose=verbose)
            continue

        ci = "".join([c.lower() for c in (scry.get("color_identity") or [])]) or "colorless"
        log(f"  - color_identity: {ci}", verbose)

        pct, num, denom = fetch_edhrec_usage(scry.get("name", row.name), args.sleep, verbose)
        if pct is None:
            notes.append("no_edhrec_usage_pct")
            log("  ! edh_usage_pct not found", verbose)
        else:
            log(f"  - edh_usage_pct: {pct:.4f}%", verbose)
        if num is None:
            notes.append("no_edh_num_decks")
        else:
            log(f"  - edh_num_decks: {num}", verbose)
        if denom is None:
            notes.append("no_edh_total_decks")
        else:
            log(f"  - edh_total_decks: {denom}", verbose)

        rate = (pct/100.0) if pct is not None else None

        enriched.append(Enriched(
            name=scry.get("name", row.name),
            set_code=scry.get("set") or row.set_code,
            qty=row.qty,
            color_identity=ci,
            edh_usage_pct=pct,
            edh_usage_rate=rate,
            edh_num_decks=num,
            edh_total_decks=denom,
            notes=";".join(notes) if notes else ""
        ))

        if args.flush_every and (processed % args.flush_every == 0):
            write_partial_csv(args.outp, enriched, sort=not args.no_sort, verbose=verbose)

        time.sleep(args.sleep)

    # Compute top 10% flags
    df = pd.DataFrame([to_row_dict(e) for e in enriched])
    if not df.empty:
        # Calculate thresholds ignoring NaNs/None
        pct_thr = df['edh_usage_pct'].dropna().quantile(0.9) if df['edh_usage_pct'].notna().any() else None
        num_thr = df['edh_num_decks'].dropna().quantile(0.9) if df['edh_num_decks'].notna().any() else None
        for e in enriched:
            marks = []
            if pct_thr is not None and e.edh_usage_pct is not None and e.edh_usage_pct >= pct_thr:
                marks.append("[TOP10_PCT]")
            if num_thr is not None and e.edh_num_decks is not None and e.edh_num_decks >= num_thr:
                marks.append("[TOP10_NUM]")
            if marks:
                marks.append("[HIGHLIGHT]")
            if marks:
                e.notes = (e.notes + ";" if e.notes else "") + "".join(marks)

    # Final write
    df_final = pd.DataFrame([to_row_dict(e) for e in enriched])
    if not args.no_sort and not df_final.empty:
        df_final = df_final.sort_values(by=["edh_usage_pct","edh_num_decks"], ascending=[False, False], na_position="last")
    df_final.to_csv(args.outp, index=False)
    log(f"[write] {len(df_final)} rows -> {args.outp}", verbose)

    dt = time.time() - t0
    log(f"\n[done] Processed {len(enriched)} cards in {dt:.1f}s", verbose)

if __name__ == "__main__":
    main()
