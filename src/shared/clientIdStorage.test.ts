import { afterEach, describe, expect, it } from 'vitest';
import { getStoredClientId, setStoredClientId } from './clientIdStorage';

describe('clientIdStorage', () => {
  afterEach(() => {
    window.localStorage.clear();
  });

  it('returns the saved client id when it is present', () => {
    window.localStorage.setItem('gmail-label-manager.client-id', 'my-client-id');

    expect(getStoredClientId()).toBe('my-client-id');
  });

  it('persists a new client id and clears it when empty', () => {
    setStoredClientId('new-client-id');
    expect(window.localStorage.getItem('gmail-label-manager.client-id')).toBe('new-client-id');

    setStoredClientId('');
    expect(window.localStorage.getItem('gmail-label-manager.client-id')).toBeNull();
  });
});
