#!/usr/bin/env python
"""Utilities shared by legacy migration scripts."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional

LOGGER = logging.getLogger(__name__)


def normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_string(value: Any, upper: bool = False) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        raw = value
    else:
        raw = str(value)
    raw = normalize_spaces(raw)
    return raw.upper() if upper else raw


def normalize_code(value: Any) -> str:
    return normalize_string(value, upper=True)


def normalize_document(value: Any) -> str:
    normalized = normalize_string(value, upper=True)
    normalized = re.sub(r"[^A-Z0-9]", "", normalized)
    return normalized


def normalize_email(value: Any) -> str:
    email = normalize_string(value).lower()
    return email if "@" in email else ""


def parse_decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    if value in (None, ""):
        return default
    if isinstance(value, Decimal):
        return value
    raw = normalize_string(value)
    if not raw:
        return default

    raw = raw.replace("$", "").replace("%", "")
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    else:
        raw = raw.replace(",", ".")

    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return default


def parse_int(value: Any, default: int = 0) -> int:
    dec = parse_decimal(value, default=Decimal(default))
    try:
        return int(dec)
    except (TypeError, ValueError):
        return default


def parse_date(value: Any) -> Optional[date]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    raw = normalize_string(value)
    if not raw:
        return None

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


@dataclass
class Incident:
    severity: str
    stage: str
    source: str
    key: str
    message: str


class IncidentLogger:
    def __init__(self) -> None:
        self.items: list[Incident] = []

    def add(self, severity: str, stage: str, source: str, key: str, message: str) -> None:
        self.items.append(
            Incident(
                severity=severity.upper(),
                stage=stage,
                source=source,
                key=normalize_string(key),
                message=normalize_spaces(message),
            )
        )

    def summary(self) -> dict[str, int]:
        counters: dict[str, int] = {"INFO": 0, "WARN": 0, "ERROR": 0}
        for item in self.items:
            counters[item.severity] = counters.get(item.severity, 0) + 1
        return counters

    def dump_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "summary": self.summary(),
            "incidents": [asdict(item) for item in self.items],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        LOGGER.info("Reporte de incidencias escrito en %s", path)
