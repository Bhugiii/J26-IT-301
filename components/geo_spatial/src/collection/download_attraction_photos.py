
"""
TravelMind - Automatic Attraction Photo Downloader

Searches Wikimedia Commons for candidate photographs of
100 Sri Lankan tourist attractions.

Outputs:
1. assets/images/attractions/*.jpg
2. config/attraction_image_candidates.csv

IMPORTANT:
- Downloaded images are NOT automatically approved.
- Visually review the photograph and its license.
- Only approved photographs should be shown as exact
  attraction images in the public tourist dashboard.
"""

from pathlib import Path
from html import unescape
import csv
import re
import time
import os

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ============================================================
# STEP 1 - PROJECT SETTINGS
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

IMAGE_DIR = ROOT / "assets" / "images" / "attractions"
CONFIG_DIR = ROOT / "config"

IMAGE_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_CSV = (
    CONFIG_DIR / "attraction_image_candidates.csv"
)

API_URL = "https://commons.wikimedia.org/w/api.php"

# Replace this with your contact email address or the URL
# of a Wikimedia user page you control.
#
# Wikimedia asks automated clients to identify themselves.
CONTACT = os.environ.get("TRAVELMIND_CONTACT", "").strip()

# Download a resized image suitable for web cards.
IMAGE_WIDTH = 1200

# Delay between attraction searches, in seconds.
REQUEST_DELAY = 1.5

# Set to 10 for an initial test.
# Change to 100 after testing the first 10.
MAX_ATTRACTIONS = 100


# ============================================================
# STEP 2 - 100 SRI LANKAN ATTRACTIONS
# ============================================================

ATTRACTIONS = [

    # 1. COLOMBO & WESTERN REGION
    "Gangaramaya Temple",
    "Galle Face Green",
    "Colombo National Museum",
    "Independence Memorial Hall Colombo",
    "Viharamahadevi Park",
    "Seema Malaka Temple",
    "Kelaniya Raja Maha Vihara",
    "Mount Lavinia Beach",
    "Negombo Beach",
    "Negombo Dutch Fort",

    # 2. KALUTARA & GALLE REGION
    "Kalutara Bodhiya",
    "Richmond Castle Kalutara",
    "Bentota Beach",
    "Brief Garden Bentota",
    "Kosgoda Turtle Conservation Project",
    "Hikkaduwa Beach",
    "Galle Fort",
    "Galle Lighthouse",
    "Unawatuna Beach",
    "Jungle Beach Unawatuna",

    # 3. MATARA & HAMBANTOTA REGION
    "Mirissa Beach",
    "Coconut Tree Hill Mirissa",
    "Weligama Beach",
    "Polhena Beach",
    "Dondra Head Lighthouse",
    "Hiriketiya Beach",
    "Hummanaya Blow Hole",
    "Tangalle Beach",
    "Yala National Park",
    "Bundala National Park",

    # 4. KANDY & MATALE REGION
    "Temple of the Tooth",
    "Royal Botanical Gardens Peradeniya",
    "Kandy Lake",
    "Bahirawakanda Vihara Buddha Statue",
    "Udawattakele Forest Reserve",
    "Ambuluwawa Tower",
    "Sigiriya Rock Fortress",
    "Pidurangala Rock",
    "Dambulla Cave Temple",
    "Aluvihare Rock Temple",

    # 5. NUWARA ELIYA & BADULLA REGION
    "Nine Arch Bridge Ella",
    "Ravana Falls",
    "Little Adam's Peak",
    "Ella Rock",
    "Diyaluma Falls",
    "Dunhinda Falls",
    "Horton Plains National Park",
    "World's End Horton Plains",
    "Gregory Lake",
    "Hakgala Botanical Garden",

    # 6. RATNAPURA & KEGALLE REGION
    "Sinharaja Forest Reserve",
    "Adam's Peak Sri Lanka",
    "Bopath Ella Falls",
    "Bambarakanda Falls",
    "Pinnawala Elephant Orphanage",
    "Pinnawala Open Zoo",
    "Belilena Cave",
    "Kitulgala",
    "Saman Devalaya Ratnapura",
    "Udawalawe National Park",

    # 7. ANURADHAPURA & POLONNARUWA
    "Ruwanwelisaya",
    "Jaya Sri Maha Bodhi",
    "Jetavanaramaya",
    "Abhayagiri Dagaba",
    "Isurumuniya Temple",
    "Mihintale",
    "Polonnaruwa Vatadage",
    "Gal Vihara Polonnaruwa",
    "Parakrama Samudra",
    "Medirigiriya Vatadage",

    # 8. NORTHERN SRI LANKA
    "Jaffna Fort",
    "Nallur Kandaswamy Temple",
    "Casuarina Beach Jaffna",
    "Keerimalai Sacred Water Springs",
    "Nagadeepa Purana Vihara",
    "Delft Island Sri Lanka",
    "Point Pedro Lighthouse",
    "Kandarodai Archaeological Site",
    "Mannar Fort",
    "Adam's Bridge Sri Lanka",

    # 9. EASTERN SRI LANKA
    "Koneswaram Temple",
    "Fort Frederick Trincomalee",
    "Nilaveli Beach",
    "Uppuveli Beach",
    "Pigeon Island National Park",
    "Pasikudah Beach",
    "Batticaloa Lighthouse",
    "Arugam Bay",
    "Muhudu Maha Viharaya",
    "Kumana National Park",

    # 10. NORTH-WEST & UVA REGION
    "Kalpitiya Beach",
    "Wilpattu National Park",
    "Munneswaram Temple",
    "Yapahuwa Rock Fortress",
    "Ridi Viharaya",
    "Panduwasnuwara Ancient Kingdom",
    "Maligawila Buddha Statue",
    "Buduruwagala Temple",
    "Lahugala Kitulana National Park",
    "Maduru Oya National Park",
]


# ============================================================
# STEP 3 - VALIDATE CONFIGURATION
# ============================================================

if len(ATTRACTIONS) != 100:
    raise ValueError(
        f"Expected 100 attractions, got {len(ATTRACTIONS)}"
    )

if len(set(ATTRACTIONS)) != 100:
    raise ValueError("Duplicate attraction names detected.")

if not CONTACT:
    raise ValueError(
        "Set TRAVELMIND_CONTACT to a contact email or Wikimedia user-page URL "
        "before running this script."
    )

if not 1 <= MAX_ATTRACTIONS <= len(ATTRACTIONS):
    raise ValueError(
        "MAX_ATTRACTIONS must be between 1 and 100."
    )


# ============================================================
# STEP 4 - CREATE HTTP SESSION
# ============================================================

session = requests.Session()

session.headers.update({
    "User-Agent": (
        f"TravelMindResearch/1.0 "
        f"(Sri Lanka educational tourism project; {CONTACT})"
    ),
    "Accept": "application/json",
})

retry_policy = Retry(
    total=3,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
    respect_retry_after_header=True,
)

adapter = HTTPAdapter(max_retries=retry_policy)

session.mount("https://", adapter)


# ============================================================
# STEP 5 - HELPERS
# ============================================================

def safe_filename(text):
    """Create a filesystem-safe image filename."""
    return re.sub(
        r"[^a-z0-9]+",
        "_",
        text.lower()
    ).strip("_")


def clean_metadata(value):
    """Remove basic HTML formatting from metadata text."""
    value = unescape(str(value or ""))
    return re.sub(r"<[^>]*>", "", value).strip()


def get_metadata_value(metadata, name):
    item = metadata.get(name, {})
    if isinstance(item, dict):
        return item.get("value", "")
    return ""


def allowed_license(license_name):
    """
    Accept common Commons reuse licenses.

    Actual license terms must still be reviewed.
    """
    name = license_name.strip().lower()

    return (
        name == "cc0"
        or name.startswith("cc0 ")
        or name in ["public domain", "pd"]
        or name.startswith("cc by ")
        or name.startswith("cc by-sa ")
    )


def read_existing_results():
    """Allow the downloader to resume previous work."""
    existing = {}

    if OUTPUT_CSV.exists():
        with open(
            OUTPUT_CSV,
            "r",
            encoding="utf-8-sig",
            newline=""
        ) as file:
            reader = csv.DictReader(file)

            for row in reader:
                name = row.get("attraction_name", "")
                if name:
                    existing[name] = row

    return existing


CSV_FIELDS = [
    "attraction_name",
    "image_file",
    "wikimedia_file_title",
    "source_page",
    "creator",
    "license",
    "license_url",
    "review_status",
]


def save_results(records):
    """Save metadata after each successful download."""
    with open(
        OUTPUT_CSV,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=CSV_FIELDS,
            extrasaction="ignore"
        )

        writer.writeheader()
        writer.writerows(records.values())


# ============================================================
# STEP 6 - SEARCH WIKIMEDIA COMMONS
# ============================================================

def search_commons(attraction_name):

    queries = [
        f'"{attraction_name}" Sri Lanka',
        f'"{attraction_name}"',
        f'{attraction_name} Sri Lanka',
    ]

    for search_query in queries:

        print(f"  Searching: {search_query}")

        parameters = {
            "action": "query",
            "generator": "search",
            "gsrsearch": search_query,
            "gsrnamespace": 6,
            "gsrlimit": 10,
            "prop": "imageinfo",
            "iiprop": "url|mime|extmetadata",
            "iiurlwidth": IMAGE_WIDTH,
            "format": "json",
            "formatversion": 2,
        }

        response = session.get(
            API_URL,
            params=parameters,
            timeout=40
        )

        response.raise_for_status()
        payload = response.json()

        if "error" in payload:
            raise RuntimeError(
                f"Wikimedia API error: {payload['error']}"
            )

        pages = payload.get(
            "query", {}
        ).get("pages", [])

        # Prefer files whose titles contain
        # more of the search terms.
        terms = [
            word.lower()
            for word in re.findall(
                r"[A-Za-z]+",
                attraction_name
            )
            if len(word) > 2
        ]

        pages = sorted(
            pages,
            key=lambda page: sum(
                word in page.get(
                    "title", ""
                ).lower()
                for word in terms
            ),
            reverse=True
        )

        for page in pages:

            infos = page.get("imageinfo", [])

            if not infos:
                continue

            info = infos[0]

            # Use JPEG only so saved files
            # have a reliable .jpg extension.
            if info.get("mime") != "image/jpeg":
                continue

            metadata = info.get(
                "extmetadata", {}
            )

            license_name = clean_metadata(
                get_metadata_value(
                    metadata,
                    "LicenseShortName"
                )
            )

            if not allowed_license(license_name):
                continue

            image_url = (
                info.get("thumburl")
                or info.get("url")
            )

            if not image_url:
                continue

            creator = clean_metadata(
                get_metadata_value(
                    metadata,
                    "Artist"
                )
            )

            license_url = get_metadata_value(
                metadata,
                "LicenseUrl"
            )

            return {
                "image_url": image_url,
                "wikimedia_file_title": page.get(
                    "title", ""
                ),
                "source_page": info.get(
                    "descriptionurl", ""
                ),
                "creator": creator,
                "license": license_name,
                "license_url": license_url,
            }

        time.sleep(REQUEST_DELAY)

    return None


# ============================================================
# STEP 7 - DOWNLOAD IMAGE
# ============================================================

def download_image(image_url, destination):

    with session.get(
        image_url,
        timeout=60,
        stream=True
    ) as response:

        response.raise_for_status()

        content_type = response.headers.get(
            "Content-Type", ""
        ).lower()

        if "image/jpeg" not in content_type:
            raise ValueError(
                f"Expected JPEG but received {content_type}"
            )

        temp_path = destination.with_suffix(".part")

        try:
            with open(temp_path, "wb") as file:
                for chunk in response.iter_content(
                    chunk_size=65536
                ):
                    if chunk:
                        file.write(chunk)

            # Verify JPEG signature.
            with open(temp_path, "rb") as file:
                signature = file.read(3)

            if signature != b"\xff\xd8\xff":
                raise ValueError(
                    "Downloaded file is not a valid JPEG."
                )

            temp_path.replace(destination)

        finally:
            if temp_path.exists():
                temp_path.unlink()


# ============================================================
# STEP 8 - MAIN DOWNLOADER
# ============================================================

def main():

    print("\n" + "=" * 65)
    print("TRAVELMIND - AUTOMATIC ATTRACTION PHOTO DOWNLOADER")
    print("=" * 65)

    print("Available attractions:", len(ATTRACTIONS))
    print("Attractions in this run:", MAX_ATTRACTIONS)

    existing_records = read_existing_results()

    successful = 0
    skipped = 0
    failed = 0

    selected_attractions = ATTRACTIONS[:MAX_ATTRACTIONS]

    for index, attraction_name in enumerate(
        selected_attractions,
        start=1
    ):

        print(
            f"\n[{index}/{len(selected_attractions)}] "
            f"{attraction_name}"
        )

        existing = existing_records.get(
            attraction_name
        )

        # Skip images that were already downloaded
        # and recorded in the metadata CSV.
        if existing:
            existing_file = (
                IMAGE_DIR / existing.get("image_file", "")
            )

            if (
                existing_file.is_file()
                and existing_file.suffix.lower() == ".jpg"
            ):
                print("  Already downloaded - skipping")
                skipped += 1
                continue

        try:
            candidate = search_commons(
                attraction_name
            )

            if candidate is None:
                print("  No suitable candidate found")
                failed += 1
                continue

            filename = (
                safe_filename(attraction_name)
                + ".jpg"
            )

            destination = IMAGE_DIR / filename

            print(
                "  Wikimedia file:",
                candidate["wikimedia_file_title"]
            )

            print("  Downloading photograph...")

            download_image(
                candidate["image_url"],
                destination
            )

            # Store all available attribution metadata.
            record = {
                "attraction_name": attraction_name,
                "image_file": filename,
                "wikimedia_file_title": candidate[
                    "wikimedia_file_title"
                ],
                "source_page": candidate[
                    "source_page"
                ],
                "creator": candidate[
                    "creator"
                ],
                "license": candidate[
                    "license"
                ],
                "license_url": candidate[
                    "license_url"
                ],
                "review_status": "needs_visual_review",
            }

            existing_records[
                attraction_name
            ] = record

            save_results(existing_records)

            print("  Saved:", destination)
            print("  License:", candidate["license"])
            print("  Status: needs_visual_review")

            successful += 1

        except (
            requests.RequestException,
            RuntimeError,
            ValueError,
            OSError
        ) as error:

            print("  Failed:", error)
            failed += 1

        time.sleep(REQUEST_DELAY)

    print("\n" + "=" * 65)
    print("TRAVELMIND DOWNLOAD SUMMARY")
    print("=" * 65)

    print("New images:", successful)
    print("Already downloaded:", skipped)
    print("Not downloaded / failed:", failed)

    print("\nImages folder:")
    print(IMAGE_DIR)

    print("\nImage metadata file:")
    print(OUTPUT_CSV)

    print(
        "\nIMPORTANT: Inspect the photographs before "
        "using them as exact attraction images."
    )

    print("\nDownloader completed.")


if __name__ == "__main__":
    main()
