# Gmail Label Manager

A Vite + React + TypeScript app for safely previewing and applying Gmail label operations.

## What the app does

- Manage Gmail labels in a single tree view
- Switch between a demo dataset and a real Google account
- Filter labels by name
- Select all visible, selectable labels from the Source column with one click
- Merge selected labels into a target label
- Rename labels inline
- Delete empty labels only
- Prevent actions on system labels
- Hide test-only labels from Google account data
- Show a loading spinner while Gmail labels are being fetched
- Persist the Google OAuth client ID locally in the browser
- Refresh mail counts after label operations and skip deleted labels safely

## Current UI behavior

- Compact mode toggle: Demo / Google
- Google auth status is displayed in the connection box
- A floating setup panel opens from the Google button when needed
- The active mode is visually emphasized with red for Demo and green for Google
- The operation summary shows the real selected label paths
- The tree remains clean and compact without outer frames around the operation block or label tree

## Features checklist

- Unified label tree with nested hierarchy
- Label count display
- Source selection by checkbox
- Target selection by radio
- Rename and delete actions
- Operation summary at top
- Validation messages for invalid operations
- Demo mode and live Google mode
- Safe handling of Gmail API 404s for deleted labels
- Google API transient-error handling and refresh logic

## Development

```bash
npm install
npm run dev
```

## Production build

```bash
npm run build
```

## Tests

```bash
npm test
```

## Using Google account mode

### 1) Create a Google OAuth client ID

1. Open the [Google Cloud Console](https://console.cloud.google.com/)
2. Create or select a project
3. Enable the Gmail API
4. Create an OAuth 2.0 Client ID
5. Choose a Web application
6. Add your local origin, for example: `http://localhost:5173`
7. Copy the generated Client ID

### 2) Use it in the app

1. Select the Google mode
2. Paste the Client ID in the popup field
3. Click Connect Google account
4. Authorize the app to access Gmail labels
5. Review the planned changes and run the operation when ready

## Notes

- The app uses the Gmail API with OAuth for real label operations
- The required scopes are `gmail.labels` and `gmail.modify`
- In demo mode, the app uses a built-in dataset and does not require a Google account
- System labels are intentionally disabled and cannot be edited
- Test labels are filtered out to avoid noise in the Gmail tree
- Deleted labels are skipped during refresh if Gmail returns a 404
