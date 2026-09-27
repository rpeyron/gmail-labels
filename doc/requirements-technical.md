# Requirements — Technical

Engineering constraints for this project. Source: `.github/copilot.json`.

## Context

- Include: `src/`
- Exclude: `dist/`, `node_modules/`, `tmp/`

## Stack

- Language: TypeScript (strict mode, `no implicit any`)
- UI: React 18
- Build: Vite
- Test: Vitest (+ Testing Library, jsdom)
- Tree rendering: react-arborist
- Architecture: clean

### Architecture rules

- Pure functions in core logic (`src/domain/`).
- Side effects isolated in adapters (`src/infrastructure/`).
- Layer layout:
  - `src/app/` — bootstrap
  - `src/domain/` — pure label-operation logic
  - `src/features/` — React UI
  - `src/infrastructure/` — Gmail API, auth, demo data
  - `src/shared/` — cross-cutting utilities (e.g. client ID storage)
  - `src/test/` — test setup

## Commands

```bash
npm install
npm run dev      # dev server (http://localhost:5173)
npm run build    # tsc -b && vite build
npm run preview  # preview production build
npm test         # vitest run
```

## Logic — Gmail API

- Use the official Gmail API only for live data.
- Required scopes: `https://www.googleapis.com/auth/gmail.labels`, `https://www.googleapis.com/auth/gmail.modify`.
- Keep label tree updates consistent with the latest Gmail response.
- Refresh affected mail counts after each successful operation.
- Refresh visible label mail counts in parallel when the `Mails` header is activated.
- Retry transient failures when appropriate.
- Handle stale deleted labels gracefully by ignoring 404 responses.

## Logic — collision handling

- Show the real paths in the summary before execution.
- Keep rename target names aligned with the actual label being renamed.

## Robustness

- Scale: support practical Gmail label trees in normal mailbox usage; filtering and bulk selection must not disrupt layout.
- Performance:
  - Batch refresh of affected labels.
  - Avoid unnecessary Gmail detail requests for deleted or collapsed labels.
  - Keep progress feedback visible during execution.

## Tests

- Unit:
  - normalization of Gmail labels
  - system label protection
  - test-label filtering
  - auth errors and API responses
- Integration:
  - demo and Google modes
  - operation summaries
  - refresh flows after actions
- Coverage: project-level regression checks maintained.
