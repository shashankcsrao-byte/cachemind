"""JSON-file persistence (the Python stand-in for LocalStorage)."""
import json
import os
from pathlib import Path

# "file" keeps data in a JSON file next to the app (single user, local use).
# "session" keeps it in the browser session only, so visitors of a shared
# deployment never see or reset each other's data.
STORAGE_MODE = os.environ.get("CACHEMIND_STORAGE", "file").strip().lower()
if STORAGE_MODE not in ("file", "session"):
    raise RuntimeError(f"CACHEMIND_STORAGE must be 'file' or 'session', got '{STORAGE_MODE}'.")

DATA_FILE = Path(__file__).with_name("cachemind_data.json")
MAX_HISTORY = 200
DEFAULT = {"configs": [], "sequences": [], "history": [], "scores": []}


def load(path=DATA_FILE):
    try:
        data = json.loads(Path(path).read_text())
    except FileNotFoundError:
        return {k: list(v) for k, v in DEFAULT.items()}
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(f"Could not read saved data at {path}: {exc}") from exc
    return {k: list(data.get(k, [])) for k in DEFAULT}


def save(data, path=DATA_FILE):
    Path(path).write_text(json.dumps(data, indent=2))


def append(data, key, item, limit=MAX_HISTORY):
    """Return a new data dict with item appended to data[key]."""
    return {**data, key: (data[key] + [item])[-limit:]}


def remove(data, key, index):
    return {**data, key: data[key][:index] + data[key][index + 1:]}


def cleared(key=None, data=None):
    if key is None:
        return {k: [] for k in DEFAULT}
    return {**data, key: []}
