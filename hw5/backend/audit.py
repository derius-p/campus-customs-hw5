"""Audit trail: every agent-loop step is appended to output/audit_trail.json as it happens.

The file is a JSON list that only grows. Earlier runs are never wiped (each record carries its run_id
and ticket_id, so runs can be told apart). Each write goes to a temp file first and is then swapped
in, so a crash mid-write can't leave a half-written file.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from backend.models import AgentEvent

AUDIT_PATH = Path(__file__).resolve().parents[1] / "output" / "audit_trail.json"
_lock = threading.Lock()


def read_audit(path: Path = AUDIT_PATH) -> list[dict]:
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path} should hold a JSON list of audit records")
    return data


def append_event(event: AgentEvent, path: Path = AUDIT_PATH) -> None:
    """Listener for RunState: add one event to the end of the audit trail."""
    with _lock:
        records = read_audit(path)
        records.append(event.model_dump(mode="json", exclude_none=True))
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, path)
