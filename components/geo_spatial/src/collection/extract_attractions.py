"""Extract named Sri Lankan tourism features from an offline Geofabrik OSM PBF.

Run from project root:
    python src/collection/extract_attractions.py
    python src/collection/extract_attractions.py --limit 100

Requires: python -m pip install osmium
Source: © OpenStreetMap contributors (ODbL). No Google Places API used.
"""
import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import osmium

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PBF = ROOT / 'data' / 'raw' / 'sri-lanka-latest.osm.pbf'
DEFAULT_OUTPUT = ROOT / 'data' / 'processed' / 'travelmind_attractions.csv'
CSV_CONFIG = ROOT / 'config' / 'csv_columns.json'

# Tourism features, excluding generic stores, housing, hotels and restaurants.
# OSM tagging is not exhaustive; inspect and validate your output before research use.
CATEGORY_RULES = [
    ('tourism', 'museum', 'Museums'),
    ('tourism', 'gallery', 'Museums'),
    ('tourism', 'zoo', 'Wildlife'),
    ('tourism', 'aquarium', 'Wildlife'),
    ('tourism', 'viewpoint', 'Scenic viewpoints'),
    ('tourism', 'attraction', 'Tourist attractions'),
    ('tourism', 'theme_park', 'Parks'),
    ('tourism', 'artwork', 'Cultural heritage'),
    ('tourism', 'picnic_site', 'Nature'),
    ('historic', 'archaeological_site', 'Archaeological sites'),
    ('historic', 'ruins', 'Ancient ruins'),
    ('historic', 'castle', 'Forts and heritage'),
    ('historic', 'fort', 'Forts and heritage'),
    ('historic', 'monument', 'Historical landmarks'),
    ('historic', 'memorial', 'Historical landmarks'),
    ('historic', 'temple', 'Temples'),
    ('historic', 'yes', 'Historical landmarks'),
    ('natural', 'beach', 'Beaches'),
    ('natural', 'waterfall', 'Waterfalls'),
    ('natural', 'peak', 'Mountains'),
    ('natural', 'cave_entrance', 'Caves'),
    ('natural', 'spring', 'Nature'),
    ('leisure', 'nature_reserve', 'Nature reserves'),
    ('leisure', 'park', 'Parks'),
    ('leisure', 'garden', 'Gardens'),
    ('leisure', 'wildlife_hide', 'Wildlife'),
    ('boundary', 'national_park', 'National parks'),
    ('amenity', 'place_of_worship', 'Religious sites'),
]


def category_for(tags):
    # Check distinctive name/attributes, then thematic OSM tags.
    if tags.get('waterway') == 'waterfall':
        return 'Waterfalls'
    if tags.get('religion') == 'buddhist' and tags.get('amenity') == 'place_of_worship':
        return 'Temples'
    for key, value, category in CATEGORY_RULES:
        if tags.get(key) == value:
            return category
    return None

def in_sri_lanka(lat, lon):
    # Broad safety check only, not a district or national boundary check.
    return 5.8 <= lat <= 9.9 and 79.5 <= lon <= 82.1


class Extractor(osmium.SimpleHandler):
    def __init__(self, columns, limit=None):
        super().__init__()
        self.columns = columns
        self.limit = limit
        self.items = {}
        self.invalid_geometries = 0
        self.now = datetime.now(timezone.utc).date().isoformat()

    def _add(self, osm_type, osm_id, tags, lat, lon):
        name = tags.get('name:en') or tags.get('name')
        category = category_for(tags)
        if not name or not category or not in_sri_lanka(lat, lon):
            return
        key = f'{osm_type}/{osm_id}'
        if key in self.items:
            return
        osm_url = f'https://www.openstreetmap.org/{osm_type}/{osm_id}'
        row = dict.fromkeys(self.columns, '')
        row.update({
            'attraction_id': f'osm_{osm_type}_{osm_id}',
            'attraction_name': name.strip(),
            'tourism_category': category,
            'latitude': round(lat, 7),
            'longitude': round(lon, 7),
            'formatted_address': ', '.join(filter(None, [
                tags.get('addr:street'), tags.get('addr:city'), tags.get('addr:postcode')
            ])),
            'source': 'OpenStreetMap / Geofabrik',
            'source_url': osm_url,
            'last_verified_date': self.now,
            'opening_hours': tags.get('opening_hours', ''),
            'description': tags.get('description:en') or tags.get('description', ''),
        })
        # district, province, area_id deliberately blank until verified with GIS polygons.
        # Other research/model fields are not available from the PBF.
        self.items[key] = row
        if self.limit is not None and len(self.items) >= self.limit:
            raise StopExtraction()

    def node(self, node):
        tags = dict(node.tags)
        if not category_for(tags) or not (tags.get('name:en') or tags.get('name')):
            return
        if node.location.valid():
            self._add('node', node.id, tags, node.location.lat, node.location.lon)

    def way(self, way):
        tags = dict(way.tags)
        if not category_for(tags) or not (tags.get('name:en') or tags.get('name')):
            return
        # Approximate representative point: average of valid way vertices.
        # This is not a polygon centroid; may lie outside concave polygons.
        coords = [(nd.location.lat, nd.location.lon) for nd in way.nodes if nd.location.valid()]
        if not coords:
            self.invalid_geometries += 1
            return
        lat = sum(x for x, _ in coords) / len(coords)
        lon = sum(y for _, y in coords) / len(coords)
        self._add('way', way.id, tags, lat, lon)


class StopExtraction(Exception):
    pass


def main():
    parser = argparse.ArgumentParser(description='TravelMind offline OSM attraction CSV extractor')
    parser.add_argument('--input', type=Path, default=DEFAULT_PBF)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--limit', type=int, default=None, help='Optional number of features for a quick test')
    args = parser.parse_args()
    if not args.input.is_file():
        parser.error(f'PBF not found: {args.input}. Place the downloaded file in data/raw/.')
    if args.limit is not None and args.limit < 1:
        parser.error('--limit must be greater than 0')
    columns = json.loads(CSV_CONFIG.read_text(encoding='utf-8'))
    if not isinstance(columns, list):
        parser.error('config/csv_columns.json must contain a JSON array')
    extractor = Extractor(columns, args.limit)
    print(f'Reading PBF: {args.input}', flush=True)
    try:
        extractor.apply_file(str(args.input), locations=True, idx='flex_mem')
    except StopExtraction:
        pass
    except Exception as exc:
        parser.exit(1, f'Failed to read PBF: {exc}\n')
    if not extractor.items:
        print('No named attractions found. CSV not overwritten.')
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(sorted(extractor.items.values(), key=lambda row: row['attraction_name'].casefold()))
    print(f'Saved {len(extractor.items)} named OSM attractions to {args.output}')
    print('District and province fields are blank until verified against district boundary polygons.')
    print('Coverage: named OSM nodes and ways only; OSM relations are not included.')
    print('Way coordinates are approximate points, not verified entrances or polygon centroids.')
    print('Source: © OpenStreetMap contributors (ODbL). Attribute OSM in research outputs.')


if __name__ == '__main__':
    main()
