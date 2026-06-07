"""Imports router (bead bud-rbx): preview, commit, and history for OFX/QFX uploads.

Three endpoints back the import workflow:

* ``POST /imports/preview`` parses an uploaded OFX/QFX file and reports what an
  import *would* do — parsed accounts, the transactions that would be inserted,
  and how many would be skipped as duplicates — WITHOUT writing anything to the
  database. This is the read-only "dry run" the UI shows before committing.
* ``POST /imports`` performs the real import via
  :meth:`ImportService.import_file`, which parses, dedupes (by bank FITID and by
  file content hash) and inserts in one call.
* ``GET /imports/history`` lists recorded import batches, newest first.

Money convention: amounts are signed milliunits (negative = outflow), matching
the rest of the API. The OFX parser yields ``Decimal`` dollars, so preview
converts them with ``dollars_to_milliunits`` (the same helper the service uses)
to keep the preview numbers identical to what a commit would store.

How preview avoids writing
--------------------------
There is no parse-only method on :class:`ImportService`, so this router calls
the dependency-free parser :func:`src.imports.ofx.parse_ofx_bytes` directly. To
report duplicates without inserting, it resolves each parsed OFX account number
to an existing account id via the read-only :meth:`Database.get_accounts`, then
asks the read-only :meth:`Database.transaction_exists` whether each FITID was
already imported. The "already imported file" flag uses the read-only
:meth:`Database.file_hash_imported`. None of these touch the write path, so the
DB is guaranteed unchanged by a preview. (If a parsed account has never been
imported before, it simply has no existing id and all its transactions are
treated as new — which is correct.)
"""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from backend import schemas
from backend.deps import get_budget_id, get_db, get_import_service
from src.cache.database import Database
from src.imports.ofx import OFXParseError, parse_ofx_bytes
from src.imports.service import ImportService, _account_label
from src.utils.formatters import dollars_to_milliunits

router = APIRouter(tags=["imports"])


@router.post("/imports/preview", response_model=schemas.ImportPreview)
async def preview_import(
    file: UploadFile = File(...),
    db: Database = Depends(get_db),
    budget_id: str = Depends(get_budget_id),
) -> schemas.ImportPreview:
    """Parse an uploaded OFX/QFX file and report what an import would do.

    Read-only: parses with :func:`parse_ofx_bytes` and uses read-only Database
    queries for dedupe detection. Never writes to the database.
    """
    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    try:
        accounts = parse_ofx_bytes(data)
    except OFXParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse OFX/QFX file: {exc}",
        ) from exc

    file_hash = hashlib.sha256(data).hexdigest()
    already_imported_file = db.file_hash_imported(budget_id, file_hash)

    # Read-only map of existing account-number -> account id, so we can probe
    # transaction_exists for FITID dedupe without upserting accounts.
    existing_account_ids = {
        row["account_number"]: row["id"]
        for row in db.get_accounts(budget_id)
        if row["account_number"]
    }

    account_labels: list[str] = []
    new_transactions: list[schemas.Transaction] = []
    duplicate_count = 0
    all_dates: list[str] = []

    for acct in accounts:
        if not acct.account_id:
            continue
        label = _account_label(acct)
        account_labels.append(label)
        existing_id = existing_account_ids.get(acct.account_id)

        for txn in acct.transactions:
            # Mirror the service: rows without a FITID or post date are skipped.
            if not txn.fitid or not txn.posted:
                continue
            date_str = txn.posted.isoformat()
            is_dup = bool(existing_id) and db.transaction_exists(existing_id, txn.fitid)
            if is_dup:
                duplicate_count += 1
                continue
            all_dates.append(date_str)
            new_transactions.append(
                schemas.Transaction(
                    # No DB row exists yet; surface the bank FITID as the id so
                    # the preview rows are still uniquely identifiable in the UI.
                    id=txn.fitid,
                    account_id=existing_id,
                    account_name=label,
                    date=date_str,
                    amount=dollars_to_milliunits(txn.amount),
                    memo=txn.memo,
                    payee_name=txn.payee,
                    import_id=txn.fitid,
                )
            )

    return schemas.ImportPreview(
        filename=file.filename or "upload.ofx",
        accounts=account_labels,
        new_transactions=new_transactions,
        duplicate_count=duplicate_count,
        already_imported_file=already_imported_file,
        date_min=min(all_dates) if all_dates else None,
        date_max=max(all_dates) if all_dates else None,
    )


@router.post("/imports", response_model=schemas.ImportResult)
async def commit_import(
    file: UploadFile = File(...),
    service: ImportService = Depends(get_import_service),
) -> schemas.ImportResult:
    """Import an uploaded OFX/QFX file (parse + dedupe + insert)."""
    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    try:
        result = service.import_file(file.filename or "upload.ofx", data)
    except OFXParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse OFX/QFX file: {exc}",
        ) from exc

    return schemas.ImportResult(
        filename=result.filename,
        accounts=result.accounts,
        imported=result.imported,
        duplicates=result.duplicates,
        auto_categorized=result.auto_categorized,
        already_imported_file=result.already_imported_file,
        date_min=result.date_min,
        date_max=result.date_max,
    )


@router.get("/imports/history", response_model=list[schemas.ImportBatch])
def import_history(
    limit: int = Query(50, ge=1, le=500, description="Max batches to return."),
    db: Database = Depends(get_db),
    budget_id: str = Depends(get_budget_id),
) -> list[schemas.ImportBatch]:
    """List recorded import batches, newest first."""
    rows = db.get_import_batches(budget_id, limit=limit)
    return [schemas.ImportBatch(**dict(row)) for row in rows]
