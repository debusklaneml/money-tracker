"""Tests for the imports router (bead bud-rbx).

A temp SQLite file is configured via ``BUD_DB_PATH`` BEFORE importing
``backend.deps`` so the shared Database singleton points at it. Only the imports
router is mounted on a fresh FastAPI app.

There is no OFX/QFX sample in the repo, so we construct a minimal but valid OFX
1.x (SGML) byte string matching what ``src.imports.ofx.parse_ofx_bytes``
expects (an ``<OFX>`` root, a ``<STMTRS>`` block with ``<ACCTID>``/``<ACCTTYPE>``
and ``<STMTTRN>`` rows carrying ``<FITID>``/``<DTPOSTED>``/``<TRNAMT>``).

Flow exercised:
  1. preview -> 200, parsed txns present, AND the DB has written nothing.
  2. commit -> ImportResult counts.
  3. history -> the committed batch shows up.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Minimal valid OFX 1.x (SGML) statement: one checking account, two txns.
SAMPLE_OFX = b"""OFXHEADER:100
DATA:OFXSGML
VERSION:102

<OFX>
<BANKMSGSRSV1>
<STMTTRNRS>
<STMTRS>
<CURDEF>USD
<BANKACCTFROM>
<ACCTID>123456789
<ACCTTYPE>CHECKING
</BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260101120000
<TRNAMT>-25.00
<FITID>TXN-0001
<NAME>Coffee Shop
<MEMO>Latte
</STMTTRN>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20260103120000
<TRNAMT>1500.00
<FITID>TXN-0002
<NAME>Employer
<MEMO>Paycheck
</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL>
<BALAMT>1475.00
<DTASOF>20260103120000
</LEDGERBAL>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""


@pytest.fixture()
def client_and_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = Path(tmp.name)
    os.environ["BUD_DB_PATH"] = str(db_path)

    # No importlib.reload: reloading swaps module identity in sys.modules,
    # which desyncs routers' Depends() from the providers other tests clear.
    from backend import deps
    deps.get_db.cache_clear()
    deps.get_budget_id.cache_clear()

    from backend.routers import imports

    app = FastAPI()
    app.include_router(imports.router, prefix="/api")
    test_client = TestClient(app)

    db = deps.get_db()
    budget_id = deps.get_budget_id()

    try:
        yield test_client, db, budget_id
    finally:
        deps.get_db.cache_clear()
        deps.get_budget_id.cache_clear()
        os.environ.pop("BUD_DB_PATH", None)
        for suffix in ("", "-wal", "-shm"):
            p = Path(str(db_path) + suffix)
            if p.exists():
                p.unlink()


def _upload(client, path, content=SAMPLE_OFX, filename="statement.ofx"):
    return client.post(
        path,
        files={"file": (filename, content, "application/x-ofx")},
    )


def _count_transactions(db, budget_id):
    with db._get_connection() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE budget_id = ?",
            (budget_id,),
        ).fetchone()[0]


def test_preview_does_not_write(client_and_db):
    client, db, budget_id = client_and_db

    resp = _upload(client, "/api/imports/preview")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["filename"] == "statement.ofx"
    assert len(body["accounts"]) == 1
    assert len(body["new_transactions"]) == 2
    assert body["duplicate_count"] == 0
    assert body["already_imported_file"] is False
    assert body["date_min"] == "2026-01-01"
    assert body["date_max"] == "2026-01-03"

    # -25.00 dollars -> -25000 milliunits.
    amounts = {t["amount"] for t in body["new_transactions"]}
    assert amounts == {-25000, 1500000}

    # The hard requirement: preview wrote nothing.
    assert _count_transactions(db, budget_id) == 0


def test_commit_then_history(client_and_db):
    client, db, budget_id = client_and_db

    resp = _upload(client, "/api/imports")
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["imported"] == 2
    assert result["duplicates"] == 0
    assert result["already_imported_file"] is False
    assert len(result["accounts"]) == 1
    assert result["date_min"] == "2026-01-01"
    assert result["date_max"] == "2026-01-03"

    assert _count_transactions(db, budget_id) == 2

    # Re-importing the same file: all FITIDs are dupes, file hash flagged.
    resp2 = _upload(client, "/api/imports")
    assert resp2.status_code == 200, resp2.text
    result2 = resp2.json()
    assert result2["imported"] == 0
    assert result2["duplicates"] == 2
    assert result2["already_imported_file"] is True

    # Preview after a commit should now report the txns as duplicates.
    prev = _upload(client, "/api/imports/preview").json()
    assert prev["duplicate_count"] == 2
    assert prev["new_transactions"] == []
    assert prev["already_imported_file"] is True

    # History shows the recorded batch(es).
    hist = client.get("/api/imports/history")
    assert hist.status_code == 200, hist.text
    batches = hist.json()
    assert len(batches) >= 1
    first = batches[0]
    assert first["filename"] == "statement.ofx"
    assert first["txn_count"] == 2

    # limit param is honoured.
    limited = client.get("/api/imports/history?limit=1")
    assert limited.status_code == 200
    assert len(limited.json()) == 1


def test_delete_removes_batch_and_transactions(client_and_db):
    client, db, budget_id = client_and_db

    # Commit an import, then locate its batch.
    resp = _upload(client, "/api/imports")
    assert resp.status_code == 200, resp.text
    assert _count_transactions(db, budget_id) == 2

    batches = client.get("/api/imports/history").json()
    assert len(batches) == 1
    batch_id = batches[0]["id"]

    # Delete it: reports how many transactions were cascade-removed.
    resp = client.delete(f"/api/imports/{batch_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == batch_id
    assert body["deleted_transactions"] == 2

    # Both the batch and its transactions are gone.
    assert _count_transactions(db, budget_id) == 0
    assert client.get("/api/imports/history").json() == []


def test_delete_missing_batch_is_404(client_and_db):
    client, _, _ = client_and_db
    resp = client.delete("/api/imports/9999")
    assert resp.status_code == 404


def test_reimport_after_delete_succeeds(client_and_db):
    client, db, budget_id = client_and_db

    # Import, then delete the batch.
    _upload(client, "/api/imports")
    batch_id = client.get("/api/imports/history").json()[0]["id"]
    assert client.delete(f"/api/imports/{batch_id}").status_code == 200

    # After deletion, a preview treats the file as brand new (its hash is no
    # longer recorded and its FITIDs were removed with the transactions).
    prev = _upload(client, "/api/imports/preview").json()
    assert prev["already_imported_file"] is False
    assert prev["duplicate_count"] == 0
    assert len(prev["new_transactions"]) == 2

    # Re-importing the SAME file must now work as a fresh import.
    resp = _upload(client, "/api/imports")
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["imported"] == 2
    assert result["duplicates"] == 0
    assert result["already_imported_file"] is False
    assert _count_transactions(db, budget_id) == 2


def test_empty_file_is_400(client_and_db):
    client, _, _ = client_and_db
    resp = _upload(client, "/api/imports/preview", content=b"")
    assert resp.status_code == 400


def test_garbage_file_is_400(client_and_db):
    client, _, _ = client_and_db
    resp = _upload(client, "/api/imports/preview", content=b"not an ofx file")
    assert resp.status_code == 400
    resp2 = _upload(client, "/api/imports", content=b"not an ofx file")
    assert resp2.status_code == 400
