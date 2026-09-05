export type GmailLabel = {
  id: string;
  name: string;
  mailCount?: number;
  isSystem?: boolean;
  children?: GmailLabel[];
};

export type GmailApiLabel = {
  id: string;
  name: string;
  type?: string;
  messagesTotal?: number;
  threadsTotal?: number;
  messageListVisibility?: string;
  labelListVisibility?: string;
};

export type GmailDataMode = 'demo' | 'gmail';

export type GmailUserProfile = {
  emailAddress: string;
};

import { demoLabels } from './demoMode';

type GmailApiResponse = {
  labels?: GmailApiLabel[];
};

const shouldHideTestLabel = (labelName: string): boolean => {
  const normalized = labelName.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
  if (!normalized) {
    return false;
  }

  return normalized.split(/\s+/).some((segment) => segment === 'test' || segment === 'tests');
};

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
    if (shouldHideTestLabel(label.name)) {
      return;
    }

    const segments = label.name.split('/').filter(Boolean).map((segment) => segment.trim());
    if (segments.length === 0) {
      return;
    }

    const isSystemLabel = label.type === 'system';

    segments.forEach((segment, indexValue) => {
      const path = segments.slice(0, indexValue + 1).join('/').toLowerCase().replace(/[^a-z0-9/]+/g, '-');
      const node = createNode(path, segment);

      if (indexValue === segments.length - 1) {
        node.id = label.id;
        node.mailCount = label.messagesTotal;
        node.isSystem = isSystemLabel;
      }

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
    return (payload.labels ?? []).filter((label) => !shouldHideTestLabel(label.name));
  } catch (error) {
    if (error instanceof Error && error.message.startsWith('Unable to fetch Gmail labels')) {
      throw error;
    }
    return [];
  }
};

export const fetchGmailUserProfile = async (accessToken: string): Promise<GmailUserProfile> => {
  const response = await fetch('https://gmail.googleapis.com/gmail/v1/users/me/profile', {
    headers: { Authorization: `Bearer ${accessToken}` },
  });

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(`Unable to fetch Gmail profile (${response.status}): ${errorBody}`);
  }

  return (await response.json()) as GmailUserProfile;
};

export const fetchGmailLabelDetails = async (labelId: string, accessToken: string): Promise<GmailApiLabel> => {
  const response = await fetch(`https://gmail.googleapis.com/gmail/v1/users/me/labels/${encodeURIComponent(labelId)}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(`Unable to fetch Gmail label details (${response.status}): ${errorBody}`);
  }

  return (await response.json()) as GmailApiLabel;
};

export const loadGmailLabels = async (mode: GmailDataMode = 'demo', accessToken?: string): Promise<GmailLabel[]> => {
  if (mode === 'demo') {
    return demoLabels;
  }

  const rawLabels = await fetchGmailLabels(accessToken);
  return normalizeGmailApiLabels(rawLabels);
};
