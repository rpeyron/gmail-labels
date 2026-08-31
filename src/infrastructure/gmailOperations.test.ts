import { describe, expect, it, vi, beforeEach } from 'vitest';
import { applyRenameLabel, applyMergeLabels } from './gmailOperations';

const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('Gmail Operations', () => {
  beforeEach(() => {
    mockFetch.mockClear();
  });

  describe('applyRenameLabel', () => {
    it('successfully renames a label via Gmail API', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ id: 'label-123', name: 'New Name' }),
      });

      const result = await applyRenameLabel({
        labelId: 'label-123',
        newName: 'New Name',
        accessToken: 'token-abc',
      });

      expect(result.success).toBe(true);
      expect(mockFetch).toHaveBeenCalledWith(
        'https://gmail.googleapis.com/gmail/v1/users/me/labels/label-123',
        expect.objectContaining({
          method: 'PATCH',
          headers: expect.objectContaining({
            Authorization: 'Bearer token-abc',
          }),
        }),
      );
      expect(mockFetch).toHaveBeenCalledTimes(2);
    });

    it('verifies a child label rename using its complete Gmail label name', async () => {
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: async () => ({ id: 'label-123', name: 'Projects/Renamed' }),
        })
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: async () => ({ id: 'label-123', name: 'Projects/Renamed' }),
        });

      const result = await applyRenameLabel({
        labelId: 'label-123',
        newName: 'Projects/Renamed',
        accessToken: 'token-abc',
      });

      expect(result.success).toBe(true);
      expect(mockFetch.mock.calls[0][1]).toEqual(expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ name: 'Projects/Renamed' }),
      }));
      expect(mockFetch).toHaveBeenCalledTimes(2);
    });

    it('returns an error when the API call fails', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 404,
        text: async () => 'Label not found',
      });

      const result = await applyRenameLabel({
        labelId: 'nonexistent',
        newName: 'New Name',
        accessToken: 'token-abc',
      });

      expect(result.success).toBe(false);
      expect(result.error).toContain('404');
    });
  });

  describe('applyMergeLabels', () => {
    it('successfully merges labels by moving messages', async () => {
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: async () => ({
            messages: [{ id: 'msg-1' }, { id: 'msg-2' }],
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: async () => ({}),
        })
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: async () => ({ messages: [] }),
        });

      const result = await applyMergeLabels({
        sourceId: 'source-label',
        targetId: 'target-label',
        accessToken: 'token-abc',
      });

      expect(result.success).toBe(true);
      expect(mockFetch).toHaveBeenCalledTimes(3);
    });

    it('loads every message page before applying batches', async () => {
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: async () => ({ messages: [{ id: 'msg-1' }], nextPageToken: 'next-page' }),
        })
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          json: async () => ({ messages: [{ id: 'msg-2' }] }),
        })
        .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({}) })
        .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ messages: [] }) });

      const result = await applyMergeLabels({ sourceId: 'source-label', targetId: 'target-label', accessToken: 'token-abc' });

      expect(result.success).toBe(true);
      expect(mockFetch).toHaveBeenCalledTimes(4);
      expect(mockFetch.mock.calls[1][0]).toContain('pageToken=next-page');
    });

    it('handles empty label gracefully', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ messages: [] }),
      });

      const result = await applyMergeLabels({
        sourceId: 'empty-label',
        targetId: 'target-label',
        accessToken: 'token-abc',
      });

      expect(result.success).toBe(true);
    });
  });
});
