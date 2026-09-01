# Gmail Labels

A Vite + React + TypeScript application for managing Gmail labels safely.

## Features

- View a unified label hierarchy with dedicated Source and Target columns
- Expand, collapse, and expand all nodes in the hierarchy from the tree UI
- Select multiple source labels via checkboxes
- Select a single target label via radio button
- Preview source paths and target path in the summary at top
- Rename labels using inline action buttons with a pencil icon
- Delete labels only when they have 0 messages
- Preview planned changes in dry-run mode
- Validate merge targets and missing labels
- Real Gmail API integration with OAuth authentication
- Demo mode for testing without a Google account

## Interface

The application features a single unified tree with:
- **Label column**: Shows the full label hierarchy with depth indentation and a label icon
- **Mails column**: Displays the message count for each label
- **Source column**: Checkbox to select labels as sources for merge operations
- **Target column**: Radio button to select a single target label for merging
- **Actions column**: Rename and delete buttons with icon-based actions
- **Operation Summary** (top): Shows sources paths (with / separator), target path, and operation count

## Development

```bash
npm install
npm run dev
```

## Build

```bash
npm run build
```

## Using Gmail Account Mode

### Step 1: Get a Google OAuth Client ID

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Gmail API:
   - Go to **APIs & Services > Enabled APIs & services**
   - Click **+ ENABLE APIS AND SERVICES**
   - Search for "Gmail API" and enable it
4. Create an OAuth 2.0 credential:
   - Go to **APIs & Services > Credentials**
   - Click **+ CREATE CREDENTIALS** > **OAuth 2.0 Client ID**
   - Choose "Web application"
   - Add authorized JavaScript origins (e.g., http://localhost:5173` for development)
   - Save your **Client ID**

### Step 2: Use in the App

1. Select "Google account" mode from the dropdown
2. Paste your OAuth Client ID into the field
3. Click "Sign in with Google"
4. Authorize the app to access your Gmail labels
5. Preview your changes and apply them when ready

## Notes

- The app requires `gmail.labels` and `gmail.modify` OAuth scopes
- Changes are applied only after explicit user confirmation
- In demo mode, no Google account is required and all data is simulated
- The app uses batching for large label operations to respect API limits
