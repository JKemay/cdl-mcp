# cdl-mcp

An MCP server that lets a Claude model query Call of Duty League match data. Install it locally, plug it into Claude Desktop, and ask about CDL matches, stats, events, and teams in normal conversation.

## What's behind it

There is no official CDL stats API. Activision pulled their old endpoints years ago and callofdutyleague.com doesn't expose JSON. So this server scrapes breakingpoint.gg, which is the best community-run CDL stats site. Their match pages are server-side rendered with full per-map per-player stats embedded in the HTML, which makes scraping clean and Playwright unnecessary.

That said, this is a scraper, not an authorized client. A few things to keep in mind:

- Personal use only. Don't redistribute the data, don't run this as a public service, don't put it behind your own paid product.
- Caching is mandatory. The server caches every response with conservative TTLs. Don't disable it.
- The polite User-Agent identifies the tool. Don't change it to spoof a browser.
- If breakingpoint.gg redesigns their HTML, parsers break. Selectors are isolated to one file so the fix is usually a couple of lines.

If you ever want to do this above-board, email steve@breakingpoint.gg (that's actually what the "API" link in their footer is, just an obfuscated email address). They might be open to a partnership for a real integration.

## Setup

Python 3.10 or newer. From inside the project folder:

```bash
pip install -e .
```

That installs the package and registers `cdl-mcp` as a console script. Test it runs:

```bash
cdl-mcp
```

It should hang waiting for MCP stdio input. Ctrl+C to exit. No prints expected, MCP runs over stdout.

## Plugging it into Claude Desktop

Find your `claude_desktop_config.json`:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

Add a `cdl` entry under `mcpServers`:

```json
{
  "mcpServers": {
    "cdl": {
      "command": "cdl-mcp"
    }
  }
}
```

If `cdl-mcp` isn't on Claude Desktop's PATH (homebrew or pyenv pythons especially), use the absolute path. Find it with `which cdl-mcp` and paste it in.

Restart Claude Desktop. Open the tools menu and you should see five tools under "cdl".

You can run this alongside valorant-mcp by putting both blocks in the same `mcpServers` object.

## Tool reference

### `list_matches(limit=20)`

Recent and upcoming CDL matches. Each entry has a match ID you can drill into.

Each item: `match_id`, `url`, `when` (like "~10 hours" or "LIVE"), `blurb` (event name and teams), `raw_text` (the full link text in case you need to parse more).

The match list strip appears on most BP pages and includes both upcoming and just-finished matches.

### `match_summary(match_id)`

Full breakdown for one match. The big one.

Returns:

- `match_id`, `url`, `title`
- `event` - dict with `id` and `name`
- `team_ids` - the two team IDs in order
- `teams` - team names parsed from the page title
- `maps` - list of dicts with `map_num`, `map`, `mode` (Hardpoint, Search & Destroy, Control, Overload)
- `stat_tables` - list of tables. The first is the series overall, the rest are per-map breakdowns. Each table has `headers` and `rows`. Each row is a player with `player_id`, `name`, `team_id`, plus all the stats columns for that map's mode (kills, deaths, K/D, +/-, damage, hill time or first bloods depending on mode, BP rating).

Match IDs come from `list_matches`, from URLs you paste, or from `event_overview`.

### `find_team_matches(team_name, limit=10)`

Substring-filter on the match list. Pass a team name fragment.

Examples that work: `"OpTic"`, `"Falcons"`, `"FaZe"`, `"Royal Ravens"`. Case-insensitive.

Returns the same shape as `list_matches`.

### `event_overview(event_id)`

Event info: title, participating teams, list of matches in the event.

Event IDs come from match summaries (`.event.id`) or by browsing breakingpoint.gg/events.

### `clear_cache()`

Drops the in-memory cache. Useful if you're tracking a live match and the 60-second match-list TTL is too slow.

Returns `{"ok": true}`.

## Example prompts

Once the server is wired up:

- "What CDL matches are coming up today?"
- "Pull the full stat breakdown for match 214971"
- "How did Riyadh Falcons play in their last match? Who topped the boards?"
- "Show me the CDL Minor 2 Tournament event, event ID 108"
- "Find OpTic Texas's last five matches and tell me their win rate"
- "Compare Cellium and Pred's stats from the Falcons vs Ravens match"

The model picks tools, calls them, synthesizes. If a live match is updating and the cache is stale, you can say "clear the cache and refresh" and it'll call `clear_cache()` first.

## Caching strategy

Per-endpoint TTLs, all measured from the moment of the call:

- Match list (`/matches`): 60 seconds. Changes when games go live or finish.
- Finished match detail: 600 seconds (10 minutes). Doesn't change once final.
- Event page: 300 seconds (5 minutes). Updates as matches in the event finish.

If you want different TTLs, edit `_default_ttl` in `BPScraper.__init__` or pass `ttl` to specific `_fetch` calls.

## Troubleshooting

**Tools don't show up in Claude Desktop.** Restart the app fully. Check the config JSON is valid. Run `cdl-mcp` from terminal directly to confirm the script is on PATH.

**Empty `stat_tables` from `match_summary`.** The match might not have stats yet (upcoming or live with no maps finished). Check the URL in a browser. If the page has stats but the tool returns nothing, the table HTML structure changed and you need to update `_parse_stats_table` in `scraper.py`.

**`team_ids` is empty or wrong length.** The match page didn't render two team links in the order expected. This happens for TBD matches and forfeits.

**Match IDs that work in the browser return 404.** BP sometimes uses redirect URLs with the team names in them, like `/match/214971/Riyadh-Falcons-vs-...`. The numeric ID alone works for fetching, that's what the scraper uses. If it 404s, the match might have been removed.

**Everything fails with 429 or 503.** You're hitting BP too fast. The cache should be preventing this, but if you're rapidly clearing the cache or running multiple Claude conversations at once, back off. If it keeps happening, your IP might be flagged temporarily, wait a few hours.

## Why some things aren't here

**No season standings tool.** The standings page hydrates from client-side JS, so the static HTML you'd get from a plain HTTP fetch has nothing useful. Pulling standings would mean adding Playwright as a dependency, plus shipping a headless Chromium binary, plus eating a 1 to 2 second cold start per call. If you really want standings exposed to the model, that's a separate `cdl-mcp[browser]` extra and worth its own decision. For now, the model can usually derive standings from event results.

**No per-player career aggregates.** Individual player pages at `/players/{id}/{name}` show career and season totals, but again hydrated client-side. Same Playwright tradeoff. If you want this, the easier path might be to call `match_summary` for the last N matches and aggregate in Python.

**No fantasy projections.** BP's fantasy data is behind their login. Not touching it.

## Dev notes

Two real source files. `cache.py` is a tiny TTL cache, no dependencies. `scraper.py` does all the HTTP fetching and HTML parsing. `server.py` exposes the scraper as MCP tools.

To add a tool, decorate an async function with `@mcp.tool()` and write a clear docstring. The model reads the docstring to decide when to call it.

To handle a page BP redesigns, fix the selector in `scraper.py`. Methods are:

- `_parse_match_links(html)` for the match list strip
- `_parse_stats_table(table)` for player stat tables
- `match_summary(match_id)` orchestrates the whole match detail extraction

The BP HTML uses some patterns you can rely on: `/match/{id}`, `/teams/{id}`, `/players/{id}/{name}` URL shapes, and `<h6>Map N: <map> <mode> - Breakdown` headers for map sections. Those have been stable across CoD title transitions in the past. The table column headers might shift between modes (Hill Time for Hardpoint, FB for SnD, Goals for Overload) so the parser zips columns to headers dynamically rather than assuming positions.

## License and credits

This server is not affiliated with breakingpoint.gg, the Call of Duty League, Activision, or any of the CDL teams. All trademarks belong to their respective owners.

Use this for personal analysis. Don't be the reason BP has to add a CAPTCHA.
