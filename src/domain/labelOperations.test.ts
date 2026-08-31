import { describe, expect, it } from 'vitest';
import { buildLabelPlan, flattenLabelTree } from './labelOperations';

describe('buildLabelPlan', () => {
  it('creates a merge plan and a rename plan from selected labels', () => {
    const labels = [
      { id: 'work', name: 'Work', children: [{ id: 'work-archive', name: 'Archive' }] },
      { id: 'personal', name: 'Personal' },
    ];

    const plan = buildLabelPlan({
      labels,
      selectedLabelIds: ['work-archive', 'personal'],
      targetLabelId: 'work',
      renameMap: { work: 'Career' },
      dryRun: true,
    });

    expect(plan.operations).toHaveLength(2);
    expect(plan.operations[0]).toMatchObject({ type: 'rename', targetId: 'work', newName: 'Career' });
    expect(plan.operations[1]).toMatchObject({ type: 'merge', sourceId: 'personal', targetId: 'work' });
    expect(plan.canApply).toBe(true);
  });

  it('rejects invalid merge targets and missing labels', () => {
    const labels = [{ id: 'work', name: 'Work' }];

    const plan = buildLabelPlan({
      labels,
      selectedLabelIds: ['missing'],
      targetLabelId: 'unknown',
      renameMap: {},
      dryRun: true,
    });

    expect(plan.canApply).toBe(false);
    expect(plan.validationErrors).toContain('Selected label missing does not exist');
    expect(plan.validationErrors).toContain('Target label unknown does not exist');
  });
});

describe('flattenLabelTree', () => {
  it('flattens the label hierarchy into a simple list', () => {
    const labels = [
      {
        id: 'work',
        name: 'Work',
        mailCount: 42,
        children: [{ id: 'archive', name: 'Archive', mailCount: 8 }],
      },
      { id: 'personal', name: 'Personal', mailCount: 15 },
    ];

    expect(flattenLabelTree(labels)).toEqual([
      { id: 'work', name: 'Work', depth: 0, mailCount: 42 },
      { id: 'archive', name: 'Archive', depth: 1, mailCount: 8 },
      { id: 'personal', name: 'Personal', depth: 0, mailCount: 15 },
    ]);
  });
});
