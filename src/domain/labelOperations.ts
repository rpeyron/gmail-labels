export type LabelNode = {
  id: string;
  name: string;
  mailCount?: number;
  children?: LabelNode[];
};

export type LabelOperation =
  | { type: 'merge'; sourceId: string; targetId: string; dryRun: boolean }
  | { type: 'rename'; targetId: string; newName: string; dryRun: boolean };

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
};

const collectIds = (labels: LabelNode[]): string[] => {
  return labels.flatMap((label) => [label.id, ...collectIds(label.children ?? [])]);
};

const isDescendantOf = (labels: LabelNode[], sourceId: string, targetId: string): boolean => {
  const visit = (nodes: LabelNode[]): boolean => {
    return nodes.some((node) => {
      if (node.id === sourceId) {
        return false;
      }
      if (node.id === targetId) {
        return (node.children ?? []).some((child) => child.id === sourceId || isDescendantOf([child], sourceId, targetId));
      }
      return visit(node.children ?? []);
    });
  };

  return visit(labels);
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
}: BuildLabelPlanInput): LabelPlan => {
  const availableIds = new Set(collectIds(labels));
  const validationErrors: string[] = [];

  selectedLabelIds.forEach((labelId) => {
    if (!availableIds.has(labelId)) {
      validationErrors.push(`Selected label ${labelId} does not exist`);
    }
  });

  if (!availableIds.has(targetLabelId)) {
    validationErrors.push(`Target label ${targetLabelId} does not exist`);
  }

  const operations: LabelOperation[] = [];

  Object.entries(renameMap).forEach(([targetId, newName]) => {
    if (availableIds.has(targetId)) {
      operations.push({ type: 'rename', targetId, newName, dryRun });
    }
  });

  const renamedTargets = new Set(Object.keys(renameMap));

  selectedLabelIds.forEach((sourceId) => {
    if (
      availableIds.has(sourceId) &&
      availableIds.has(targetLabelId) &&
      sourceId !== targetLabelId &&
      !renamedTargets.has(sourceId) &&
      !isDescendantOf(labels, sourceId, targetLabelId)
    ) {
      operations.push({ type: 'merge', sourceId, targetId: targetLabelId, dryRun });
    }
  });

  return {
    operations,
    canApply: validationErrors.length === 0,
    validationErrors,
  };
};
