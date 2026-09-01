const CLIENT_ID_STORAGE_KEY = 'gmail-label-manager.client-id';

export const getStoredClientId = (): string => {
  if (typeof window === 'undefined') {
    return '';
  }

  return window.localStorage.getItem(CLIENT_ID_STORAGE_KEY) ?? '';
};

export const setStoredClientId = (value: string): void => {
  if (typeof window === 'undefined') {
    return;
  }

  const trimmedValue = value.trim();

  if (!trimmedValue) {
    window.localStorage.removeItem(CLIENT_ID_STORAGE_KEY);
    return;
  }

  window.localStorage.setItem(CLIENT_ID_STORAGE_KEY, trimmedValue);
};
