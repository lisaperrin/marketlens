"""Presentation: rich tables for the terminal and plain dicts for JSON and MCP."""

from marketlens.report.brief import Brief, build_brief
from marketlens.report.tables import (
    alerts_table,
    brief_renderable,
    comparison_table,
    indicator_table,
    portfolio_table,
    quote_table,
    summary_table,
)

__all__ = [
    "Brief",
    "alerts_table",
    "brief_renderable",
    "build_brief",
    "comparison_table",
    "indicator_table",
    "portfolio_table",
    "quote_table",
    "summary_table",
]
