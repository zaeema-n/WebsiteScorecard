"""Tests for domain search."""

from unittest.mock import MagicMock, patch

import pytest

from websitescorecard.resolve.domain_search import (
    extract_hostname,
    hostnames_from_results,
    matches_suffix,
    normalize_suffixes,
    search_domains,
)


@pytest.mark.parametrize(
    ("hostname", "suffixes", "expected"),
    [
        ("treasury.gov.lk", ["gov.lk", "gov"], True),
        ("treasury.gov.lk", ["gov"], False),
        ("defence.gov", ["gov"], True),
        ("defence.gov", ["gov.lk"], False),
        ("evil.gov.attacker.com", ["gov"], False),
        ("notgov.com", ["gov"], False),
        ("gov.lk", ["gov.lk"], True),
        ("www.example.gov.lk", ["gov.lk"], True),
    ],
)
def test_matches_suffix(hostname, suffixes, expected):
    assert matches_suffix(hostname, suffixes) is expected


def test_matches_suffix_none_suffixes_accepts_all():
    assert matches_suffix("anything.com", None) is True


def test_normalize_suffixes_longest_first():
    assert normalize_suffixes(["gov", "gov.lk", ".GOV.LK"]) == ["gov.lk", "gov"]


def test_normalize_suffixes_empty_returns_none():
    assert normalize_suffixes([]) is None
    assert normalize_suffixes(["", "  "]) is None


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.treasury.gov.lk/about", "treasury.gov.lk"),
        ("http://defence.gov", "defence.gov"),
        ("treasury.gov.lk", "treasury.gov.lk"),
        ("https://example.com:8443/path", "example.com"),
        ("://bad", None),
        ("", None),
    ],
)
def test_extract_hostname(url, expected):
    assert extract_hostname(url) == expected


def test_hostnames_from_results_dedupes_and_filters():
    results = [
        {"href": "https://www.treasury.gov.lk/"},
        {"href": "https://treasury.gov.lk/page"},
        {"href": "https://en.wikipedia.org/wiki/Treasury"},
        {"href": "https://defence.gov.lk/"},
        {"href": "https://news.site.com/story"},
    ]

    assert hostnames_from_results(
        results,
        normalized_suffixes=normalize_suffixes(["gov.lk", "gov"]),
    ) == [
        "treasury.gov.lk",
        "defence.gov.lk",
    ]


@patch("websitescorecard.resolve.domain_search.DDGS")
def test_search_domains_filters_and_limits(mock_ddgs_cls):
    mock_ddgs = MagicMock()
    mock_ddgs.__enter__.return_value = mock_ddgs
    mock_ddgs.text.return_value = [
        {"href": "https://www.treasury.gov.lk/"},
        {"href": "https://en.wikipedia.org/wiki/Treasury"},
        {"href": "https://defence.gov.lk/"},
        {"href": "https://finance.gov.lk/"},
    ]
    mock_ddgs_cls.return_value = mock_ddgs

    domains = search_domains(
        "Ministry of Finance Sri Lanka",
        limit=2,
        normalized_suffixes=normalize_suffixes(["gov.lk"]),
        oversample_factor=2,
    )

    assert domains == ["treasury.gov.lk", "defence.gov.lk"]
    mock_ddgs.text.assert_called_once_with("Ministry of Finance Sri Lanka", max_results=4)


@patch("websitescorecard.resolve.domain_search.DDGS")
def test_search_domains_zero_limit_returns_empty(mock_ddgs_cls):
    assert search_domains("query", limit=0) == []
    mock_ddgs_cls.assert_not_called()
