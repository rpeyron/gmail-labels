# Requirements — Functional

End-user Gmail label management UI.

## Delivery scope

Priority order:

1. Google account mode and demo mode parity
2. Merge, rename, and delete workflows
3. Safe operation summary and live validation
4. Preview planned tasks before execution
5. Compact and clear label-tree UX

## Gmail label management

- Display nested Gmail label hierarchy.
- Sort labels alphabetically at every tree level, case-insensitively, with system labels last.
- Source selection for visible, selectable labels.
- With an empty filter: activating the Source header clears all source selections if any are selected; with none selected it selects all visible selectable labels.
- Double-click a label to select every non-system label with exactly the same name; selection is additive and keeps existing source selections.
- Single target selection (radio).
- Rename labels inline, with the current label path shown in the summary.
- Delete labels only when they are empty and not system labels.
- Block system labels from all action flows.
- Filter labels by name, debounced at 400 ms before applying.
- Expand every folder required to make all filtered matches visible.
- When filtering, keep matching folders and leaves, and dim non-matching parents required for matching paths.
- Hide test-only labels from Google results.
- Refresh mail counts after affected operations.
- Refresh mail counts for every visible label row when the `Mails` column header is activated.
- Refresh a single label count by clicking its `Mails` cell, including `—` values not loaded yet.
- Clicking a directory name does not change expansion; only its `▾`/`▸` control toggles it.
- Keep the current parent path sticky while scrolling, including when filtered; clicking a sticky parent scrolls until its row is the first visible tree entry.
- Loading spinner while Gmail labels are fetched.

## Demo mode

Purpose: allow UI testing without a Google account.

- Load a built-in dataset of fake Gmail labels.
- Include deep and repeated-name branches to test sticky parents, filtering, expand/collapse, and multi-selection.
- Include repeated Inbox and Archive labels across branches for exact-name selection tests.
- Include representative system labels to test read-only behavior and ordering.
- Hide demo mail counts initially; hydrate them locally on demand to match Google mode.
- Keep the UI fully interactive in demo mode.
- Clearly indicate when running without a live Google session.

## Mode parity

- Common operation model across demo and Google modes.
- Refresh state after successful operations.
- Keep operation summary and validation in sync.
- Ignore deleted labels when Gmail returns a 404 during refresh.
- Demo mode: simulate label and mail-count updates locally.
- Google mode: execute Gmail API operations and refresh label data from the API.
- Never display stale label data from a deleted Gmail label.

## UI

Style: compact minimalistic.

### Interface

- Single unified tree with a compact operation summary and top-right control panel.
- Components:
  - Mode toggle: Demo / Google with strong active state colors (red = Demo, green = Google).
  - Connection status box: connection state and user identity.
  - Google popup: floating configuration panel anchored to the Google button.
  - Operation summary (top): source, target, operation direction, real selected label paths.
  - Label hierarchy: tree with Label, Mails, Source, Target, Actions columns.
  - Source selection: one click on visible selectable labels.
  - Target selection: single radio button.
  - Actions column: inline rename and delete.
  - Gmail link action: open the full label path in a new Gmail search window.
  - Tree toolbar: filter, expand all, collapse all, refresh.
  - Mail-count refresh: header refreshes visible rows; cell refreshes one label.
  - Operation preview: same task rows as Run, zero progress, no side effects.
  - Validation errors: display invalid operation states.
- Tree remains clean and compact: no outer frames around the operation block or label tree.

### Tree view

- Indentation based on depth; 5 columns: Label, Mails, Source, Target, Actions.
- Label icon before each label name.
- Expand/collapse controls per node and global expand/collapse.
- Preserve each node's expanded state when mail counts or label data update (including while filtering).
- Sticky parent path bar: includes rendered bar height when determining ancestors; geometry stable, no flicker on path change.
- Source selection respects the active filter and excludes system labels.
- `Mails` header refreshes counts for rendered rows only, respecting filter and expanded branches.
- Delete disabled for system labels and non-empty labels.
- Path display uses `/` separators.

### Dry-run

- Show planned operations before execution.
- Preview creates one pending task row per executable operation, processed count zero.
- No side effects before confirmation.
- Display progress for the active operation.

## Authentication (user-facing)

- Google OAuth Client ID entered in-app, persisted in browser session storage.
- Re-open the Google setup panel when needed; allow sign-out and reconnect.
- Sign-in flow: select Google mode → paste Client ID → Connect → authorize Gmail label access.

### Credential setup (Google Cloud Console)

- Provider: Google Cloud Console; API: Gmail API; application type: Web application.
- Authorized JavaScript origins: `http://localhost:5173`.
- Configure the OAuth consent screen audience before sign-in.
- Add every Gmail address used for testing under **Google Auth platform > Audience > Test users** (the addresses in docs are examples only).
- Test-mode refresh tokens can expire after seven days; sign in again when necessary.

## Safety

- Never log sensitive Gmail data.
- Require explicit user intent before applying label changes.
- Gracefully skip deleted labels on missing-entity (404) responses.
- Keep system labels read-only.

## Goals

- Robust Gmail label management experience.
- Compact, clear UI for everyday operations.
- Safe Google-account workflows with reliable refreshes.
- Documentation and behavior aligned with the shipped product.
