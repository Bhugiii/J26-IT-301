"""Patch TravelMind searches to match district OR attraction name, without touching photos."""
from pathlib import Path
from datetime import datetime
import shutil
import re
import pandas as pd

ROOT = Path(__file__).resolve().parent
APP = ROOT / 'src/dashboard/app.py'
HOME = ROOT / 'src/dashboard/tm_home_dashboard.py'
REG = ROOT / 'config/attraction_image_final_review.csv'
DATA = ROOT / 'data/processed/travelmind_combined_clusters.csv'
IMG = ROOT / 'assets/images/attractions'


def replace_file(path, replacements):
    if not path.exists():
        print(f'MISSING: {path}')
        return 0
    original = path.read_text(encoding='utf-8-sig')
    modified = original
    total = 0
    for label, pattern, replacement in replacements:
        modified, count = re.subn(pattern, replacement, modified)
        if count:
            print(f'  {label}: {count} edit(s)')
            total += count
    if modified == original:
        print(f'  No matching search pattern in {path.name}; file left unchanged.')
        return 0
    compile(modified, str(path), 'exec')
    backup = path.with_name(path.stem + '_before_district_search_' + datetime.now().strftime('%Y%m%d_%H%M%S') + path.suffix)
    shutil.copy2(path, backup)
    path.write_text(modified, encoding='utf-8')
    print(f'  Updated: {path}\n  Backup: {backup}')
    return total


print('PATCHING MAIN GIS FILTER')
# Works with the one-line syntax from the uploaded Group Menu upgrade.
app_count = replace_file(APP, [(
    'Search by district or attraction name',
    r'(?m)^(\s*)if search\.strip\(\):\s*filtered\s*=\s*filtered\[filtered\.attraction_name\.str\.contains\(search\.strip\(\),\s*case=False,\s*regex=False,\s*na=False\)\]',
    r'\1if search.strip():\n\1    matched_name = filtered.attraction_name.str.contains(search.strip(), case=False, regex=False, na=False)\n\1    matched_district = filtered.district.str.contains(search.strip(), case=False, regex=False, na=False)\n\1    filtered = filtered[matched_name | matched_district]',
)])

print('\nPATCHING DASHBOARD SEARCH')
# Current dashboard search searches attraction_name; include the district as well.
home_count = replace_file(HOME, [(
    'Homepage search by district or attraction',
    r'(?P<frame>\b\w+)\.attraction_name\.str\.contains\(query\.strip\(\),\s*case=False,\s*regex=False,\s*na=False\)',
    lambda m: '(' + m.group('frame') + '.attraction_name.str.contains(query.strip(), case=False, regex=False, na=False) | ' + m.group('frame') + '.district.str.contains(query.strip(), case=False, regex=False, na=False))',
)])

print('\nKANDY PHOTO REGISTER CHECK')
if DATA.exists() and REG.exists():
    d = pd.read_csv(DATA, low_memory=False, dtype={'attraction_id':'str'})
    r = pd.read_csv(REG, dtype=str).fillna('')
    ids = set(d.loc[d.district.astype(str).str.strip().str.casefold().eq('kandy'), 'attraction_id'].astype(str))
    approved = r[r.final_image_decision.astype(str).str.strip().str.casefold().eq('approved')]
    kandy = approved[approved.attraction_id.astype(str).isin(ids)]
    present = kandy[kandy.image_file.map(lambda x: bool(x) and (IMG / x).is_file())]
    print(f'Kandy dataset records: {len(ids)}')
    print(f'Kandy approved register entries: {len(kandy)}')
    print(f'Kandy approved files found on disk: {len(present)}')
    if kandy.empty:
        print('ACTION: Kandy approval script may not have run. Check the earlier approval output.')
    elif present.empty:
        print('ACTION: Photos are approved but missing from assets/images/attractions.')
    else:
        print('Photo register appears usable; search filtering was likely hiding results.')
else:
    print('Could not check photo register or dataset; missing one of the local CSV files.')

print('\nFinished. Restart Streamlit or refresh the page.')
