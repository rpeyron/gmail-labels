import { describe, expect, it } from 'vitest';
import { loadGmailLabels, normalizeGmailApiLabels } from './gmailApi';

describe('loadGmailLabels', () => {
  it('returns demo data when demo mode is selected', async () => {
    const labels = await loadGmailLabels('demo');

    expect(labels).toHaveLength(6);
    expect(labels[0].name).toBe('Projects');
    expect(labels[1].name).toBe('Personal');
  });

  it('reports an authentication error when Gmail mode is unavailable', async () => {
    await expect(loadGmailLabels('gmail')).rejects.toThrow('Unable to fetch Gmail labels (401)');
  });

  it('builds a nested tree from slash-separated Gmail label names', () => {
    const labels = normalizeGmailApiLabels([
      { id: 'work', name: 'Work', type: 'user' },
      { id: 'work/projects', name: 'Work/Projects', type: 'user', messagesTotal: 12 },
      { id: 'work/projects/launch', name: 'Work/Projects/Launch', type: 'user', messagesTotal: 4 },
      { id: 'personal', name: 'Personal', type: 'user' },
    ]);

    expect(labels[0].name).toBe('Work');
    expect(labels[0].children?.[0].id).toBe('work/projects');
    expect(labels[0].children?.[0].mailCount).toBe(12);
    expect(labels[0].children?.[0].name).toBe('Projects');
    expect(labels[0].children?.[0].children?.[0].name).toBe('Launch');
  });
});
