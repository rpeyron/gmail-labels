import { describe, expect, it } from 'vitest';
import { loadGmailLabels, normalizeGmailApiLabels } from './gmailApi';

describe('loadGmailLabels', () => {
  it('returns demo data when demo mode is selected', async () => {
    const labels = await loadGmailLabels('demo');

    expect(labels).toHaveLength(3);
    expect(labels[0].name).toBe('Projects');
    expect(labels[1].name).toBe('Personal');
  });

  it('returns a fallback dataset when Gmail mode is unavailable', async () => {
    const labels = await loadGmailLabels('gmail');

    expect(labels).toHaveLength(3);
    expect(labels[0].name).toBe('Projects');
  });

  it('builds a nested tree from slash-separated Gmail label names', () => {
    const labels = normalizeGmailApiLabels([
      { id: 'work', name: 'Work', type: 'user' },
      { id: 'work/projects', name: 'Work/Projects', type: 'user' },
      { id: 'work/projects/launch', name: 'Work/Projects/Launch', type: 'user' },
      { id: 'personal', name: 'Personal', type: 'user' },
    ]);

    expect(labels[0].name).toBe('Work');
    expect(labels[0].children?.[0].name).toBe('Projects');
    expect(labels[0].children?.[0].children?.[0].name).toBe('Launch');
  });
});
