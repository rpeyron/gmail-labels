![AI Generated](https://raw.githubusercontent.com/rpeyron/rpeyron/master/images/badges/badge-ia.svg)

# Gmail Label Manager

Web app to preview and apply Gmail label operations safely: merge, rename, delete, filter — in a single tree view.

## Features

- Unified label tree with nested hierarchy, alphabetical sorting (system labels last)
- Merge selected labels into a target label, rename inline, delete empty labels only
- Operation summary with real label paths and live validation before execution
- Preview planned tasks (dry run) before running them
- Filter by name (auto-applied after 400 ms) with automatic expansion of matches
- Select all visible labels in one click; double-click selects all labels with the same name
- Sticky parent path while scrolling; open a label in Gmail in a new window
- Mail counts per label, refreshable individually or for all visible rows
- Demo mode (built-in dataset, no Google account) and Google mode (live Gmail API)
- System labels are read-only; test-only labels are hidden

## Quick start

Requires Node.js 18+.

```bash
npm install
npm run dev
```

Open http://localhost:5173 and switch to **Demo** mode — no Google account needed.

## Google account mode

1. In [Google Cloud Console](https://console.cloud.google.com/): create/select a project, enable the **Gmail API**, create an **OAuth 2.0 Client ID** (Web application), and add `http://localhost:5173` to **Authorized JavaScript origins**.
2. Add every Gmail address you'll use as a test user (**Google Auth platform > Audience > Test users**) while the consent screen is in Testing status.
3. In the app: select **Google** mode → paste the Client ID → **Connect Google account** → authorize → review the summary → **Run**.

Notes: test-mode refresh tokens expire after ~7 days (sign in again as needed); accounts not listed as test users get `access_denied`.

## Commands

| Command | Description |
|---|---|
| `npm run dev` | Dev server |
| `npm run build` | Production build |
| `npm test` | Run tests |

## stats — companion tools

Standalone Python tools (no dependency on the app) to analyze Gmail Takeout `.mbox` exports:

| Tool | Purpose |
|---|---|
| `generate.py` | Render messages stats to JSON data for the HTML viewer |
| `app.html` | Advanced statistics browser explorer: view, filter, sort, group mails statistics |
| `start-web.py` | Local HTTP server for the viewer (opens browser; `--no-browser` to disable) |
| `json-mbox-diff.py` | Diff two mails.json synthesis files |
| `json-mbox-enrich.py` | Add/refresh mid_dup and mid_invalid fields on mails.json files |
| `mbox-stats.py` | Basic statistics per year and Gmail label (count, size) — robust slow parser (`mailbox`) |
| `mbox-stats-fast.py` | Same basic statistics with a fast manual line-based parser for very large mbox files |

Typical run for the viewer:

```bash
python generate.py [-o OUT] <mbox|maildir>...   # bare name or name.ext -> data/; with a directory -> that directory; .json appended if missing
python start-web.py            # opens http://localhost:9000/ (use --no-browser to disable)
```

Edit the `MBOX_FILE` path at the top of the stats scripts before running them.

## tools — mailbox maintenance

Standalone Python utilities for mbox/sbd mail-store trees (e.g. Thunderbird, Netscape):

| Tool | Purpose |
|---|---|
| `tools/clean-empty-mbox/clean_empty_mbox.py` | Recursively delete empty (0-byte) mboxes and their `.msf` from an mbox/sbd tree, then remove emptied `.sbd` folders (deepest-first); empty parent mboxes are kept while their `.sbd` still has children; supports `--dry-run` |
| `tools/mbox-merge/merge_mbox.py` | Merge several mbox/sbd mail-store trees into one output directory, concatenating mboxes sharing the same relative path and preserving the folder layout (`.msf`/`.html`/`.log` ignored) |
| [`tools/mbox-encoding/mbox-encoding-fix.py`](tools/mbox-encoding/README.md) | Check and repair mbox/sbd encoding issues |
| `tools/snm_tools/snm_to_mbox.py` | Convert a legacy Netscape 4 `.snm` mailbox to standard mbox format |

## More

Mainly developed with IA (Copilot & Claude free plans)
- Engineering constraints: [AGENTS.md](AGENTS.md)
- Full requirements: [doc/requirements-functional.md](doc/requirements-functional.md), [doc/requirements-technical.md](doc/requirements-technical.md)
