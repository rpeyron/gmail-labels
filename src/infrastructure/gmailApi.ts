export type GmailLabel = {
  id: string;
  name: string;
  mailCount?: number;
  children?: GmailLabel[];
};

export type GmailApiLabel = {
  id: string;
  name: string;
  type?: string;
  messageListVisibility?: string;
  labelListVisibility?: string;
};

export type GmailDataMode = 'demo' | 'gmail';

type GmailApiResponse = {
  labels?: GmailApiLabel[];
};

const demoLabels: GmailLabel[] = [
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

export const normalizeGmailApiLabels = (labels: GmailApiLabel[]): GmailLabel[] => {
  const root: GmailLabel[] = [];
  const index = new Map<string, GmailLabel>();

  const createNode = (path: string, name: string): GmailLabel => {
    const existing = index.get(path);
    if (existing) {
      return existing;
    }

    const node: GmailLabel = { id: path, name, children: [] };
    index.set(path, node);
    return node;
  };

  const attachChild = (parent: GmailLabel, child: GmailLabel) => {
    parent.children ??= [];
    if (!parent.children.some((existingChild) => existingChild.id === child.id)) {
      parent.children.push(child);
    }
  };

  labels.forEach((label) => {
    const segments = label.name.split('/').filter(Boolean).map((segment) => segment.trim());
    if (segments.length === 0) {
      return;
    }

    segments.forEach((segment, indexValue) => {
      const path = segments.slice(0, indexValue + 1).join('/').toLowerCase().replace(/[^a-z0-9/]+/g, '-');
      const node = createNode(path, segment);

      if (indexValue > 0) {
        const parentPath = segments.slice(0, indexValue).join('/').toLowerCase().replace(/[^a-z0-9/]+/g, '-');
        const parentNode = index.get(parentPath);
        if (parentNode) {
          attachChild(parentNode, node);
        }
      } else if (!root.some((rootNode) => rootNode.id === node.id)) {
        root.push(node);
      }
    });
  });

  return root;
};

const fetchGmailLabels = async (accessToken?: string): Promise<GmailApiLabel[]> => {
  try {
    const headers: HeadersInit = {};
    if (accessToken) {
      headers.Authorization = `Bearer ${accessToken}`;
    }

    const response = await fetch('https://gmail.googleapis.com/gmail/v1/users/me/labels', { headers });
    if (!response.ok) {
      throw new Error(`Unable to fetch Gmail labels (${response.status})`);
    }

    const payload = (await response.json()) as GmailApiResponse;
    return payload.labels ?? [];
  } catch {
    return [];
  }
};

export const loadGmailLabels = async (mode: GmailDataMode = 'demo', accessToken?: string): Promise<GmailLabel[]> => {
  if (mode === 'demo') {
    return demoLabels;
  }

  const rawLabels = await fetchGmailLabels(accessToken);
  if (rawLabels.length === 0) {
    return demoLabels;
  }

  return normalizeGmailApiLabels(rawLabels);
};
