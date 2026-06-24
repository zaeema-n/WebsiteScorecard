"""Tests for resolve runner."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from websitescorecard.csv_io import read_csv
from websitescorecard.resolve.resolve_runner import (
    LOOKUP_ERROR_COL,
    LOOKUP_STATUS_COL,
    ResolveConfig,
    _url_columns,
    run_resolve,
)


def test_url_columns_limit_1():
    assert _url_columns("URL", 1) == ["URL"]


def test_url_columns_limit_3():
    assert _url_columns("URL", 3) == ["URL", "url_2", "url_3"]


def test_url_columns_custom_primary():
    assert _url_columns("website", 2) == ["website", "url_2"]


@patch("websitescorecard.resolve.resolve_runner.search_domains")
def test_run_resolve_limit_1(mock_search, tmp_path: Path):
    def fake_search(query: str, **kwargs):
        if "Finance" in query:
            return ["treasury.gov.lk"]
        if "Defence" in query:
            return ["defence.gov.lk"]
        return []

    mock_search.side_effect = fake_search

    input_csv = tmp_path / "input.csv"
    output_csv = tmp_path / "output.csv"
    input_csv.write_text(
        "Institution Name\nMinistry of Finance\nMinistry of Defence\n",
        encoding="utf-8",
    )

    config = ResolveConfig(
        input_path=input_csv,
        output_path=output_csv,
        name_column="Institution Name",
        limit=1,
        suffixes=["gov.lk"],
        delay=0,
    )

    run_resolve(config)

    columns, rows = read_csv(output_csv)
    assert columns == ["Institution Name", "URL", LOOKUP_STATUS_COL, LOOKUP_ERROR_COL]
    assert rows[0] == {
        "Institution Name": "Ministry of Finance",
        "URL": "treasury.gov.lk",
        LOOKUP_STATUS_COL: "ok",
        LOOKUP_ERROR_COL: "",
    }
    assert rows[1]["URL"] == "defence.gov.lk"
    assert rows[1][LOOKUP_STATUS_COL] == "ok"
    assert mock_search.call_count == 2


@patch("websitescorecard.resolve.resolve_runner.search_domains")
def test_run_resolve_limit_3(mock_search, tmp_path: Path):
    mock_search.return_value = ["first.gov.lk", "second.gov.lk", "third.gov.lk"]

    input_csv = tmp_path / "input.csv"
    output_csv = tmp_path / "output.csv"
    input_csv.write_text("Institution Name\nMinistry A\n", encoding="utf-8")

    config = ResolveConfig(
        input_path=input_csv,
        output_path=output_csv,
        name_column="Institution Name",
        limit=3,
        delay=0,
    )

    run_resolve(config)

    columns, rows = read_csv(output_csv)
    assert columns == [
        "Institution Name",
        "URL",
        "url_2",
        "url_3",
        LOOKUP_STATUS_COL,
        LOOKUP_ERROR_COL,
    ]
    row = rows[0]
    assert row["URL"] == "first.gov.lk"
    assert row["url_2"] == "second.gov.lk"
    assert row["url_3"] == "third.gov.lk"
    assert row[LOOKUP_STATUS_COL] == "ok"
    assert row[LOOKUP_ERROR_COL] == ""


@patch("websitescorecard.resolve.resolve_runner.search_domains")
def test_run_resolve_skips_existing_url(mock_search, tmp_path: Path):
    input_csv = tmp_path / "input.csv"
    output_csv = tmp_path / "output.csv"
    input_csv.write_text(
        "Institution Name,URL\nMinistry of Finance,manual.gov.lk\nMinistry of Defence,\n",
        encoding="utf-8",
    )
    mock_search.return_value = ["defence.gov.lk"]

    config = ResolveConfig(
        input_path=input_csv,
        output_path=output_csv,
        name_column="Institution Name",
        limit=1,
        delay=0,
    )

    run_resolve(config)

    _, rows = read_csv(output_csv)
    assert rows[0]["URL"] == "manual.gov.lk"
    assert rows[0][LOOKUP_STATUS_COL] == ""
    assert rows[1]["URL"] == "defence.gov.lk"
    assert rows[1][LOOKUP_STATUS_COL] == "ok"
    mock_search.assert_called_once()


@patch("websitescorecard.resolve.resolve_runner.search_domains")
def test_run_resolve_no_results(mock_search, tmp_path: Path):
    mock_search.return_value = []

    input_csv = tmp_path / "input.csv"
    output_csv = tmp_path / "output.csv"
    input_csv.write_text("Institution Name\nUnknown Body\n", encoding="utf-8")

    config = ResolveConfig(
        input_path=input_csv,
        output_path=output_csv,
        name_column="Institution Name",
        limit=1,
        delay=0,
    )

    run_resolve(config)

    _, rows = read_csv(output_csv)
    assert rows[0]["URL"] == ""
    assert rows[0][LOOKUP_STATUS_COL] == "no_results"
    assert rows[0][LOOKUP_ERROR_COL] == ""


@patch("websitescorecard.resolve.resolve_runner.search_domains")
def test_run_resolve_search_error(mock_search, tmp_path: Path):
    mock_search.side_effect = RuntimeError("search failed")

    input_csv = tmp_path / "input.csv"
    output_csv = tmp_path / "output.csv"
    input_csv.write_text("Institution Name\nMinistry A\n", encoding="utf-8")

    config = ResolveConfig(
        input_path=input_csv,
        output_path=output_csv,
        name_column="Institution Name",
        limit=1,
        delay=0,
    )

    run_resolve(config)

    _, rows = read_csv(output_csv)
    assert rows[0]["URL"] == ""
    assert rows[0][LOOKUP_STATUS_COL] == "error"
    assert rows[0][LOOKUP_ERROR_COL] == "search failed"


def test_run_resolve_empty_name_records_error(tmp_path: Path):
    input_csv = tmp_path / "input.csv"
    output_csv = tmp_path / "output.csv"
    input_csv.write_text("Institution Name\n  \n", encoding="utf-8")

    config = ResolveConfig(
        input_path=input_csv,
        output_path=output_csv,
        name_column="Institution Name",
        limit=1,
        delay=0,
    )

    with patch("websitescorecard.resolve.resolve_runner.search_domains") as mock_search:
        run_resolve(config)
        mock_search.assert_not_called()

    _, rows = read_csv(output_csv)
    assert rows[0][LOOKUP_STATUS_COL] == "error"
    assert "Empty value" in rows[0][LOOKUP_ERROR_COL]


def test_run_resolve_missing_column_raises(tmp_path: Path):
    input_csv = tmp_path / "input.csv"
    output_csv = tmp_path / "output.csv"
    input_csv.write_text("name\nAcme\n", encoding="utf-8")

    config = ResolveConfig(
        input_path=input_csv,
        output_path=output_csv,
        name_column="Institution Name",
        delay=0,
    )

    with pytest.raises(ValueError, match="Institution Name"):
        run_resolve(config)
