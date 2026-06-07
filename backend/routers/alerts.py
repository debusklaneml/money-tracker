"""Alerts router — list, run detection, and dismiss/acknowledge alerts.

``backend.main`` mounts this under the ``/api`` prefix, so routes here are
declared without it. Any monetary values inside ``metadata`` are milliunits.

Endpoints:

* ``GET /alerts`` lists persisted alerts via :meth:`Database.get_alerts`.
* ``POST /alerts/run`` runs every registered detector
  (:meth:`AlertRegistry.run_all`) and persists the results with
  :func:`save_alerts_to_db`, which dedupes against existing non-dismissed alerts.
  Mirrors the legacy ``pages/6_Alerts.py`` flow. Returns how many *new* alerts
  were saved (an int >= 0; zero is normal on minimal data).
* ``POST /alerts/{alert_id}/dismiss`` and ``/acknowledge`` wrap the matching DB
  methods. Those methods issue a bare UPDATE and do not report whether the id
  existed, so these endpoints are best-effort: they always return a 200
  ``MessageResponse`` even if ``alert_id`` matched no row.

Metadata mapping
----------------
The ``alerts`` table stores ``metadata`` as a JSON string (or NULL), but
``schemas.Alert.metadata`` is a ``dict``. ``_row_to_alert`` ``json.loads`` the
string (treating NULL/empty as ``None``) before validating, so the rest of the
row maps one-to-one onto the wire model (``dismissed`` int 0/1 -> bool).
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends

from backend import schemas
from backend.deps import get_budget_id, get_db
from src.alerts import AlertRegistry, save_alerts_to_db
from src.cache.database import Database

router = APIRouter(tags=["alerts"])


def _row_to_alert(row) -> schemas.Alert:
    """Map an ``alerts`` row onto the wire model, decoding the JSON metadata.

    The DB stores ``metadata`` as a JSON string; the wire model expects a dict,
    so parse it here. NULL/empty/invalid JSON degrades to ``None`` rather than
    raising, so a malformed legacy row never breaks the listing.
    """
    data = dict(row)
    raw_meta = data.get("metadata")
    if raw_meta:
        try:
            data["metadata"] = json.loads(raw_meta)
        except (json.JSONDecodeError, TypeError):
            data["metadata"] = None
    else:
        data["metadata"] = None
    return schemas.Alert.model_validate(data)


@router.get("/alerts", response_model=list[schemas.Alert])
def list_alerts(
    include_dismissed: bool = False,
    limit: int = 100,
    db: Database = Depends(get_db),
    budget_id: str = Depends(get_budget_id),
) -> list[schemas.Alert]:
    """List persisted alerts (newest first), optionally including dismissed ones."""
    rows = db.get_alerts(budget_id, include_dismissed=include_dismissed, limit=limit)
    return [_row_to_alert(row) for row in rows]


@router.post("/alerts/run", response_model=schemas.MessageResponse)
def run_alerts(
    db: Database = Depends(get_db),
    budget_id: str = Depends(get_budget_id),
) -> schemas.MessageResponse:
    """Run all alert detectors and persist any newly detected alerts.

    Mirrors ``pages/6_Alerts.py``: ``AlertRegistry.run_all`` produces candidate
    alerts and ``save_alerts_to_db`` persists the ones that aren't duplicates of
    existing non-dismissed alerts. The reported count is the number of new alerts
    saved and may be zero on minimal data.
    """
    detected = AlertRegistry.run_all(budget_id, db)
    saved = save_alerts_to_db(db, budget_id, detected)
    return schemas.MessageResponse(
        status="ok", message=f"Detected and saved {saved} new alert(s)."
    )


@router.post("/alerts/{alert_id}/dismiss", response_model=schemas.MessageResponse)
def dismiss_alert(
    alert_id: int,
    db: Database = Depends(get_db),
    budget_id: str = Depends(get_budget_id),
) -> schemas.MessageResponse:
    """Dismiss an alert (best-effort: 200 even if ``alert_id`` matched no row)."""
    db.dismiss_alert(alert_id)
    return schemas.MessageResponse(status="ok", message=f"Alert {alert_id} dismissed.")


@router.post("/alerts/{alert_id}/acknowledge", response_model=schemas.MessageResponse)
def acknowledge_alert(
    alert_id: int,
    db: Database = Depends(get_db),
    budget_id: str = Depends(get_budget_id),
) -> schemas.MessageResponse:
    """Acknowledge an alert (best-effort: 200 even if ``alert_id`` matched no row)."""
    db.acknowledge_alert(alert_id)
    return schemas.MessageResponse(
        status="ok", message=f"Alert {alert_id} acknowledged."
    )
