import type { GmailDataMode } from '../../infrastructure/gmailApi';

type DataSourcePanelProps = {
  dataMode: GmailDataMode;
  accessToken: string;
  userEmail: string;
  applying: boolean;
  clientId: string;
  googleConfigOpen: boolean;
  onDataModeChange: (mode: GmailDataMode) => void;
  onClientIdChange: (clientId: string) => void;
  onConfigToggle: () => void;
  onSignIn: () => void;
  onSignOut: () => void;
};

const DataSourcePanel = ({
  dataMode,
  accessToken,
  userEmail,
  applying,
  clientId,
  googleConfigOpen,
  onDataModeChange,
  onClientIdChange,
  onConfigToggle,
  onSignIn,
  onSignOut,
}: DataSourcePanelProps) => (
  <div className="mode-panel">
    <div className="source-toggle" role="tablist" aria-label="Select data source">
      <button type="button" role="tab" aria-selected={dataMode === 'demo'} className={`source-toggle-option ${dataMode === 'demo' ? 'source-toggle-option-demo-active' : ''}`} onClick={() => onDataModeChange('demo')}>
        Demo
      </button>
      <button type="button" role="tab" aria-selected={dataMode === 'gmail'} className={`source-toggle-option ${dataMode === 'gmail' ? 'source-toggle-option-google-active' : ''}`} onClick={() => onDataModeChange('gmail')}>
        Google
      </button>
    </div>

    {dataMode === 'gmail' ? (
      <div className="connection-status-wrap">
        <div className="connection-status-box">
          <span className={`oauth-status ${accessToken ? 'oauth-status-connected' : ''}`}>
            {accessToken ? 'Connected' : 'Not connected'}
          </span>
          {accessToken && userEmail ? <span className="account-identity" title={userEmail}><span className="account-identity-icon" aria-hidden="true">◉</span>{userEmail}</span> : null}
          {!accessToken ? (
            <button type="button" className="connection-action-button" onClick={onConfigToggle} aria-expanded={googleConfigOpen} aria-controls="google-config-panel">
              {googleConfigOpen ? 'Hide' : 'Connect'}
            </button>
          ) : (
            <button type="button" className="connection-action-button secondary" onClick={onSignOut} disabled={applying}>Sign out</button>
          )}
        </div>
        {!accessToken && googleConfigOpen ? (
          <div id="google-config-panel" className="oauth-login-panel floating-panel">
            <label className="oauth-label" htmlFor="google-client-id">Client ID</label>
            <input id="google-client-id" className="token-input" value={clientId} onChange={(event) => onClientIdChange(event.target.value)} placeholder="Google OAuth Client ID" aria-label="Google OAuth client ID" disabled={applying} />
            <button onClick={onSignIn} disabled={applying} className="sign-in-button">{applying ? 'Connecting…' : 'Connect Google account'}</button>
          </div>
        ) : null}
      </div>
    ) : <span className="oauth-status">Local demo</span>}
  </div>
);

export default DataSourcePanel;
