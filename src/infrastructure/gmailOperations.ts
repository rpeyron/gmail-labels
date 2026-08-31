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

  const response = await fetch(endpoint, options);

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(`Gmail API error (${response.status}): ${errorBody}`);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
};

export const applyRenameLabel = async (input: ApplyRenameInput): Promise<OperationResult> => {
  try {
    const endpoint = `https://gmail.googleapis.com/gmail/v1/users/me/labels/${encodeURIComponent(input.labelId)}`;

    await makeGmailApiCall(endpoint, 'PATCH', { name: input.newName }, input.accessToken);

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
    const messagesEndpoint = `https://gmail.googleapis.com/gmail/v1/users/me/messages?q=label:${encodeURIComponent(input.sourceId)}`;
    const modifyEndpoint = 'https://gmail.googleapis.com/gmail/v1/users/me/messages/batchModify';

    const messagesResponse = (await makeGmailApiCall(messagesEndpoint, 'GET', undefined, input.accessToken)) as {
      messages?: Array<{ id: string }>;
    };
    const messages = messagesResponse.messages ?? [];

    if (messages.length === 0) {
      return { success: true };
    }

    const messageIds = messages.map((msg) => msg.id);
    const batchSize = 1000;

    for (let i = 0; i < messageIds.length; i += batchSize) {
      const batch = messageIds.slice(i, i + batchSize);

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
    return { success: true };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Failed to delete label',
    };
  }
};
