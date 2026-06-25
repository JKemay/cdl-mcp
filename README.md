# cdl-mcp

An [MCP](https://modelcontextprotocol.io) server that exposes **Call of Duty League** (CDL) match data, scraped from [breakingpoint.gg](https://breakingpoint.gg).

It lets an MCP-compatible client (such as Claude) look up upcoming and recent matches, detailed per-map and per-player match summaries, and event overviews.

## Features

- Upcoming and recent CDL matches
- Full match summaries with per-map and per-player stats
- Event overviews (teams and matches)
- Polite, cached HTTP access to breakingpoint.gg

## Repository layout

The MCP server package lives in the [`cdl-mcp/`](cdl-mcp/) subdirectory.

| Path | Description |
| --- | --- |
| [`cdl-mcp/`](cdl-mcp/) | The `cdl-mcp` Python package (server, scraper, cache) |
| [`cdl-mcp/README.md`](cdl-mcp/README.md) | Full installation, configuration, and usage documentation |
| [`cdl-mcp-DOCS.md`](cdl-mcp-DOCS.md) | Design and implementation notes |
| [`tests/`](tests/) | Unit tests |

## Documentation

See **[cdl-mcp/README.md](cdl-mcp/README.md)** for full installation, configuration, and usage instructions.

## Development

```bash
# install the package (from the package subdirectory) plus dev tools
pip install -e cdl-mcp
pip install ruff pytest

# lint
ruff check cdl-mcp tests

# run the tests
pytest
```

## License

Licensed under the terms in [LICENSE](LICENSE).
