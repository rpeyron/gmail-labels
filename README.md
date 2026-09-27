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

## takeout-stats — companion tools

Standalone Python tools (no dependency on the app) to analyze Gmail Takeout `.mbox` exports:

| Tool | Purpose |
|---|---|
| `mbox-gen-html.py` | Render messages stats to JSON data for the HTML viewer |
| `mbox-gen-html.html` | Advanced statistics browser explorer: view, filter, sort, group mails statistics |
| `mbox-stats.py` | Basic statistics per year and Gmail label (count, size) — robust slow parser (`mailbox`) |
| `mbox-stats-fast.py` | Same basic statistics with a fast manual line-based parser for very large mbox files |

Typical run for the viewer:

```bash
python mbox-gen-html.py <mbox|maildir>...
python -m http.server 9000
# open http://localhost:9000/mbox-gen-html.html
```

Edit the `MBOX_FILE` path at the top of the stats scripts before running them.

## More

Mainly developed with IA (Copilot & Claude free plans)
- Engineering constraints: [AGENTS.md](AGENTS.md)
- Full requirements: [doc/requirements-functional.md](doc/requirements-functional.md), [doc/requirements-technical.md](doc/requirements-technical.md)
