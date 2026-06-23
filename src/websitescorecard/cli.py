"""CLI entry point for WebsiteScorecard."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console

from websitescorecard import __version__
from websitescorecard.checks import CHECK_REGISTRY, resolve_checks
from websitescorecard.resolve_runner import ResolveConfig, run_resolve
from websitescorecard.runner import ScanConfig, run_scan

app = typer.Typer(
    name="websitescorecard",
    help="Scan websites from a CSV and enrich with check results.",
    no_args_is_help=True,
)
console = Console()


def _default_output_path(input_csv: Path) -> Path:
    return input_csv.with_name(f"{input_csv.stem}_scored{input_csv.suffix}")


def _default_resolve_output_path(input_csv: Path) -> Path:
    return input_csv.with_name(f"{input_csv.stem}_resolved{input_csv.suffix}")


def _parse_suffixes(suffixes: str) -> list[str] | None:
    parsed = [part.strip() for part in suffixes.split(",") if part.strip()]
    return parsed or None


def _collect_check_names(checks: str) -> list[str]:
    return [name.strip().lower() for name in checks.split(",") if name.strip()]


@app.command("scan")
def scan(
    input_csv: Annotated[Path, typer.Argument(help="Input CSV file path")],
    column: Annotated[str, typer.Option("-c", "--column", help="CSV column containing website URLs")],
    output: Annotated[
        Optional[Path],
        typer.Option("-o", "--output", help="Output CSV file path"),
    ] = None,
    checks: Annotated[
        str,
        typer.Option("--checks", help="Comma-separated list of checks to run (e.g. ssl)"),
    ] = "",
    concurrency: Annotated[
        int, typer.Option("--concurrency", help="Number of parallel workers")
    ] = 5,
    timeout: Annotated[
        float, typer.Option("--timeout", help="Per-check socket timeout in seconds")
    ] = 10.0,
    no_error_columns: Annotated[
        bool,
        typer.Option("--no-error-columns", help="Omit error detail columns from output"),
    ] = False,
) -> None:
    """Scan websites from a CSV and write an enriched copy."""
    if not input_csv.exists():
        console.print(f"[red]Error:[/red] Input file not found: {input_csv}")
        raise typer.Exit(code=1)

    check_names = _collect_check_names(checks)
    if not check_names:
        console.print("[red]Error:[/red] No checks specified. Use --checks ssl.")
        raise typer.Exit(code=1)

    unknown = [name for name in check_names if name not in CHECK_REGISTRY]
    if unknown:
        available = ", ".join(sorted(CHECK_REGISTRY))
        console.print(
            f"[red]Error:[/red] Unknown check(s): {', '.join(unknown)}. "
            f"Available: {available}"
        )
        raise typer.Exit(code=1)

    output_path = output or _default_output_path(input_csv)
    enabled_checks = resolve_checks(check_names, timeout=timeout)

    config = ScanConfig(
        input_path=input_csv,
        output_path=output_path,
        url_column=column,
        checks=enabled_checks,
        concurrency=concurrency,
        include_error_columns=not no_error_columns,
    )

    try:
        run_scan(config)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(f"[green]Done.[/green] Wrote {len(enabled_checks)} check(s) to {output_path}")


@app.command("resolve")
def resolve(
    input_csv: Annotated[Path, typer.Argument(help="Input CSV file path")],
    column: Annotated[
        str,
        typer.Option("-c", "--column", help="CSV column with institution/department names"),
    ],
    output: Annotated[
        Optional[Path],
        typer.Option("-o", "--output", help="Output CSV file path"),
    ] = None,
    limit: Annotated[
        int, typer.Option("--limit", help="Max domains to keep per row")
    ] = 1,
    suffixes: Annotated[
        str,
        typer.Option(
            "--suffixes",
            help="Comma-separated hostname suffixes to allow (e.g. gov.lk,gov)",
        ),
    ] = "",
    query_suffix: Annotated[
        str,
        typer.Option("--query-suffix", help="Text appended to every search query"),
    ] = "Sri Lanka",
    url_column: Annotated[
        str,
        typer.Option("--url-column", help="Column name for the first result URL"),
    ] = "URL",
    concurrency: Annotated[
        int, typer.Option("--concurrency", help="Number of parallel workers")
    ] = 1,
    delay: Annotated[
        float,
        typer.Option("--delay", help="Seconds to wait between searches per worker"),
    ] = 1.0,
    timeout: Annotated[
        Optional[float],
        typer.Option("--timeout", help="HTTP timeout for search requests in seconds"),
    ] = None,
) -> None:
    """Resolve institution names to domains via web search and write an enriched CSV."""
    if not input_csv.exists():
        console.print(f"[red]Error:[/red] Input file not found: {input_csv}")
        raise typer.Exit(code=1)

    if limit < 1:
        console.print("[red]Error:[/red] --limit must be at least 1.")
        raise typer.Exit(code=1)

    output_path = output or _default_resolve_output_path(input_csv)
    timeout_seconds = int(timeout) if timeout is not None else None

    config = ResolveConfig(
        input_path=input_csv,
        output_path=output_path,
        name_column=column,
        url_column=url_column,
        limit=limit,
        suffixes=_parse_suffixes(suffixes),
        query_suffix=query_suffix,
        concurrency=concurrency,
        delay=delay,
        timeout=timeout_seconds,
    )

    try:
        run_resolve(config)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(f"[green]Done.[/green] Wrote resolved domains to {output_path}")


@app.command("version")
def version_cmd() -> None:
    """Show the installed version."""
    console.print(__version__)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
