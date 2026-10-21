"""Approve checked Matara photos without overwriting TravelMind's existing register.

Place this script in the TravelMind project root and run:
    python approve_matara_photos_one_step.py

Six vetted candidate rows are eligible; the Dondra Point candidate is held because
its Commons page is for a Buddha statue, not an identifiable Dondra Point view.
"""
from __future__ import annotations

import csv
import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / "config/photo_candidates/matara_download_review.csv"
REGISTER = ROOT / "config/attraction_image_final_review.csv"
IMAGE_DIR = ROOT / "assets/images/attractions"
BACKUPS = ROOT / "config/backups"

# Exact Matara attraction IDs from the uploaded dataset; Dondra held for review.
APPROVABLE_IDS = {
    "osm_node_5764539554",  # Coconut Tree Hill
    "osm_way_573467082",    # Secret Beach
    "osm_way_497744372",    # Madiha Beach
    "osm_node_11595481269", # Blue Beach Island
    "osm_way_1166309032",  # Weherahena Viharaya
    "osm_way_496970157",   # Dutch Church
}
HELD_IDS = {"osm_node_6620896189": "Commons photo shows a Buddha statue at Dondra, not clearly Dondra Point"}
LICENSES = {"CC BY 2.0", "CC BY-SA 3.0", "CC BY-SA 4.0"}
REQUIRED = {"attraction_id", "image_file", "final_image_decision"}


def read_csv(path: Path):
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"Missing CSV header: {path}")
        return list(reader), list(reader.fieldnames)


def valid_https(url: str, host: str) -> bool:
    parsed = urlparse(str(url).strip())
    return parsed.scheme == "https" and parsed.hostname == host


def main():
    if not REPORT.is_file():
        raise FileNotFoundError(f"Missing download report: {REPORT}")
    if not REGISTER.is_file():
        raise FileNotFoundError(f"Missing current approval register: {REGISTER}")

    reports, report_cols = read_csv(REPORT)
    original, columns = read_csv(REGISTER)
    if not REQUIRED.issubset(columns):
        raise ValueError(f"Register missing columns: {sorted(REQUIRED - set(columns))}")
    if not {"attraction_id", "download_status", "image_file", "creator", "license", "license_url", "source_page"}.issubset(report_cols):
        raise ValueError("Download report is missing required metadata columns")

    known_ids = {r["attraction_id"].strip() for r in original}
    new_rows = []
    seen = set()
    skipped = []
    issues = []
    for r in reports:
        aid = r["attraction_id"].strip()
        if aid in HELD_IDS:
            skipped.append(f"{r.get('attraction_name', aid)}: HELD — {HELD_IDS[aid]}")
            continue
        if aid not in APPROVABLE_IDS:
            continue
        if aid in seen:
            issues.append(f"Duplicate candidate ID: {aid}")
            continue
        seen.add(aid)
        if aid in known_ids:
            skipped.append(f"{r.get('attraction_name', aid)}: already in existing register (not overwritten)")
            continue
        fname = r["image_file"].strip()
        if r["download_status"].strip() != "DOWNLOADED_PENDING_VISUAL_REVIEW":
            issues.append(f"{aid}: image not downloaded")
            continue
        if not fname or fname != Path(fname).name or not re.fullmatch(r"[\w.-]+\.(jpg|jpeg|png|webp)", fname, re.I):
            issues.append(f"{aid}: invalid image filename")
            continue
        if not (IMAGE_DIR / fname).is_file() or (IMAGE_DIR / fname).stat().st_size < 1000:
            issues.append(f"{aid}: missing or unexpectedly small image file: {fname}")
            continue
        if not r["creator"].strip() or r["license"].strip() not in LICENSES:
            issues.append(f"{aid}: missing creator or unsupported license")
            continue
        if not valid_https(r["source_page"], "commons.wikimedia.org") or not valid_https(r["license_url"], "creativecommons.org"):
            issues.append(f"{aid}: invalid Commons source or Creative Commons license URL")
            continue
        row = {c: "" for c in columns}
        for c in columns:
            if c in r:
                row[c] = r[c]
        row["attraction_id"] = aid
        row["image_file"] = fname
        row["final_image_decision"] = "approved"
        new_rows.append(row)

    print(f"Existing register records: {len(original)}")
    print(f"New eligible Matara photos: {len(new_rows)}")
    for line in skipped:
        print("  SKIP:", line)
    if issues:
        print("\nVALIDATION FAILED — no files changed:")
        for line in issues:
            print(" -", line)
        raise SystemExit(1)
    if not new_rows:
        print("Nothing new to approve. Your register is unchanged.")
        return

    print("\nPlease confirm you personally reviewed the images and the Commons file/license pages.")
    if input("Type APPROVE to update the register: ").strip() != "APPROVE":
        print("Cancelled. No files changed.")
        return

    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup = BACKUPS / f"attraction_image_final_review_before_matara_{stamp}.csv"
    shutil.copy2(REGISTER, backup)

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8-sig", newline="", dir=REGISTER.parent,
                                         prefix="matara_register_", suffix=".tmp", delete=False) as out:
            temp_path = Path(out.name)
            writer = csv.DictWriter(out, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(original + new_rows)
        os.replace(temp_path, REGISTER)
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()

    print(f"\nAPPROVED: {len(new_rows)} new Matara photos")
    print(f"Total register records: {len(original) + len(new_rows)}")
    print(f"Backup: {backup}")
    print(f"Updated: {REGISTER}")
    print("Dondra Point is still pending. All previous rows preserved.")


if __name__ == "__main__":
    main()
