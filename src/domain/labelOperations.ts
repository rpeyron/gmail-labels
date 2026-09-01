export type LabelNode = {
  id: string;
  name: string;
  mailCount?: number;
  isSystem?: boolean;
  children?: LabelNode[];
};

export type OperationMode = 'merge' | 'rename' | 'delete';

export type LabelOperation =
  | { type: 'merge'; sourceId: string; targetId: string; dryRun: boolean }
  | { type: 'rename'; targetId: string; newName: string; dryRun: boolean }
  | { type: 'delete'; targetId: string; dryRun: boolean };

export type LabelPlan = {
  operations: LabelOperation[];
  canApply: boolean;
  validationErrors: string[];
};

export type BuildLabelPlanInput = {
  labels: LabelNode[];
  selectedLabelIds: string[];
  targetLabelId: string;
  renameMap: Record<string, string>;
  dryRun: boolean;
  mode?: OperationMode;
};

const collectIds = (labels: LabelNode[]): string[] => {
  return labels.flatMap((label) => [label.id, ...collectIds(label.children ?? [])]);
};

export const flattenLabelTree = (labels: LabelNode[]) => {
  const flatten = (nodes: LabelNode[], depth = 0): Array<LabelNode & { depth: number }> => {
    return nodes.flatMap((node) => [
      { id: node.id, name: node.name, mailCount: node.mailCount, depth },
      ...flatten(node.children ?? [], depth + 1),
    ]);
  };

  return flatten(labels);
};

export const buildLabelPlan = ({
  labels,
  selectedLabelIds,
  targetLabelId,
  renameMap,
  dryRun,
  mode = 'merge',
}: BuildLabelPlanInput): LabelPlan => {
  const availableIds = new Set(collectIds(labels));
  const validationErrors: string[] = [];

  selectedLabelIds.forEach((labelId) => {
    if (!availableIds.has(labelId)) {
      validationErrors.push(`Selected label ${labelId} does not exist`);
    }
  });

  if (targetLabelId && !availableIds.has(targetLabelId)) {
    validationErrors.push(`Target label ${targetLabelId} does not exist`);
  }

  const operations: LabelOperation[] = [];

  if (mode === 'rename') {
    Object.entries(renameMap).forEach(([targetId, newName]) => {
      if (availableIds.has(targetId) && newName.trim()) {
        operations.push({ type: 'rename', targetId, newName: newName.trim(), dryRun });
      }
    });
  }

  if (mode === 'merge') {
    const renamedTargets = new Set(Object.keys(renameMap));

    selectedLabelIds.forEach((sourceId) => {
      if (
        availableIds.has(sourceId) &&
        targetLabelId &&
        availableIds.has(targetLabelId) &&
        sourceId !== targetLabelId &&
        !renamedTargets.has(sourceId)
      ) {
        operations.push({ type: 'merge', sourceId, targetId: targetLabelId, dryRun });
      }
    });
  }

  if (mode === 'delete') {
    selectedLabelIds.forEach((labelId) => {
      if (availableIds.has(labelId)) {
        operations.push({ type: 'delete', targetId: labelId, dryRun });
      }
    });
  }

  return {
    operations,
    canApply: validationErrors.length === 0,
    validationErrors,
  };
};
