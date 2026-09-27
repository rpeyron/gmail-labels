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
    id: 'demo-work',
    name: 'Work',
    mailCount: 312,
    children: [
      {
        id: 'demo-work-clients',
        name: 'Clients',
        mailCount: 146,
        children: [
          {
            id: 'demo-work-clients-northwind',
            name: 'Northwind',
            mailCount: 58,
            children: [
              { id: 'demo-work-clients-northwind-2025', name: '2025', mailCount: 24 },
              { id: 'demo-work-clients-northwind-archive', name: 'Archive', mailCount: 34 },
            ],
          },
          {
            id: 'demo-work-clients-contoso',
            name: 'Contoso',
            mailCount: 88,
            children: [
              { id: 'demo-work-clients-contoso-2025', name: '2025', mailCount: 41 },
              { id: 'demo-work-clients-contoso-archive', name: 'Archive', mailCount: 47 },
            ],
          },
        ],
      },
      {
        id: 'demo-work-planning',
        name: 'Planning',
        mailCount: 166,
        children: [
          {
            id: 'demo-work-planning-q1',
            name: 'Q1',
            mailCount: 72,
            children: [{ id: 'demo-work-planning-q1-review', name: 'Review', mailCount: 29 }],
          },
          {
            id: 'demo-work-planning-q2',
            name: 'Q2',
            mailCount: 94,
            children: [{ id: 'demo-work-planning-q2-review', name: 'Review', mailCount: 38 }],
          },
        ],
      },
    ],
  },
  {
    id: 'demo-research',
    name: 'Research',
    mailCount: 228,
    children: [
      {
        id: 'demo-research-library',
        name: 'Library',
        mailCount: 117,
        children: [
          { id: 'demo-research-library-archive', name: 'Archive', mailCount: 63 },
          { id: 'demo-research-library-reading', name: 'Reading list', mailCount: 54 },
        ],
      },
      {
        id: 'demo-research-notes',
        name: 'Notes',
        mailCount: 111,
        children: [
          {
            id: 'demo-research-notes-2024',
            name: '2024',
            mailCount: 52,
            children: [{ id: 'demo-research-notes-2024-archive', name: 'Archive', mailCount: 17 }],
          },
          { id: 'demo-research-notes-2025', name: '2025', mailCount: 59 },
        ],
      },
    ],
  },
  {
    id: 'demo-teams',
    name: 'Teams',
    mailCount: 205,
    children: [
      {
        id: 'demo-teams-design',
        name: 'Design',
        mailCount: 72,
        children: [
          { id: 'demo-teams-design-inbox', name: 'Inbox', mailCount: 31 },
          { id: 'demo-teams-design-archive', name: 'Archive', mailCount: 41 },
        ],
      },
      {
        id: 'demo-teams-engineering',
        name: 'Engineering',
        mailCount: 83,
        children: [
          {
            id: 'demo-teams-engineering-inbox',
            name: 'Inbox',
            mailCount: 44,
            children: [{ id: 'demo-teams-engineering-inbox-urgent', name: 'Urgent', mailCount: 12 }],
          },
          { id: 'demo-teams-engineering-archive', name: 'Archive', mailCount: 39 },
        ],
      },
      {
        id: 'demo-teams-support',
        name: 'Support',
        mailCount: 50,
        children: [
          { id: 'demo-teams-support-inbox', name: 'Inbox', mailCount: 27 },
          { id: 'demo-teams-support-archive', name: 'Archive', mailCount: 23 },
        ],
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
    children: [{ id: 'demo-empty-projects-archived', name: 'Archive', mailCount: 0 }],
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
  {
    id: 'INBOX',
    name: 'Inbox',
    mailCount: 42,
    isSystem: true,
  },
  {
    id: 'STARRED',
    name: 'Starred',
    mailCount: 18,
    isSystem: true,
  },
  {
    id: 'SENT',
    name: 'Sent',
    mailCount: 27,
    isSystem: true,
  },
  {
    id: 'TRASH',
    name: 'Trash',
    mailCount: 6,
    isSystem: true,
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

const removeMailCounts = (nodes: LabelNode[]): LabelNode[] =>
  nodes.map(({ mailCount: _mailCount, children, ...node }) => ({
    ...node,
    children: children ? removeMailCounts(children) : undefined,
  }));

export const getDemoLabels = (): LabelNode[] => removeMailCounts(demoLabels);

export const getDemoLabelMailCount = (id: string): number | undefined => findNodeById(demoLabels, id)?.mailCount;

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
