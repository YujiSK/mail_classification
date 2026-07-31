"""Deterministic artifact serialization."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable, Mapping

from mail_classification.schemas import RawMailRecord, sha256_bytes


def records_to_jsonl_bytes(records: Iterable[RawMailRecord]) -> bytes:
    lines = [record.model_dump_json() for record in records]
    return (("\n".join(lines) + "\n") if lines else "").encode("utf-8")


def write_jsonl(path: str | Path, records: list[RawMailRecord]) -> str:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = records_to_jsonl_bytes(records)
    output.write_bytes(payload)
    return sha256_bytes(payload)


def read_jsonl(path: str | Path) -> list[RawMailRecord]:
    return [
        RawMailRecord.model_validate_json(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line
    ]


def write_json(path: str | Path, payload: Mapping[str, object]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def write_csv(
    path: str | Path, rows: list[Mapping[str, object]], fieldnames: list[str]
) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
