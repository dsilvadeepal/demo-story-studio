import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
def test_inventory_covers_five_pages():
    p = ROOT / 'contracts/dashboard-inventory.json'
    assert p.exists(), 'Missing inventory'
    inv = json.loads(p.read_text())
    assert {x['page'] for x in inv} == {'executive', 'pipeline', 'detail', 'trend', 'breakdown'}
    source = json.loads((ROOT/'dashboard-discovery-complete.json').read_text())
    for domain in ['Sales', 'Service']:
        expected = {(p['name'],w['id']) for p in source[domain]['pages'] for w in p['widgets']}
        actual = {(x['source_page_id'],x['source_widget_id']) for x in inv if x['dashboard']==domain.lower()}
        assert actual == expected
    assert all(x['metric_ids'] or x['excluded_reason'] for x in inv)
