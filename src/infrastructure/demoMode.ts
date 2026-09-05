import type { LabelNode, LabelOperation } from '../domain/labelOperations';

export const demoLabels: LabelNode[] = [
  {
    id: 'demo-projects',
    name: 'Projects',
    mailCount: 184,
    children: [
      {
        id: 'demo-projects-archive',
        name: 'Archive',
        mailCount: 76,
        children: [{ id: 'demo-projects-archive-2024', name: '2024', mailCount: 32 }],
      },
      {
        id: 'demo-projects-ongoing',
        name: 'Ongoing',
        mailCount: 108,
        children: [{ id: 'demo-projects-ongoing-alpha', name: 'Alpha', mailCount: 41 }],
      },
    ],
  },
  {
    id: 'demo-personal',
    name: 'Personal',
    mailCount: 96,
    children: [
      {
        id: 'demo-personal-travel',
        name: 'Travel',
        mailCount: 53,
        children: [{ id: 'demo-personal-travel-2025', name: '2025', mailCount: 19 }],
      },
      {
        id: 'demo-personal-family',
        name: 'Family',
        mailCount: 43,
      },
    ],
  },
  {
    id: 'demo-admin',
    name: 'Admin',
    mailCount: 67,
    children: [{ id: 'demo-admin-invoices', name: 'Invoices', mailCount: 21 }],
  },
  {
    id: 'demo-empty-projects',
    name: 'Empty projects',
    mailCount: 0,
    children: [{ id: 'demo-empty-projects-archived', name: 'Archived', mailCount: 0 }],
  },
  {
    id: 'demo-empty-ops',
    name: 'Ops backlog',
    mailCount: 0,
  },
  {
    id: 'demo-empty-archive',
    name: 'Archive room',
    mailCount: 0,
  },
];

const findNodeById = (nodes: LabelNode[], id: string): LabelNode | null => {
  for (const node of nodes) {
    if (node.id === id) {
      return node;
    }
    const childMatch = findNodeById(node.children ?? [], id);
    if (childMatch) {
      return childMatch;
    }
  }
  return null;
};

const updateNodeById = (nodes: LabelNode[], id: string, updater: (node: LabelNode) => LabelNode): LabelNode[] =>
  nodes.map((node) => {
    if (node.id === id) {
      return updater(node);
    }
    if ((node.children ?? []).length > 0) {
      return { ...node, children: updateNodeById(node.children ?? [], id, updater) };
    }
    return node;
  });

const hasDescendantId = (nodes: LabelNode[], id: string): boolean =>
  nodes.some((node) => node.id === id || hasDescendantId(node.children ?? [], id));

export const removeDemoNode = (nodes: LabelNode[], id: string): LabelNode[] =>
  nodes
    .filter((node) => node.id !== id)
    .map((node) => ({
      ...node,
      children: (node.children ?? []).length > 0 ? removeDemoNode(node.children ?? [], id) : undefined,
    }))
    .filter((node) => node.children !== undefined || node.id !== id);

export const applyDemoOperation = (nodes: LabelNode[], operation: LabelOperation): LabelNode[] => {
  if (operation.type === 'rename') {
    return updateNodeById(nodes, operation.targetId, (node) => ({ ...node, name: operation.newName }));
  }

  if (operation.type === 'delete') {
    return removeDemoNode(nodes, operation.targetId);
  }

  const sourceNode = findNodeById(nodes, operation.sourceId);
  const targetNode = findNodeById(nodes, operation.targetId);
  if (!sourceNode || !targetNode) {
    return nodes;
  }

  return updateNodeById(nodes, operation.targetId, (node) => ({
    ...node,
    mailCount: (node.mailCount ?? 0) + (sourceNode.mailCount ?? 0),
  })).map((node) =>
    node.id === operation.sourceId || hasDescendantId(node.children ?? [], operation.sourceId)
      ? updateNodeById([node], operation.sourceId, (source) => ({ ...source, mailCount: 0 }))[0]
      : node,
  );
};
