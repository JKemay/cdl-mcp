# cdl-mcp

MCP server for Call of Duty League match data. Pulls from breakingpoint.gg since
there's no official CDL stats API.

**Heads up.** This is a scraper, not an authorized API client. Use it for personal
analysis only. Don't redistribute the data, don't run it commercially, and don't
hammer their site. The server has mandatory in-memory caching with conservative
TTLs and a polite User-Agent. If breakingpoint.gg changes their HTML, parsers will
break and you'll need to fix the selectors.

## Tools exposed

- `list_matches(limit)` - recent and upcoming CDL matches with IDs you can drill into
- `match_summary(match_id)` - full per-map breakdown with per-player stats
- `find_team_matches(team_name, limit)` - filter matches by team
- `event_overview(event_id)` - event info, participating teams, match list
- `clear_cache()` - drop the cache, useful for live matches

## Setup

```bash
pip install -e .
cdl-mcp   # should sit waiting for MCP stdio, ctrl+c to exit
```

## Claude Desktop config

In `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cdl": {
      "command": "cdl-mcp"
    }
  }
}
```

Restart Claude Desktop.

## Example prompts once wired up

- "What CDL matches are coming up in the next 24 hours?"
- "Pull the full stat breakdown for match 214971"
- "How did OpTic Texas do in their last 5 matches?"
- "Show me the CDL Minor 2 Tournament event details, event 108"

## Caching strategy

- Match list: 60s TTL (changes often as games go live)
- Finished match detail: 600s TTL (doesn't change)
- Event pages: 300s TTL

If you're tracking a live match, call `clear_cache()` between refreshes or just
wait the 60s.

## Known fragility

Parsers depend on breakingpoint.gg's current HTML structure as of June 2026:
- Match list: parsed from `<a href="/match/{id}">` blocks
- Match detail: per-map `<h6>` headers and `<table>` rows
- Player IDs: extracted from `/players/{id}/{name}` link patterns

If they redesign or move to a heavier client-side render that ditches SSR, you'll
need to either rewrite the parsers or swap in Playwright. The scraper structure
in `scraper.py` is isolated from the MCP layer so you only have to touch one file.

## What's intentionally missing

- No standings tool yet. The standings page is a JS-rendered grid that doesn't
  show in static HTML, so it'd need Playwright. If you want it, that's a separate
  dependency and a noticeable startup cost. Easy to bolt on if you decide it's
  worth it.
- No player career stats aggregator. Individual player pages exist at
  `/players/{id}/{name}` but the season totals there are also JS-rendered.

Both are doable, just want to be honest that "scrape all of breakingpoint.gg"
isn't free, and the SSR'd match pages are the highest-signal cheapest target.
