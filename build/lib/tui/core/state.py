import json
from pathlib import Path
from ..config import STATE_FILE

def load_state():
    """Load state from file."""
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}

def save_state(state):
    """Save state to file."""
    try:
        STATE_FILE.write_text(json.dumps(state, indent=2))
    except Exception:
        pass
