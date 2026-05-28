"""
es_adapter.py — Elasticsearch state adapter for Pi Script governance.

Queries a live ES cluster, compares against a committed baseline, and writes
state.json for the Pi Script resolver to evaluate.

Usage:
    python es_adapter.py                        # normal run — compare against baseline
    python es_adapter.py --bootstrap            # record current mapping as known-good baseline
    python es_adapter.py --host http://...      # override default ES host
    python es_adapter.py --index my-index       # override default index name
"""

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_HOST  = "http://localhost:9200"
DEFAULT_INDEX = "governed-index"
BASELINE_PATH = Path(__file__).parent / "baseline.json"
STATE_PATH    = Path(__file__).parent / "state.json"


def fetch_json(url: str) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        print(f"[es_adapter] ERROR: could not reach ES at {url} — {e}")
        sys.exit(1)


def mapping_hash(host: str, index: str) -> str:
    data = fetch_json(f"{host}/{index}/_mapping")
    canonical = json.dumps(data, sort_keys=True)
    return hashlib.md5(canonical.encode()).hexdigest()


def replica_health(host: str, index: str) -> str:
    data = fetch_json(f"{host}/_cat/indices/{index}?h=health&format=json")
    if not data:
        return "degraded"
    raw = data[0].get("health", "red")
    return "healthy" if raw == "green" else "degraded"


def shards_synced(host: str, index: str) -> bool:
    data = fetch_json(f"{host}/_cat/shards/{index}?h=state&format=json")
    return bool(data) and all(s.get("state") == "STARTED" for s in data)


def bootstrap(host: str, index: str) -> None:
    h = mapping_hash(host, index)
    baseline = {
        "index":       index,
        "mapping_hash": h,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Baseline recorded after verified clean schema. "
            "Commit this file to lock the known-good state. "
            "Changing the baseline requires a deliberate commit — that is the audit trail."
        ),
    }
    BASELINE_PATH.write_text(json.dumps(baseline, indent=2))
    print(f"[es_adapter] Bootstrap complete. Baseline saved to {BASELINE_PATH}")
    print(f"[es_adapter] Mapping hash: {h}")
    print("[es_adapter] Commit baseline.json to git to activate governance.")


def run(host: str, index: str) -> None:
    if not BASELINE_PATH.exists():
        print("[es_adapter] ERROR: baseline.json not found. Run with --bootstrap first.")
        sys.exit(1)

    baseline = json.loads(BASELINE_PATH.read_text())
    expected_hash = baseline["mapping_hash"]

    current_hash = mapping_hash(host, index)
    health       = replica_health(host, index)
    synced       = shards_synced(host, index)

    schema_intact = current_hash == expected_hash

    if not schema_intact:
        print(f"[es_adapter] SCHEMA DRIFT DETECTED")
        print(f"[es_adapter]   expected: {expected_hash}")
        print(f"[es_adapter]   current:  {current_hash}")

    state = {
        "trigger_type": "event",
        "entity": "ElasticsearchIndex",
        "entity_state": {
            "schema_intact":  schema_intact,
            "replica_health": health,
            "shards_synced":  synced,
            "index_name":     index,
        },
    }

    STATE_PATH.write_text(json.dumps(state, indent=2))
    print(f"[es_adapter] State written to {STATE_PATH}")
    print(f"[es_adapter]   schema_intact:  {schema_intact}")
    print(f"[es_adapter]   replica_health: {health}")
    print(f"[es_adapter]   shards_synced:  {synced}")


def main() -> None:
    parser = argparse.ArgumentParser(description="ES state adapter for Pi Script governance")
    parser.add_argument("--bootstrap", action="store_true", help="Record current mapping as baseline")
    parser.add_argument("--host",  default=DEFAULT_HOST,  help="Elasticsearch host URL")
    parser.add_argument("--index", default=DEFAULT_INDEX, help="Index name to govern")
    args = parser.parse_args()

    if args.bootstrap:
        bootstrap(args.host, args.index)
    else:
        run(args.host, args.index)


if __name__ == "__main__":
    main()
