import { describe, expect, it } from 'vitest';
import { buildLabelPlan, flattenLabelTree } from './labelOperations';

describe('buildLabelPlan', () => {
  it('creates a merge plan when merge mode is active', () => {
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
      mode: 'merge',
    });

    expect(plan.operations).toHaveLength(2);
    expect(plan.operations[0]).toMatchObject({ type: 'merge', sourceId: 'work-archive', targetId: 'work' });
    expect(plan.operations[1]).toMatchObject({ type: 'merge', sourceId: 'personal', targetId: 'work' });
    expect(plan.canApply).toBe(true);
  });

  it('creates a rename plan when rename mode is active', () => {
    const labels = [{ id: 'work', name: 'Work' }];

    const plan = buildLabelPlan({
      labels,
      selectedLabelIds: [],
      targetLabelId: '',
      renameMap: { work: 'Career' },
      dryRun: true,
      mode: 'rename',
    });

    expect(plan.operations).toHaveLength(1);
    expect(plan.operations[0]).toMatchObject({ type: 'rename', targetId: 'work', newName: 'Career' });
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
      mode: 'merge',
    });

    expect(plan.canApply).toBe(false);
    expect(plan.validationErrors).toContain('Selected label missing does not exist');
    expect(plan.validationErrors).toContain('Target label unknown does not exist');
  });

  it('does not complain when no source is selected in merge mode', () => {
    const labels = [{ id: 'work', name: 'Work' }];

    const plan = buildLabelPlan({
      labels,
      selectedLabelIds: [],
      targetLabelId: 'work',
      renameMap: {},
      dryRun: true,
      mode: 'merge',
    });

    expect(plan.operations).toEqual([]);
    expect(plan.validationErrors).toEqual([]);
    expect(plan.canApply).toBe(true);
  });

  it('allows merging a child source into its parent target', () => {
    const labels = [{ id: 'projects', name: 'Projects', children: [{ id: 'archive', name: 'Archive', mailCount: 12 }] }];

    const plan = buildLabelPlan({
      labels,
      selectedLabelIds: ['archive'],
      targetLabelId: 'projects',
      renameMap: {},
      dryRun: true,
      mode: 'merge',
    });

    expect(plan.operations).toEqual([{ type: 'merge', sourceId: 'archive', targetId: 'projects', dryRun: true }]);
    expect(plan.validationErrors).toEqual([]);
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
