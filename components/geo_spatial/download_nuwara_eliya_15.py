"""TravelMind Nuwara Eliya: shortlist 15 actual OSM records and download Commons candidates.

Run in the TravelMind project root:
    python -m pip install requests certifi
    python download_nuwara_eliya_15.py

All photos remain PENDING; this never edits config/attraction_image_final_review.csv.
"""
from __future__ import annotations

import csv
import html
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import certifi
import requests

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data/processed/travelmind_combined_clusters.csv"
OUT = ROOT / "config/photo_candidates"
PHOTOS = ROOT / "assets/images/attractions"
API = "https://commons.wikimedia.org/w/api.php"
HEADERS = {"User-Agent": "TravelMindEducationalPhotoResearch/1.0 (Wikimedia Commons attribution research; Python requests)"}

# Specific attraction IDs copied from the user's Nuwara Eliya dataset listing.
# These are editorial photo candidates, NOT an official popularity ranking.
TARGETS = [
    ("osm_way_493088634", "Hakgala Botanical Garden", "Hakgala Botanical Garden Sri Lanka"),
    ("osm_way_1196872351", "Lake Gregory Park", "Gregory Lake Nuwara Eliya"),
    ("osm_way_24390459", "Galway's Land National Park", "Galway's Land National Park Sri Lanka"),
    ("osm_node_4501771825", "Moon Plains", "Moon Plains Nuwara Eliya"),
    ("osm_node_1886592077", "Ramboda Falls", "Ramboda Falls Sri Lanka"),
    ("osm_node_247212347", "Devon Falls", "Devon Falls Sri Lanka"),
    ("osm_node_5809896557", "St. Clair Falls", "St Clair's Falls Sri Lanka"),
    ("osm_node_3833099699", "Bomburu Ella", "Bomburu Ella Sri Lanka"),
    ("osm_node_676861111", "Baker's Falls", "Bakers Falls Horton Plains"),
    ("osm_node_3254826636", "Lover's Leap Waterfall", "Lovers Leap Waterfall Nuwara Eliya"),
    ("osm_node_5413804743", "Aberdeen Waterfall", "Aberdeen Falls Sri Lanka"),
    ("osm_node_3207148721", "Laxapana Falls", "Laxapana Falls Sri Lanka"),
    ("osm_node_2714473161", "Seetha Amman Kovil", "Seetha Amman Temple Nuwara Eliya"),
    ("osm_node_4459218097", "Blue Fields Tea Factory", "Blue Field Tea Factory Ramboda"),
    ("osm_node_2035834190", "Pidurutalagala", "Pidurutalagala mountain Sri Lanka"),
]


def clean(value):
    return html.unescape(re.sub(r"<[^>]*>", " ", str(value or ""))).strip()


def metadata(info, key):
    return clean(info.get("extmetadata", {}).get(key, {}).get("value", ""))


def commons_candidates(session, search_text):
    params = {
        "action": "query", "format": "json", "formatversion": 2,
        "generator": "search", "gsrsearch": f'filetype:bitmap {search_text}',
        "gsrnamespace": 6, "gsrlimit": 15,
        "prop": "imageinfo", "iiprop": "url|mime|size|extmetadata",
        "iiurlwidth": 1600,
    }
    response = session.get(API, params=params, timeout=35, verify=certifi.where())
    response.raise_for_status()
    result = response.json()
    return result.get("query", {}).get("pages", [])


def candidate_score(page, main_name):
    # Names must refer to the same attraction, not just the same district.
    title = page.get("title", "").replace("File:", "").replace("_", " ").casefold()
    desc = metadata((page.get("imageinfo") or [{}])[0], "ImageDescription").casefold()
    aliases = {
        "Lake Gregory Park": ["gregory lake", "lake gregory"],
        "Galway's Land National Park": ["galway"],
        "St. Clair Falls": ["st. clair", "st clair", "saint clair"],
        "Baker's Falls": ["baker", "bakers"],
        "Lover's Leap Waterfall": ["lover's leap", "lovers leap", "lover leap"],
        "Aberdeen Waterfall": ["aberdeen"],
        "Laxapana Falls": ["laxapana", "lakshapana", "laksapana"],
        "Seetha Amman Kovil": ["seetha amman", "sita amman", "seetha kovil", "sita eliya"],
        "Blue Fields Tea Factory": ["blue field", "bluefield", "blue fields"],
        "Pidurutalagala": ["pidurutalagala", "mount pedro"],
        "Moon Plains": ["moon plains", "sandathenna"],
        "Hakgala Botanical Garden": ["hakgala"],
        "Ramboda Falls": ["ramboda fall"],
        "Devon Falls": ["devon fall"],
        "Bomburu Ella": ["bomburu"],
    }
    patterns = aliases.get(main_name, [main_name.casefold()])
    if any(a in title for a in patterns):
        return 4
    if any(a in desc for a in patterns):
        return 2
    return 0


def license_ok(info):
    # Only recognizable free-license/public-domain metadata are eligible for a *candidate* download.
    short = metadata(info, "LicenseShortName").casefold()
    license_url = metadata(info, "LicenseUrl")
    accepted = short.startswith("cc by") or short.startswith("cc0") or short in {
        "public domain", "pd", "public domain mark", "cc public domain mark 1.0"
    }
    return accepted, short, license_url


def main():
    if not DATA.is_file():
        sys.exit(f"Dataset not found: {DATA}\nRun this from your TravelMind project root.")
    OUT.mkdir(parents=True, exist_ok=True)
    PHOTOS.mkdir(parents=True, exist_ok=True)
    with DATA.open(encoding="utf-8-sig", newline="") as f:
        records = {r["attraction_id"].strip(): r for r in csv.DictReader(f)}
    missing = [ident for ident, _, _ in TARGETS if ident not in records]
    if missing:
        sys.exit(f"Safety check: attraction IDs missing from dataset: {missing}")
    for ident, title, _ in TARGETS:
        record = records[ident]
        if re.sub(r"[\W_]+", "", record.get("district", "").casefold()) != "nuwaraeliya":
            sys.exit(f"Safety check: {title} ({ident}) not in Nuwara Eliya district.")

    fields = ["attraction_id", "attraction_name", "tourism_category", "latitude", "longitude"]
    with (OUT / "nuwara_eliya_15_targets.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for ident, _, _ in TARGETS:
            writer.writerow({col: records[ident].get(col, "") for col in fields})

    report = []
    session = requests.Session()
    session.headers.update(HEADERS)
    count = 0
    for idx, (ident, label, search) in enumerate(TARGETS, 1):
        row = records[ident]
        item = {"attraction_id": ident, "attraction_name": row["attraction_name"],
                "district": row["district"], "image_file": "", "download_status": "",
                "creator": "", "license": "", "source_page": "", "license_url": "",
                "commons_title": "", "width": "", "height": "",
                "final_image_decision": "pending", "review_note": ""}
        print(f"[{idx}/15] {label}", flush=True)
        try:
            pages = commons_candidates(session, search)
            options = []
            for p in pages:
                infos = p.get("imageinfo") or []
                if not infos:
                    continue
                info = infos[0]
                mime = info.get("mime", "")
                if mime not in ("image/jpeg", "image/png", "image/webp"):
                    continue
                accepted, lic, lic_url = license_ok(info)
                if not accepted:
                    continue
                score = candidate_score(p, label)
                if score < 4:
                    continue  # Title must identify attraction; avoid generic images.
                url = info.get("thumburl") or info.get("url")
                if not url:
                    continue
                options.append((score, int(info.get("width") or 0), p, info, lic, lic_url, url))
            options.sort(key=lambda x: (x[0], min(x[1], 2500)), reverse=True)
            if not options:
                item["download_status"] = "NO_SAFE_CANDIDATE"
                item["review_note"] = "No clearly named, freely licensed Commons image found automatically. Manual review required."
            else:
                _, _, page, info, lic, lic_url, img_url = options[0]
                ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[info["mime"]]
                out_name = "nuwara_eliya_" + re.sub(r"[^a-z0-9]+", "_", label.casefold()).strip("_") + f".{ext}"
                dest = PHOTOS / out_name
                if dest.exists() and dest.stat().st_size > 0:
                    status = "EXISTS"
                else:
                    r = session.get(img_url, timeout=60, verify=certifi.where())
                    r.raise_for_status()
                    if not r.headers.get("content-type", "").startswith("image/"):
                        raise ValueError("Commons returned non-image content")
                    if len(r.content) < 5000:
                        raise ValueError("Image file unexpectedly small")
                    tmp = dest.with_suffix(dest.suffix + ".tmp")
                    tmp.write_bytes(r.content)
                    tmp.replace(dest)
                    status = "DOWNLOADED"
                item.update({"image_file": out_name, "download_status": status,
                             "creator": metadata(info, "Artist"),
                             "license": metadata(info, "LicenseShortName"),
                             "source_page": info.get("descriptionurl", ""),
                             "license_url": lic_url, "commons_title": page["title"],
                             "width": str(info.get("width", "")), "height": str(info.get("height", "")),
                             "review_note": "Check exact depicted location, creator, license, and source page before approving."})
                count += 1
                print(f"    {status}: {out_name}", flush=True)
        except (requests.RequestException, OSError, ValueError, KeyError) as exc:
            item["download_status"] = "ERROR"
            item["review_note"] = str(exc)[:250]
            print(f"    ERROR: {exc}", flush=True)
        report.append(item)
        time.sleep(0.3)

    review_path = OUT / "nuwara_eliya_download_review.csv"
    with review_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(report[0].keys()))
        writer.writeheader()
        writer.writerows(report)
    print(f"\nPhoto files downloaded or existing: {count}/15")
    print(f"Attraction shortlist: {OUT / 'nuwara_eliya_15_targets.csv'}")
    print(f"Review report: {review_path}")
    print("All files remain PENDING. Existing approved photo register was NOT modified.")


if __name__ == "__main__":
    main()
