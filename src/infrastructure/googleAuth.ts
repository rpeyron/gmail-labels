export const GOOGLE_SCOPES = 'https://www.googleapis.com/auth/gmail.labels https://www.googleapis.com/auth/gmail.modify';

type GoogleTokenClient = {
  requestAccessToken: (options?: { prompt?: string }) => void;
};

type GoogleTokenResponse = {
  access_token?: string;
  error?: string;
};

declare global {
  interface Window {
    google?: {
      accounts?: {
        oauth2?: {
          initTokenClient: (config: {
            client_id: string;
            scope: string;
            callback: (response: GoogleTokenResponse) => void;
          }) => GoogleTokenClient;
        };
      };
    };
  }
}

const loadScript = (): Promise<void> => {
  if (typeof window === 'undefined') {
    return Promise.reject(new Error('Google auth is only available in the browser.'));
  }

  if (window.google?.accounts?.oauth2?.initTokenClient) {
    return Promise.resolve();
  }

  return new Promise((resolve, reject) => {
    const existingScript = document.querySelector('script[data-google-auth]');
    if (existingScript) {
      existingScript.addEventListener('load', () => resolve(), { once: true });
      existingScript.addEventListener('error', () => reject(new Error('Unable to load Google Identity Services.')), { once: true });
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.defer = true;
    script.setAttribute('data-google-auth', 'true');
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('Unable to load Google Identity Services.'));
    document.head.appendChild(script);
  });
};

export const requestGoogleAccessToken = async (clientId: string): Promise<string> => {
  if (!clientId.trim()) {
    throw new Error('Please provide a Google OAuth client ID.');
  }

  await loadScript();

  const initTokenClient = window.google?.accounts?.oauth2?.initTokenClient;
  if (!initTokenClient) {
    throw new Error('Google Identity Services is not available in this environment.');
  }

  return new Promise((resolve, reject) => {
    const tokenClient = initTokenClient({
      client_id: clientId,
      scope: GOOGLE_SCOPES,
      callback: (response) => {
        if (response.error) {
          reject(new Error(response.error));
        } else if (response.access_token) {
          resolve(response.access_token);
        } else {
          reject(new Error('Google did not return an access token.'));
        }
      },
    });

    tokenClient.requestAccessToken({ prompt: 'consent' });
  });
};
