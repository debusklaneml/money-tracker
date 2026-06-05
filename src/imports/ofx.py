"""Dependency-free OFX / QFX statement parser.

Handles both OFX 1.x (SGML, unclosed leaf tags) and OFX 2.x / QFX (XML).
We only care about the bank-statement subset: accounts, balances, and
transactions. Each transaction carries a FITID, which banks guarantee to be
stable and unique per account — that's what we dedupe on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional


@dataclass
class OFXTransaction:
    fitid: Optional[str]
    posted: Optional[date]
    amount: Decimal          # signed: negative = outflow
    payee: Optional[str]
    memo: Optional[str]
    trntype: Optional[str]


@dataclass
class OFXAccount:
    account_id: Optional[str]      # bank ACCTID (account number)
    account_type: Optional[str]    # CHECKING / SAVINGS / CREDITCARD ...
    balance: Optional[Decimal]
    balance_date: Optional[date]
    transactions: list[OFXTransaction] = field(default_factory=list)


class OFXParseError(ValueError):
    """Raised when a file doesn't look like parseable OFX/QFX."""


def _leaf(tag: str, src: str) -> Optional[str]:
    """Read a leaf tag value, tolerant of SGML (unclosed) and XML (closed)."""
    m = re.search(rf"<{tag}>([^<\r\n]*)", src, re.IGNORECASE)
    return m.group(1).strip() if m and m.group(1).strip() else None


def _parse_date(raw: Optional[str]) -> Optional[date]:
    """OFX dates are YYYYMMDD[HHMMSS][.XXX][+/-TZ]; we keep the calendar day."""
    if not raw:
        return None
    digits = raw.strip()[:8]
    try:
        return datetime.strptime(digits, "%Y%m%d").date()
    except ValueError:
        return None


def _parse_amount(raw: Optional[str]) -> Decimal:
    if not raw:
        return Decimal(0)
    # Some exporters use comma decimals or thousands separators.
    cleaned = raw.strip().replace(",", "")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return Decimal(0)


def parse_ofx(text: str) -> list[OFXAccount]:
    """Parse OFX/QFX text into a list of accounts with their transactions."""
    if "<OFX>" not in text.upper():
        raise OFXParseError("Not an OFX/QFX file (no <OFX> root found).")

    # Drop the SGML/HTTP header block that precedes <OFX> in 1.x files.
    start = text.upper().find("<OFX>")
    body = text[start:]

    accounts: list[OFXAccount] = []
    # Bank statements live in <STMTRS>, credit-card in <CCSTMTRS>.
    for kind, block in re.findall(r"<(STMTRS|CCSTMTRS)>(.*?)</\1>", body, re.S | re.I):
        acct_type = _leaf("ACCTTYPE", block) or ("CREDITCARD" if kind.upper() == "CCSTMTRS" else None)

        # Balance comes from <LEDGERBAL>; isolate it so we read the right BALAMT.
        bal_block = re.search(r"<LEDGERBAL>(.*?)</LEDGERBAL>", block, re.S | re.I)
        bal_src = bal_block.group(1) if bal_block else block
        balance_raw = _leaf("BALAMT", bal_src)

        account = OFXAccount(
            account_id=_leaf("ACCTID", block),
            account_type=acct_type.upper() if acct_type else None,
            balance=_parse_amount(balance_raw) if balance_raw is not None else None,
            balance_date=_parse_date(_leaf("DTASOF", bal_src)),
        )

        for tb in re.findall(r"<STMTTRN>(.*?)</STMTTRN>", block, re.S | re.I):
            account.transactions.append(OFXTransaction(
                fitid=_leaf("FITID", tb),
                posted=_parse_date(_leaf("DTPOSTED", tb)),
                amount=_parse_amount(_leaf("TRNAMT", tb)),
                payee=_leaf("NAME", tb) or _leaf("PAYEE", tb),
                memo=_leaf("MEMO", tb),
                trntype=_leaf("TRNTYPE", tb),
            ))

        accounts.append(account)

    if not accounts:
        raise OFXParseError("No bank or credit-card statements found in the file.")

    return accounts


def parse_ofx_bytes(data: bytes) -> list[OFXAccount]:
    """Parse raw uploaded bytes, tolerating common encodings used by banks."""
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            return parse_ofx(data.decode(encoding))
        except UnicodeDecodeError:
            continue
    # Last resort: decode with replacement so a stray byte doesn't kill the import.
    return parse_ofx(data.decode("utf-8", errors="replace"))
