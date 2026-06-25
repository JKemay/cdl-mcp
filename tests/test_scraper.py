"""Unit tests for the pure parsing helpers in cdl_mcp.scraper.BPScraper.

These exercise functions that do no network I/O. BPScraper.__init__ only
constructs an httpx client and an in-memory cache, so it is safe to build
in a test without touching the network.
"""

from cdl_mcp.scraper import BPScraper


def make_scraper() -> BPScraper:
    return BPScraper()


# ---------------------------------------------------------------------------
# _parse_match_link_text
# ---------------------------------------------------------------------------


def test_parse_match_link_text_extracts_relative_time():
    scraper = make_scraper()
    text = "~10 hours CDL Minor 2 Tournament Riyadh Falcons Riyadh Falcons 0"
    result = scraper._parse_match_link_text(text)

    assert result["when"] == "~10 hours"
    assert result["blurb"] == "CDL Minor 2 Tournament Riyadh Falcons Riyadh Falcons 0"


def test_parse_match_link_text_handles_live():
    scraper = make_scraper()
    result = scraper._parse_match_link_text("LIVE OpTic Texas vs Atlanta FaZe")

    assert result["when"] == "LIVE"
    assert result["blurb"] == "OpTic Texas vs Atlanta FaZe"


def test_parse_match_link_text_handles_tbd():
    scraper = make_scraper()
    result = scraper._parse_match_link_text("TBD CDL Major Final")

    assert result["when"] == "TBD"
    assert result["blurb"] == "CDL Major Final"


def test_parse_match_link_text_no_prefix_returns_full_blurb():
    scraper = make_scraper()
    text = "CDL Championship Weekend bracket reset"
    result = scraper._parse_match_link_text(text)

    assert result["when"] == ""
    assert result["blurb"] == text


def test_parse_match_link_text_singular_hour():
    scraper = make_scraper()
    result = scraper._parse_match_link_text("~1 hour CDL Qualifiers")

    assert result["when"] == "~1 hour"
    assert result["blurb"] == "CDL Qualifiers"


# ---------------------------------------------------------------------------
# _clean_page_title
# ---------------------------------------------------------------------------


def test_clean_page_title_strips_breaking_point_suffix():
    assert (
        BPScraper._clean_page_title("OpTic Texas vs Atlanta FaZe - Breaking Point")
        == "OpTic Texas vs Atlanta FaZe"
    )


def test_clean_page_title_strips_event_suffix():
    assert (
        BPScraper._clean_page_title(
            "Major III | Call of Duty League Event"
        )
        == "Major III"
    )


def test_clean_page_title_trims_whitespace():
    assert BPScraper._clean_page_title("   Some Title   ") == "Some Title"


def test_clean_page_title_no_known_suffix_is_unchanged():
    assert BPScraper._clean_page_title("Plain Title") == "Plain Title"
