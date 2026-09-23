import asyncio

from mcp.server.fastmcp import FastMCP

from .scraper import BPScraper

_scraper: BPScraper | None = None


def _s() -> BPScraper:
    global _scraper
    if _scraper is None:
        _scraper = BPScraper()
    return _scraper


mcp = FastMCP("cdl")


@mcp.tool()
async def list_matches(limit: int = 20) -> list[dict]:
    """List recent and upcoming CDL matches.

    Each entry has match_id, url, and a blurb describing teams + event + time.
    Use match_summary(match_id) to drill in.
    """
    return await _s().upcoming_and_recent_matches(limit=limit)


@mcp.tool()
async def match_summary(match_id: str) -> dict:
    """Full per-map breakdown for one CDL match, with per-player K/D/damage/BP-rating.

    Returns: event, teams, map list, and stat tables. The first stat table is the
    overall series summary, the rest are per-map breakdowns in map order.
    """
    return await _s().match_summary(match_id)


@mcp.tool()
async def find_team_matches(team_name: str, limit: int = 10) -> list[dict]:
    """Filter recent/upcoming matches to ones involving a team (case-insensitive substring).

    Examples: 'OpTic', 'Falcons', 'FaZe'.
    """
    all_matches = await _s().upcoming_and_recent_matches(limit=200)
    needle = team_name.lower()
    hits = [m for m in all_matches if needle in m.get("blurb", "").lower() or needle in m.get("raw_text", "").lower()]
    return hits[:limit]


@mcp.tool()
async def event_overview(event_id: str) -> dict:
    """Event info: title, participating teams, and matches in the event.

    Find event IDs from match_summary().event.id or by browsing breakingpoint.gg/events.
    """
    return await _s().event_overview(event_id)


@mcp.tool()
async def clear_cache() -> dict:
    """Drop the in-memory cache. Useful if a live match isn't updating."""
    _s()._cache.clear()
    return {"ok": True}


def main():
    try:
        mcp.run()
    finally:
        if _scraper:
            asyncio.run(_scraper.close())


if __name__ == "__main__":
    main()
