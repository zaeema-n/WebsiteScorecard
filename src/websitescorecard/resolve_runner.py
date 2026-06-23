"""Orchestrates resolving institution names to domains via web search."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn, TimeElapsedColumn

from websitescorecard.csv_io import read_csv, write_csv
from websitescorecard.discovery import search_domains

LOOKUP_STATUS_COL = "lookup_status"
LOOKUP_ERROR_COL = "lookup_error"


@dataclass
class ResolveConfig:
    input_path: Path
    output_path: Path
    name_column: str
    url_column: str = "URL"
    limit: int = 1
    suffixes: list[str] | None = None
    query_suffix: str = "Sri Lanka"
    concurrency: int = 1
    delay: float = 1.0
    timeout: int | None = None


def _url_columns(url_column: str, limit: int) -> list[str]:
    columns = [url_column]
    for i in range(2, limit + 1):
        columns.append(f"url_{i}")
    return columns


def _output_columns(original: list[str], url_cols: list[str]) -> list[str]:
    columns = list(original)
    for col in url_cols:
        if col not in columns:
            columns.append(col)
    for col in (LOOKUP_STATUS_COL, LOOKUP_ERROR_COL):
        if col not in columns:
            columns.append(col)
    return columns


def _has_existing_url(row: dict[str, str], url_column: str) -> bool:
    return bool(row.get(url_column, "").strip())


def _ensure_resolve_columns(row: dict[str, str], url_cols: list[str]) -> dict[str, str]:
    enriched = dict(row)
    for col in url_cols:
        enriched.setdefault(col, "")
    enriched.setdefault(LOOKUP_STATUS_COL, "")
    enriched.setdefault(LOOKUP_ERROR_COL, "")
    return enriched


def _resolve_row(
    index: int,
    row: dict[str, str],
    *,
    name_column: str,
    url_columns: list[str],
    suffixes: list[str] | None,
    query_suffix: str,
    limit: int,
    delay: float,
    timeout: int | None,
) -> tuple[int, dict[str, str]]:
    if _has_existing_url(row, url_columns[0]):
        return index, _ensure_resolve_columns(row, url_columns)

    name = row.get(name_column, "").strip()
    if not name:
        enriched = _ensure_resolve_columns(row, url_columns)
        enriched[LOOKUP_STATUS_COL] = "error"
        enriched[LOOKUP_ERROR_COL] = f"Empty value in {name_column!r}"
        return index, enriched

    query = f"{name} {query_suffix}".strip()
    enriched = _ensure_resolve_columns(row, url_columns)

    try:
        domains = search_domains(
            query,
            limit=limit,
            suffixes=suffixes,
            timeout=timeout,
        )
        if domains:
            enriched[LOOKUP_STATUS_COL] = "ok"
            enriched[LOOKUP_ERROR_COL] = ""
            for col, domain in zip(url_columns, domains, strict=False):
                enriched[col] = domain
        else:
            enriched[LOOKUP_STATUS_COL] = "no_results"
            enriched[LOOKUP_ERROR_COL] = ""
    except Exception as exc:
        enriched[LOOKUP_STATUS_COL] = "error"
        enriched[LOOKUP_ERROR_COL] = str(exc)

    if delay > 0:
        time.sleep(delay)

    return index, enriched


def run_resolve(config: ResolveConfig) -> None:
    original_columns, rows = read_csv(config.input_path)

    if config.name_column not in original_columns:
        raise ValueError(
            f"Column {config.name_column!r} not found in CSV. "
            f"Available columns: {', '.join(original_columns)}"
        )

    url_cols = _url_columns(config.url_column, config.limit)
    output_columns = _output_columns(original_columns, url_cols)
    enriched_rows: list[dict[str, str] | None] = [None] * len(rows)

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
    ) as progress:
        task = progress.add_task("Resolving domains...", total=len(rows))

        with ThreadPoolExecutor(max_workers=config.concurrency) as executor:
            futures = {
                executor.submit(
                    _resolve_row,
                    i,
                    row,
                    name_column=config.name_column,
                    url_columns=url_cols,
                    suffixes=config.suffixes,
                    query_suffix=config.query_suffix,
                    limit=config.limit,
                    delay=config.delay,
                    timeout=config.timeout,
                ): i
                for i, row in enumerate(rows)
            }
            for future in as_completed(futures):
                index, enriched = future.result()
                enriched_rows[index] = enriched
                progress.advance(task)

    write_csv(config.output_path, output_columns, enriched_rows)  # type: ignore[arg-type]
