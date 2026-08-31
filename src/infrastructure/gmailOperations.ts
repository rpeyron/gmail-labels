export type ApplyRenameInput = {
  labelId: string;
  newName: string;
  accessToken: string;
};

export type ApplyMergeInput = {
  sourceId: string;
  targetId: string;
  accessToken: string;
};

export type DeleteLabelInput = {
  labelId: string;
  accessToken: string;
};

export type OperationResult = {
  success: boolean;
  error?: string;
};

const MAX_RETRIES = 3;
const BATCH_SIZE = 1000;

const wait = (milliseconds: number) => new Promise((resolve) => setTimeout(resolve, milliseconds));

const makeGmailApiCall = async (
  endpoint: string,
  method: string = 'GET',
  body?: unknown,
  accessToken?: string,
): Promise<unknown> => {
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  };

  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  const options: RequestInit = {
    method,
    headers,
  };

  if (body) {
    options.body = JSON.stringify(body);
  }

  let lastError: unknown;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt += 1) {
    try {
      const response = await fetch(endpoint, options);

      if (!response.ok) {
        const errorBody = await response.text();
        const error = new Error(`Gmail API error (${response.status}): ${errorBody}`);
        if ([408, 429, 500, 502, 503, 504].includes(response.status) && attempt < MAX_RETRIES) {
          lastError = error;
        } else {
          throw error;
        }
      } else {
        if (response.status === 204) {
          return null;
        }
        return response.json();
      }
    } catch (error) {
      lastError = error;
      if (attempt === MAX_RETRIES || (error instanceof Error && error.message.startsWith('Gmail API error ('))) {
        throw error;
      }
    }

    await wait(250 * 2 ** attempt);
  }

  throw lastError instanceof Error ? lastError : new Error('Gmail API request failed');
};

const listMessageIdsWithLabel = async (labelId: string, accessToken: string): Promise<string[]> => {
  const messageIds: string[] = [];
  let pageToken = '';

  do {
    const query = new URLSearchParams({ labelIds: labelId, maxResults: '500' });
    if (pageToken) {
      query.set('pageToken', pageToken);
    }

    const response = (await makeGmailApiCall(
      `https://gmail.googleapis.com/gmail/v1/users/me/messages?${query.toString()}`,
      'GET',
      undefined,
      accessToken,
    )) as { messages?: Array<{ id: string }>; nextPageToken?: string };

    messageIds.push(...(response.messages ?? []).map((message) => message.id).filter(Boolean));
    pageToken = response.nextPageToken ?? '';
  } while (pageToken);

  return messageIds;
};

export const applyRenameLabel = async (input: ApplyRenameInput): Promise<OperationResult> => {
  try {
    const endpoint = `https://gmail.googleapis.com/gmail/v1/users/me/labels/${encodeURIComponent(input.labelId)}`;

    const response = (await makeGmailApiCall(endpoint, 'PATCH', { name: input.newName }, input.accessToken)) as { name?: string };
    if (response.name !== undefined && response.name !== input.newName) {
      throw new Error('Gmail API returned an unexpected label name after rename');
    }

    const verified = (await makeGmailApiCall(endpoint, 'GET', undefined, input.accessToken)) as { name?: string };
    if (verified.name !== input.newName) {
      throw new Error('Label rename could not be verified');
    }

    return { success: true };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Failed to rename label',
    };
  }
};

export const applyMergeLabels = async (input: ApplyMergeInput): Promise<OperationResult> => {
  try {
    const modifyEndpoint = 'https://gmail.googleapis.com/gmail/v1/users/me/messages/batchModify';

    const messageIds = await listMessageIdsWithLabel(input.sourceId, input.accessToken);

    if (messageIds.length === 0) {
      return { success: true };
    }

    for (let i = 0; i < messageIds.length; i += BATCH_SIZE) {
      const batch = messageIds.slice(i, i + BATCH_SIZE);

      await makeGmailApiCall(
        modifyEndpoint,
        'POST',
        {
          ids: batch,
          addLabelIds: [input.targetId],
          removeLabelIds: [input.sourceId],
        },
        input.accessToken,
      );
    }

    const remainingMessageIds = await listMessageIdsWithLabel(input.sourceId, input.accessToken);
    if (remainingMessageIds.length > 0) {
      throw new Error(`Merge verification failed: ${remainingMessageIds.length} messages still have the source label`);
    }

    return { success: true };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Failed to merge labels',
    };
  }
};

export const deleteLabel = async (input: DeleteLabelInput): Promise<OperationResult> => {
  try {
    const endpoint = `https://gmail.googleapis.com/gmail/v1/users/me/labels/${encodeURIComponent(input.labelId)}`;
    await makeGmailApiCall(endpoint, 'DELETE', undefined, input.accessToken);

    try {
      await makeGmailApiCall(endpoint, 'GET', undefined, input.accessToken);
      throw new Error('Label deletion could not be verified');
    } catch (error) {
      if (error instanceof Error && error.message.includes('Gmail API error (404)')) {
        return { success: true };
      }
      throw error;
    }
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Failed to delete label',
    };
  }
};
