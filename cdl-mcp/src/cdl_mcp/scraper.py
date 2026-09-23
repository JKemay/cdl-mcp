import json
import re

import httpx
from bs4 import BeautifulSoup

from .cache import TTLCache

BASE = "https://breakingpoint.gg"

# polite UA, identifies the tool. don't pretend to be a browser
UA = "cdl-mcp/0.1 (personal MCP integration, contact via github)"

# url pattern matchers
MATCH_LINK = re.compile(r"/match/(\d+)")
TEAM_LINK = re.compile(r"/teams/(\d+)")
PLAYER_LINK = re.compile(r"/players/(\d+)/([^/?#]+)")
EVENT_LINK = re.compile(r"/events/(\d+)")


class BPScraper:
    def __init__(self, cache_ttl: int = 120):
        self._http = httpx.AsyncClient(
            base_url=BASE,
            headers={"User-Agent": UA, "Accept": "text/html"},
            timeout=20.0,
            follow_redirects=True,
        )
        self._cache = TTLCache()
        self._default_ttl = cache_ttl

    async def close(self):
        await self._http.aclose()

    # fetches a path with caching, longer ttl for finished matches since they don't change
    async def _fetch(self, path: str, ttl: int | None = None) -> str:
        ttl = ttl if ttl is not None else self._default_ttl
        hit = self._cache.get(path)
        if hit is not None:
            return hit
        r = await self._http.get(path)
        if r.status_code == 429:
            raise RuntimeError("breakingpoint.gg rate limited us, slow down")
        if r.status_code >= 400:
            raise RuntimeError(f"HTTP {r.status_code} fetching {path}")
        self._cache.set(path, r.text, ttl)
        return r.text

    # parse the floating match strip that appears on most pages
    # each <a href="/match/{id}"> contains the time, event name, both team names, and scores
    def _parse_match_links(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        out = []
        seen = set()
        for a in soup.find_all("a", href=MATCH_LINK):
            href = a.get("href", "")
            m = MATCH_LINK.search(href)
            if not m:
                continue
            mid = m.group(1)
            if mid in seen:
                continue
            seen.add(mid)
            text = a.get_text(" ", strip=True)
            # text shape: "~10 hours CDL Minor 2 Tournament Riyadh Falcons Riyadh Falcons 0 Carolina Royal Ravens Carolina Royal Ravens 0"
            # team names duplicate because there's both an img alt and a span label
            out.append({
                "match_id": mid,
                "url": f"{BASE}/match/{mid}",
                "raw_text": text,
                **self._parse_match_link_text(text),
            })
        return out

    # tries to pull time/event/teams/scores out of the run-together link text
    def _parse_match_link_text(self, text: str) -> dict:
        # pattern: <when><event><teamA repeated><scoreA><teamB repeated><scoreB>
        # since team names duplicate, we split on digits at the end
        # this is best-effort, the structured fields below are more reliable
        when = ""
        m = re.match(r"^(~?\s*\d+\s*(?:hours?|days?|minutes?|min)|LIVE|TBD)\s+(.*)$", text)
        if m:
            when = m.group(1).strip()
            rest = m.group(2)
        else:
            rest = text

        # try to extract trailing score pattern "<team><team><digit><team><team><digit>"
        # fall back to just returning the raw rest
        return {"when": when, "blurb": rest}

    # full match detail: per-map scores, per-player stats per map
    async def match_summary(self, match_id: str) -> dict:
        # finished matches barely change, cache them longer
        ttl = 600 if not match_id.startswith("live-") else 30
        html = await self._fetch(f"/match/{match_id}", ttl=ttl)
        soup = BeautifulSoup(html, "html.parser")

        # event name and id from the link near the top
        event = {"id": None, "name": None}
        for a in soup.find_all("a", href=EVENT_LINK):
            event["id"] = EVENT_LINK.search(a["href"]).group(1)
            event["name"] = a.get_text(strip=True)
            break

        # team blocks, two of them
        team_ids = []
        for a in soup.find_all("a", href=TEAM_LINK):
            tid = TEAM_LINK.search(a["href"]).group(1)
            if tid not in team_ids:
                team_ids.append(tid)
            if len(team_ids) >= 2:
                break

        # title tag has "Team A vs Team B at Event Year"
        title = (soup.find("title").text if soup.find("title") else "").strip()
        teams_from_title = []
        m = re.search(r"^(.+?)\s+vs\s+(.+?)\s+at\s+", title)
        if m:
            teams_from_title = [m.group(1).strip(), m.group(2).strip()]

        # tables: each map has a stats table; first table is the overall summary
        tables = soup.find_all("table")
        per_table = [self._parse_stats_table(t) for t in tables]
        # filter out empty/header-only tables
        per_table = [t for t in per_table if t["rows"]]

        # map names appear as h6 "Map N: <Map> <Mode> - Breakdown"
        map_headers = []
        for h in soup.find_all(["h6", "h5"]):
            txt = h.get_text(" ", strip=True)
            mm = re.match(r"Map\s+(\d+):\s*(.+?)\s+(Hardpoint|Search\s*&\s*Destroy|Control|Overload|SnD)\s*-\s*Breakdown", txt, re.IGNORECASE)
            if mm:
                map_headers.append({"map_num": int(mm.group(1)), "map": mm.group(2).strip(), "mode": mm.group(3).strip()})

        return {
            "match_id": match_id,
            "url": f"{BASE}/match/{match_id}",
            "title": self._clean_page_title(title),
            "event": event,
            "team_ids": team_ids,
            "teams": teams_from_title,
            "maps": map_headers,
            "stat_tables": per_table,
        }

    # turns a stats <table> into rows of player dicts, plus the team headers it ran under
    def _parse_stats_table(self, table) -> dict:
        headers = []
        for th in table.find_all("th"):
            headers.append(th.get_text(strip=True))

        rows = []
        current_team_id = None
        for tr in table.find_all("tr"):
            # team divider rows contain a /teams/{id} link and no real stat cells
            team_a = tr.find("a", href=TEAM_LINK)
            cells = tr.find_all("td")
            cell_text = [c.get_text(" ", strip=True) for c in cells]
            non_empty = [c for c in cell_text if c]

            if team_a and len(non_empty) <= 1:
                current_team_id = TEAM_LINK.search(team_a["href"]).group(1)
                continue

            # player rows have a /players link in the first cell
            player_a = tr.find("a", href=PLAYER_LINK)
            if not player_a or not cells:
                continue
            pmatch = PLAYER_LINK.search(player_a["href"])
            player = {
                "player_id": pmatch.group(1),
                "name": pmatch.group(2),
                "team_id": current_team_id,
            }
            # zip remaining columns with headers, skipping the player col
            stat_cells = cell_text[1:] if len(cell_text) > 1 else []
            stat_headers = headers[1:] if len(headers) > 1 else [f"col_{i}" for i in range(len(stat_cells))]
            for k, v in zip(stat_headers, stat_cells):
                player[k] = v
            rows.append(player)

        return {"headers": headers, "rows": rows}

    async def upcoming_and_recent_matches(self, limit: int = 20) -> list[dict]:
        # both pages embed the same match strip so /matches is canonical
        html = await self._fetch("/matches", ttl=60)
        items = self._parse_match_links(html)
        return items[:limit]

    async def event_overview(self, event_id: str) -> dict:
        html = await self._fetch(f"/events/{event_id}", ttl=300)
        soup = BeautifulSoup(html, "html.parser")

        # event pages render matches and teams client-side from __NEXT_DATA__
        script = soup.find("script", id="__NEXT_DATA__")
        if script:
            return self._parse_event_next_data(event_id, script.string)

        # fallback: minimal info from the HTML if __NEXT_DATA__ is missing
        title = (soup.find("title").text if soup.find("title") else "").strip()
        return {
            "event_id": event_id,
            "title": self._clean_page_title(title),
            "url": f"{BASE}/events/{event_id}",
            "teams": [],
            "matches": [],
        }

    def _parse_event_next_data(self, event_id: str, raw_json: str) -> dict:
        data = json.loads(raw_json)
        pp = data.get("props", {}).get("pageProps", {})
        event = pp.get("event", {})

        # build team lookup so we can resolve IDs in matches
        teams_list = pp.get("teams", [])
        team_lookup = {t["id"]: t for t in teams_list}
        teams_out = [
            {"team_id": str(t["id"]), "name": t.get("name")}
            for t in teams_list
        ]

        matches_out = []
        for m in pp.get("matches", []):
            t1 = team_lookup.get(m.get("team_1_id"), {})
            t2 = team_lookup.get(m.get("team_2_id"), {})
            matches_out.append({
                "match_id": str(m["id"]),
                "url": f"{BASE}/match/{m['id']}",
                "team_1": t1.get("name", "TBD"),
                "team_2": t2.get("name", "TBD"),
                "score": f"{m.get('team_1_score', 0)}-{m.get('team_2_score', 0)}",
                "status": m.get("status"),
                "datetime": m.get("datetime"),
            })

        return {
            "event_id": event_id,
            "title": event.get("name", ""),
            "url": f"{BASE}/events/{event_id}",
            "teams": teams_out,
            "matches": matches_out,
        }

    @staticmethod
    def _clean_page_title(title: str) -> str:
        for suffix in (" - Breaking Point", " | Call of Duty League Event"):
            title = title.replace(suffix, "")
        return title.strip()
