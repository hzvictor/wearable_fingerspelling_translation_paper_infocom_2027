"""Firebase Firestore sync — no login, free Spark tier, stdlib-only (urllib).

Ported from finger/tapstrap/sync_firebase.py but using urllib instead of requests
so the packaged app needs zero third-party HTTP deps. Each trial -> one Firestore
doc (raw_data gzip+base64 in `raw_gz`); plus a session meta doc and a subject doc.
Local-first + idempotent via the .synced.json manifest. Open "test mode" rules.

Config: ~/Library/Application Support/ASLCollector/firebase_config.json
  {"projectId": "...", "apiKey": "...", "collector": "yourname"}
"""
from __future__ import annotations
import base64
import gzip
import json
import urllib.parse
import urllib.request
import urllib.error

from core.paths import config_path, manifest_path, sessions_dir, session_root

FINGER_NAMES = ["thumb", "index", "middle", "ring", "pinky"]


# ---------------------------------------------------------------------------
# config + manifest
# ---------------------------------------------------------------------------

def load_config() -> dict | None:
    p = config_path()
    if not p.exists():
        return None
    try:
        cfg = json.loads(p.read_text())
    except Exception:
        return None
    if not cfg.get("projectId") or not cfg.get("collector"):
        return None
    return cfg


def _load_manifest() -> dict:
    p = manifest_path()
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return {}
    return {}


def _save_manifest(m: dict) -> None:
    tmp = manifest_path().with_suffix(".json.tmp")
    tmp.write_text(json.dumps(m, indent=2))
    tmp.replace(manifest_path())


# ---------------------------------------------------------------------------
# Firestore REST (urllib)
# ---------------------------------------------------------------------------

def _fv(v):
    if isinstance(v, bool):
        return {"booleanValue": v}
    if isinstance(v, int):
        return {"integerValue": str(v)}
    if isinstance(v, float):
        return {"doubleValue": v}
    if isinstance(v, str):
        return {"stringValue": v}
    if isinstance(v, list):
        return {"arrayValue": {"values": [_fv(x) for x in v]}}
    if v is None:
        return {"nullValue": None}
    return {"stringValue": json.dumps(v, ensure_ascii=False)}


def _request(method, url, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, r.read()


def firestore_put(cfg, collection, doc_id, fields):
    project, api_key = cfg["projectId"], cfg.get("apiKey", "")
    doc_q = urllib.parse.quote(doc_id, safe="")
    base = f"https://firestore.googleapis.com/v1/projects/{project}/databases/(default)/documents"
    url = f"{base}/{collection}?documentId={doc_q}"
    if api_key:
        url += f"&key={api_key}"
    body = {"fields": {k: _fv(v) for k, v in fields.items()}}
    try:
        _request("POST", url, body)
    except urllib.error.HTTPError as e:
        if e.code == 409:   # exists -> PATCH overwrite
            purl = f"{base}/{collection}/{doc_q}" + (f"?key={api_key}" if api_key else "")
            _request("PATCH", purl, body)
        else:
            raise


# ---------------------------------------------------------------------------
# upload helpers
# ---------------------------------------------------------------------------

def _gz_b64(obj) -> str:
    raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    return base64.b64encode(gzip.compress(raw, 6)).decode("ascii")


def _fingers_of(raw_data) -> list[str]:
    seen = set()
    for m in raw_data:
        if m.get("type") == "accl":
            pl = m.get("payload", [])
            for i in range(min(5, len(pl) // 3)):
                if any(pl[i * 3:i * 3 + 3]):
                    seen.add(i)
    return [FINGER_NAMES[i] for i in sorted(seen)]


def sync_subject(cfg, subject: dict):
    firestore_put(cfg, "subjects", f"{cfg['collector']}__{subject['id']}", {
        "subject_id": subject["id"],
        "collector": cfg["collector"],
        "display_name": subject.get("display_name", ""),
        "dominant_hand": subject.get("dominant_hand", ""),
        "age_range": subject.get("age_range", ""),
        "consent_at": subject.get("consent_at") or 0.0,
    })


def sync_session_dir(cfg, session_id: str, manifest: dict) -> bool:
    """Upload one session's meta + trials to Firestore if changed. Returns True if uploaded."""
    root = session_root(session_id)
    meta_p = root / "meta.json"
    trial_files = sorted(root.glob("trial_*.json"))
    # key the manifest on (#trials, meta mtime) so re-runs after adding trials re-sync
    sig = (len(trial_files), meta_p.stat().st_mtime if meta_p.exists() else 0)
    if manifest.get(session_id, {}).get("sig") == list(sig):
        return False

    collector = cfg["collector"]
    for tp in trial_files:
        t = json.loads(tp.read_text())
        raw = t.get("raw_data", [])
        channels = max((len(m.get("payload", [])) for m in raw if m.get("type") == "accl"),
                       default=0)
        idx = int(tp.stem.split("_")[-1])
        firestore_put(cfg, "trials", f"{collector}__{session_id}__t{idx:03d}", {
            "session_id": session_id, "collector": collector,
            "word": t.get("word", ""), "letters": t.get("letters", []),
            "num_letters": t.get("num_letters", 0), "group": t.get("group", ""),
            "trial": t.get("trial", idx), "timestamp": t.get("timestamp", 0.0),
            "num_accl": t.get("num_accl", 0), "num_imu": t.get("num_imu", 0),
            "channels": channels, "fingers": _fingers_of(raw),
            "raw_gz": _gz_b64(raw),
        })
    if meta_p.exists():
        meta = json.loads(meta_p.read_text())
        firestore_put(cfg, "sessions", f"{collector}__{session_id}", {
            "session_id": session_id, "collector": collector,
            "subject_id": meta.get("subject_id", ""),
            "protocol_id": meta.get("protocol_id", ""),
            "protocol_name": meta.get("protocol_name", ""),
            "max_accl_channels": meta.get("max_accl_channels", 0),
            "total_trials": len(trial_files),
            "started_at": meta.get("started_at", 0.0),
        })
    manifest[session_id] = {"sig": list(sig)}
    return True


def sync_all() -> int:
    """Upload every changed session. Returns count uploaded. No-op if no config."""
    cfg = load_config()
    if not cfg:
        return 0
    manifest = _load_manifest()
    d = sessions_dir()
    ids = sorted([p.name for p in d.iterdir() if p.is_dir()]) if d.exists() else []
    uploaded = 0
    for sid in ids:
        try:
            if sync_session_dir(cfg, sid, manifest):
                uploaded += 1
        except Exception:
            pass  # silent: local is source of truth, retry next time
    _save_manifest(manifest)
    return uploaded
