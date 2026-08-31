import { useEffect, useMemo, useState } from 'react';
import { buildLabelPlan, flattenLabelTree, type LabelNode, type OperationMode } from '../../domain/labelOperations';
import { fetchGmailLabelDetails, fetchGmailUserProfile, loadGmailLabels, type GmailDataMode } from '../../infrastructure/gmailApi';
import { requestGoogleAccessToken } from '../../infrastructure/googleAuth';
import { applyMergeLabels, applyRenameLabel, deleteLabel } from '../../infrastructure/gmailOperations';

type TreeRowProps = {
  node: LabelNode;
  depth: number;
  selectedIds: string[];
  onToggleSelection: (id: string) => void;
  renameMap: Record<string, string>;
  onRename: (id: string, value: string) => void;
  targetLabelId: string;
  onTargetSelect: (id: string) => void;
  editingLabelId: string | null;
  onRenameStart: (id: string) => void;
  onRenameEnd: (id: string) => void;
  onDelete: (id: string) => void;
  expandedIds: Record<string, boolean>;
  onToggleExpand: (id: string) => void;
  labelFilter: string;
  isLocked: boolean;
  activeOperation: OperationMode | null;
};

const TreeGridRow = ({
  node,
  depth,
  selectedIds,
  onToggleSelection,
  renameMap,
  onRename,
  targetLabelId,
  onTargetSelect,
  editingLabelId,
  onRenameStart,
  onRenameEnd,
  onDelete,
  expandedIds,
  onToggleExpand,
  labelFilter,
  isLocked,
  activeOperation,
}: TreeRowProps) => {
  const isSource = selectedIds.includes(node.id);
  const isTarget = targetLabelId === node.id;
  const isInternal = (node.children?.length ?? 0) > 0;
  const hasChildLabels = isInternal;
  const isRenameActive = node.mailCount !== undefined && node.mailCount !== 0;
  const isDeleteActive = node.mailCount === 0 && !hasChildLabels;
  const currentRenameValue = renameMap[node.id] ?? node.name;
  const labelIndent = depth * 18;
  const hasTargetSelection = Boolean(targetLabelId);
  const normalizedFilter = labelFilter.trim().toLowerCase();
  const hasMatchingDescendantPath = (currentNode: LabelNode, query: string): boolean =>
    (currentNode.children ?? []).some((child) => child.name.toLowerCase().includes(query) || hasMatchingDescendantPath(child, query));
  const rowMatchesFilter = !normalizedFilter || node.name.toLowerCase().includes(normalizedFilter);
  const hasMatchingDescendant = !normalizedFilter ? false : hasMatchingDescendantPath(node, normalizedFilter);
  const isFilterParentDimmed = Boolean(normalizedFilter) && !rowMatchesFilter && hasMatchingDescendant;

  return (
    <>
      <div className={`tree-row ${isTarget ? 'tree-row-targeted' : ''} ${isFilterParentDimmed ? 'tree-row-filter-dimmed' : ''}`} role="row">
        <div className="tree-cell tree-label-cell" style={{ paddingLeft: `${labelIndent}px` }} role="treeitem" aria-level={depth + 1}>
          {isInternal ? (
            <button type="button" className="tree-toggle" onClick={() => onToggleExpand(node.id)} aria-label={expandedIds[node.id] ? 'Collapse' : 'Expand'}>
              {expandedIds[node.id] ? '▾' : '▸'}
            </button>
          ) : (
            <span className="tree-toggle tree-toggle-leaf">•</span>
          )}
          <span className="tree-label-icon" aria-hidden="true">🏷️</span>
          <span className="tree-label">{node.name}</span>
        </div>
        <div className="tree-cell tree-meta" role="cell">{node.mailCount === undefined ? '—' : `${node.mailCount} mails`}</div>
        <div className="tree-cell" role="cell">
          <label className={`tree-checkbox ${isSource ? 'is-selected' : ''}`}>
            <input
              type="checkbox"
              checked={isSource}
              disabled={isLocked || Boolean(activeOperation && activeOperation !== 'merge')}
              onChange={() => onToggleSelection(node.id)}
            />
            <span>Source</span>
          </label>
        </div>
        <div className="tree-cell" role="cell">
          <label className={`tree-radio ${isTarget ? 'is-selected' : ''} ${hasTargetSelection && !isTarget ? 'is-dimmed' : ''}`}>
            <input
              type="radio"
              name="target-label"
              checked={isTarget}
              disabled={isLocked || Boolean(activeOperation && activeOperation !== 'merge')}
              onClick={() => onTargetSelect(node.id)}
            />
            <span>Target</span>
          </label>
        </div>
        <div className="tree-cell tree-actions-cell" role="cell">
          {editingLabelId === node.id ? (
            <input
              className="rename-input"
              value={currentRenameValue}
              onChange={(event) => onRename(node.id, event.target.value)}
              onBlur={() => onRenameEnd(node.id)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  onRenameEnd(node.id);
                }
              }}
              autoFocus
              placeholder="New name"
            />
          ) : (
            <>
              {isRenameActive && (
                <button
                  type="button"
                  className="action-button action-button-rename"
                  onClick={() => onRenameStart(node.id)}
                  disabled={isLocked || Boolean(activeOperation && activeOperation !== 'rename')}
                  aria-label={`Rename ${node.name}`}
                  title="Rename"
                >
                  <span aria-hidden="true">✏️</span>
                </button>
              )}
              {isDeleteActive && (
                <button
                  type="button"
                  className="action-button action-button-delete"
                  onClick={() => onDelete(node.id)}
                  disabled={isLocked || Boolean(activeOperation && activeOperation !== 'delete')}
                  aria-label={`Delete ${node.name}`}
                  title="Delete"
                >
                  <span aria-hidden="true">🗑️</span>
                </button>
              )}
            </>
          )}
        </div>
      </div>
      {isInternal && expandedIds[node.id] && (node.children ?? []).map((child) => (
        <TreeGridRow
          key={child.id}
          node={child}
          depth={depth + 1}
          selectedIds={selectedIds}
          onToggleSelection={onToggleSelection}
          renameMap={renameMap}
          onRename={onRename}
          targetLabelId={targetLabelId}
          onTargetSelect={onTargetSelect}
          editingLabelId={editingLabelId}
          onRenameStart={onRenameStart}
          onRenameEnd={onRenameEnd}
          onDelete={onDelete}
          expandedIds={expandedIds}
          onToggleExpand={onToggleExpand}
          labelFilter={labelFilter}
          isLocked={isLocked}
          activeOperation={activeOperation}
        />
      ))}
    </>
  );
};

type Props = {
  initialLabels?: LabelNode[];
};

const LabelManager = ({ initialLabels }: Props) => {
  const [labels, setLabels] = useState<LabelNode[]>(initialLabels ?? []);
  const [selected, setSelected] = useState<string[]>([]);
  const [targetLabelId, setTargetLabelId] = useState<string>('');
  const [renameMap, setRenameMap] = useState<Record<string, string>>({});
  const [operationMode, setOperationMode] = useState<OperationMode>('merge');
  const [activeOperation, setActiveOperation] = useState<OperationMode | null>(null);
  const [dataMode, setDataMode] = useState<GmailDataMode>('demo');
  const [accessToken, setAccessToken] = useState('');
  const [userEmail, setUserEmail] = useState('');
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);
  const [operationProgress, setOperationProgress] = useState<Array<{ id: string; label: string; total: number; processed: number; status: 'running' | 'success' | 'error' }>>([]);
  const [clientId, setClientId] = useState(() => {
    if (typeof window === 'undefined') {
      return '';
    }
    return window.localStorage.getItem('gmail-label-manager.client-id') ?? '';
  });
  const [applyMessage, setApplyMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [editingLabelId, setEditingLabelId] = useState<string | null>(null);
  const [expandedIds, setExpandedIds] = useState<Record<string, boolean>>({});
  const [labelFilter, setLabelFilter] = useState('');
  const [refreshingLabels, setRefreshingLabels] = useState(false);

  useEffect(() => {
    const initialExpanded: Record<string, boolean> = {};
    const populate = (nodes: LabelNode[]) => {
      nodes.forEach((node) => {
        if ((node.children?.length ?? 0) > 0) {
          initialExpanded[node.id] = true;
          populate(node.children ?? []);
        }
      });
    };
    populate(labels);
    setExpandedIds(initialExpanded);
  }, [labels]);

  useEffect(() => {
    let active = true;

    setLoading(true);
    const loadAccountData = async () => {
      try {
        const [items, profile] = await Promise.all([
          loadGmailLabels(dataMode, accessToken),
          dataMode === 'gmail' && accessToken ? fetchGmailUserProfile(accessToken) : Promise.resolve(null),
        ]);
        if (active) {
          setLabels(items);
          setUserEmail(profile?.emailAddress ?? '');
          setLoading(false);
        }
      } catch (error) {
        if (active) {
          setLoading(false);
          if (error instanceof Error && error.message.includes('(401)')) {
            setAccessToken('');
            setUserEmail('');
            setApplyMessage({ type: 'error', text: 'Your Google session has expired. Please sign in again.' });
          } else {
            setApplyMessage({ type: 'error', text: error instanceof Error ? error.message : 'Unable to load Gmail data.' });
          }
        }
      }
    };

    void loadAccountData();

    return () => {
      active = false;
    };
  }, [dataMode, accessToken]);

  const flattened = useMemo(() => flattenLabelTree(labels), [labels]);

  const ensureLabelMailCount = async (labelId: string): Promise<boolean> => {
    if (dataMode === 'demo' || flattened.some((label) => label.id === labelId && label.mailCount !== undefined)) {
      return true;
    }

    if (!accessToken) {
      setApplyMessage({ type: 'error', text: 'Please sign in with your Google Account first.' });
      return false;
    }

    try {
      const details = await fetchGmailLabelDetails(labelId, accessToken);
      setLabels((current) => updateNodeById(current, labelId, (node) => ({ ...node, mailCount: details.messagesTotal })));
      return true;
    } catch (error) {
      setApplyMessage({
        type: 'error',
        text: error instanceof Error ? error.message : 'Unable to load Gmail label details.',
      });
      return false;
    }
  };

  const ensureOperationMailCounts = async (operations: Array<{ type: string; sourceId?: string; targetId: string }>) => {
    const ids = [
      ...new Set(
        operations.flatMap((operation) =>
          [operation.targetId, operation.sourceId].filter((id): id is string => Boolean(id)),
        ),
      ),
    ];
    const counts = new Map<string, number>();

    for (const id of ids) {
      const current = flattened.find((label) => label.id === id);
      if (current?.mailCount !== undefined) {
        counts.set(id, current.mailCount);
        continue;
      }

      if (dataMode === 'demo') {
        counts.set(id, current?.mailCount ?? 0);
        continue;
      }

      if (!accessToken) {
        return null;
      }

      try {
        const details = await fetchGmailLabelDetails(id, accessToken);
        counts.set(id, details.messagesTotal ?? 0);
        setLabels((currentLabels) => updateNodeById(currentLabels, id, (node) => ({ ...node, mailCount: details.messagesTotal })));
      } catch (error) {
        setApplyMessage({ type: 'error', text: error instanceof Error ? error.message : 'Unable to load Gmail label details.' });
        return null;
      }
    }

    return counts;
  };

  const selectedForCurrentOperation = useMemo(() => {
    if (operationMode === 'rename') {
      return Object.keys(renameMap).filter((id) => (renameMap[id] ?? '').trim().length > 0);
    }

    if (operationMode === 'delete') {
      return selected;
    }

    return selected;
  }, [operationMode, renameMap, selected]);

  const getOperationMailCount = (
    operation: { type: string; sourceId?: string; targetId: string; newName?: string },
    hydratedCounts?: Map<string, number>,
  ) => {
    if (operation.type === 'delete') {
      return 0;
    }

    const labelId = operation.type === 'merge' ? operation.sourceId ?? operation.targetId : operation.targetId;
    const match = flattened.find((label) => label.id === labelId);
    return Math.max(0, hydratedCounts?.get(labelId) ?? match?.mailCount ?? 0);
  };

  const plan = useMemo(
    () =>
      buildLabelPlan({
        labels,
        selectedLabelIds: selectedForCurrentOperation,
        targetLabelId: operationMode === 'merge' ? targetLabelId : '',
        renameMap,
        dryRun: true,
        mode: operationMode,
      }),
    [labels, selectedForCurrentOperation, targetLabelId, renameMap, operationMode],
  );

  const toggleSelection = (id: string) => {
    if (applying || activeOperation === 'rename' || activeOperation === 'delete') {
      return;
    }

    setOperationMode('merge');
    setActiveOperation('merge');
    setSelected((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  };

  const updateRename = (id: string, value: string) => {
    setRenameMap((current) => ({ ...current, [id]: value }));
  };

  const removeLabelFromTree = (nodes: LabelNode[], idToRemove: string): LabelNode[] =>
    nodes
      .filter((node) => node.id !== idToRemove)
      .map((node) => ({
        ...node,
        children: node.children ? removeLabelFromTree(node.children, idToRemove) : undefined,
      }))
      .filter((node) => node.id !== idToRemove || !node.children || node.children.length > 0);

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
        return {
          ...node,
          children: updateNodeById(node.children ?? [], id, updater),
        };
      }
      return node;
    });

  const hasDescendantId = (nodes: LabelNode[], id: string): boolean =>
    nodes.some((node) => node.id === id || hasDescendantId(node.children ?? [], id));

  const removeNodeById = (nodes: LabelNode[], id: string): LabelNode[] =>
    nodes
      .filter((node) => node.id !== id)
      .map((node) => ({
        ...node,
        children: (node.children ?? []).length > 0 ? removeNodeById(node.children ?? [], id) : undefined,
      }))
      .filter((node) => node.children !== undefined || node.id !== id);

  const applyDemoOperation = (nodes: LabelNode[], operation: { type: string; sourceId?: string; targetId: string; newName?: string }): LabelNode[] => {
    if (operation.type === 'rename') {
      return updateNodeById(nodes, operation.targetId, (node) => ({
        ...node,
        name: operation.newName ?? node.name,
      }));
    }

    if (operation.type === 'delete') {
      return removeNodeById(nodes, operation.targetId);
    }

    if (operation.type === 'merge' && operation.sourceId) {
      const sourceId = operation.sourceId;
      const sourceNode = findNodeById(nodes, operation.sourceId);
      const targetNode = findNodeById(nodes, operation.targetId);
      if (!sourceNode || !targetNode) {
        return nodes;
      }

      const sourceChildren = sourceNode.children ?? [];
      const sourceHasChildren = sourceChildren.length > 0;
      const sourceIsParentOfOtherLabels = hasDescendantId(nodes, operation.sourceId) && sourceHasChildren;

      return updateNodeById(nodes, operation.targetId, (node) => ({
        ...node,
        mailCount: (node.mailCount ?? 0) + (sourceNode.mailCount ?? 0),
      })).map((node) =>
        node.id === sourceId || hasDescendantId(node.children ?? [], sourceId)
          ? updateNodeById([node], sourceId, (source) => ({ ...source, mailCount: 0 }))[0]
          : node,
      );
    }

    return nodes;
  };

  const handleDeleteLabel = (id: string) => {
    const targetNode = flattened.find((label) => label.id === id);
    if (!targetNode || (targetNode.mailCount ?? 0) > 0) {
      return;
    }

    setLabels((current) => removeLabelFromTree(current, id));
    setSelected((current) => current.filter((item) => item !== id));
    setRenameMap((current) => {
      const next = { ...current };
      delete next[id];
      return next;
    });
    setTargetLabelId((current) => (current === id ? '' : current));
    setEditingLabelId((current) => (current === id ? null : current));
  };

  const collectAllIds = (node: LabelNode): string[] => [node.id, ...(node.children ?? []).flatMap(collectAllIds)];

  const filterLabels = (nodes: LabelNode[], query: string): LabelNode[] => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) {
      return nodes;
    }

    return nodes.reduce<LabelNode[]>((acc, node) => {
      const children = filterLabels(node.children ?? [], normalizedQuery);
      const matches = node.name.toLowerCase().includes(normalizedQuery);

      if (matches || children.length > 0) {
        acc.push({
          ...node,
          children: children.length > 0 ? children : undefined,
        });
      }

      return acc;
    }, []);
  };

  const filteredLabels = useMemo(() => filterLabels(labels, labelFilter), [labels, labelFilter]);

  const hasMatchingDescendantPath = (node: LabelNode, query: string): boolean =>
    (node.children ?? []).some((child) => child.name.toLowerCase().includes(query) || hasMatchingDescendantPath(child, query));

  const getSourceNames = (): string[] => {
    const findLabel = (nodes: LabelNode[], id: string, path: string[] = []): string | null => {
      for (const node of nodes) {
        const newPath = [...path, node.name];
        if (node.id === id) {
          return newPath.join('/');
        }
        const found = findLabel(node.children ?? [], id, newPath);
        if (found) return found;
      }
      return null;
    };

    return selected
      .map((id) => findLabel(labels, id))
      .filter((name): name is string => name !== null);
  };

  const getTargetName = (): string | null => {
    const findLabel = (nodes: LabelNode[], id: string, path: string[] = []): string | null => {
      for (const node of nodes) {
        const newPath = [...path, node.name];
        if (node.id === id) {
          return newPath.join('/');
        }
        const found = findLabel(node.children ?? [], id, newPath);
        if (found) return found;
      }
      return null;
    };

    return findLabel(labels, targetLabelId);
  };

  const toggleExpand = (id: string) => {
    setExpandedIds((current) => ({
      ...current,
      [id]: !(current[id] ?? false),
    }));
  };

  const expandAll = () => {
    const next = Object.fromEntries(labels.flatMap((node) => collectAllIds(node).map((id) => [id, true])));
    setExpandedIds(next);
  };

  const collapseAll = () => {
    setExpandedIds({});
  };

  const refreshLabels = async () => {
    if (applying || refreshingLabels) {
      return;
    }

    try {
      setRefreshingLabels(true);
      const refreshedLabels = await loadGmailLabels(dataMode, accessToken);
      setLabels(refreshedLabels);
      setSelected([]);
      setTargetLabelId('');
      setRenameMap({});
      setActiveOperation(null);
      setOperationProgress([]);
      setApplyMessage(null);
    } catch (error) {
      setApplyMessage({
        type: 'error',
        text: error instanceof Error ? error.message : 'Unable to refresh labels.',
      });
    } finally {
      setRefreshingLabels(false);
    }
  };

  const handleGoogleSignIn = async () => {
    if (!clientId.trim()) {
      setApplyMessage({ type: 'error', text: 'Please enter your Google OAuth client ID first.' });
      return;
    }

    try {
      window.localStorage.setItem('gmail-label-manager.client-id', clientId.trim());
      setApplying(true);
      const token = await requestGoogleAccessToken(clientId);
      const profile = await fetchGmailUserProfile(token);
      setAccessToken(token);
      setUserEmail(profile.emailAddress);
      setDataMode('gmail');
      setApplyMessage({ type: 'success', text: 'Signed in to Google Account.' });
      setTimeout(() => setApplyMessage(null), 3000);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to sign in with Google.';
      setApplyMessage({ type: 'error', text: message });
    } finally {
      setApplying(false);
    }
  };

  const resetOperation = () => {
    setSelected([]);
    setTargetLabelId('');
    setRenameMap({});
    setOperationMode('merge');
    setActiveOperation(null);
    setApplyMessage(null);
    setOperationProgress([]);
  };

  const clearProgressForNewOperation = () => {
    setApplyMessage(null);
    setOperationProgress([]);
  };

  const findLabelPath = (id: string): string | null => {
    const walk = (nodes: LabelNode[], path: string[] = []): string | null => {
      for (const node of nodes) {
        const nextPath = [...path, node.name];
        if (node.id === id) {
          return nextPath.join('/');
        }
        const found = walk(node.children ?? [], nextPath);
        if (found) {
          return found;
        }
      }
      return null;
    };

    return walk(labels, []);
  };

  const getRenamedLabelName = (labelId: string, newName: string): string => {
    const currentPath = findLabelPath(labelId);
    const parentPath = currentPath?.includes('/') ? currentPath.slice(0, currentPath.lastIndexOf('/')) : '';
    return parentPath ? `${parentPath}/${newName}` : newName;
  };

  const canRunOperation = plan.operations.length > 0 && plan.validationErrors.length === 0;

  const getProgressItemId = (operation: { type: string; sourceId?: string; targetId: string; newName?: string }) =>
    `${operation.type}:${operation.type === 'merge' ? operation.sourceId ?? operation.targetId : operation.targetId}`;

  const executionOperations = (() => {
    const mergeOperations = plan.operations.filter(
      (operation): operation is (typeof plan.operations)[number] & { type: 'merge'; sourceId: string } =>
        operation.type === 'merge' && Boolean(operation.sourceId),
    );

    if (mergeOperations.length === 0) {
      return plan.operations;
    }

    const sourceIds = new Set(mergeOperations.map((operation) => operation.sourceId));
    const canDeleteSource = (node: LabelNode): boolean =>
      (node.children ?? []).every((child) => sourceIds.has(child.id) && canDeleteSource(child));

    const sourceDeletionOperations = mergeOperations
      .map((operation) => ({ operation, sourceNode: findNodeById(labels, operation.sourceId) }))
      .filter(({ sourceNode }) => sourceNode && canDeleteSource(sourceNode))
      .sort(({ operation: first }, { operation: second }) => {
        const firstDepth = flattened.find((label) => label.id === first.sourceId)?.depth ?? 0;
        const secondDepth = flattened.find((label) => label.id === second.sourceId)?.depth ?? 0;
        return secondDepth - firstDepth;
      })
      .map(({ operation }) => ({ type: 'delete' as const, targetId: operation.sourceId, dryRun: operation.dryRun }));

    return [...plan.operations, ...sourceDeletionOperations];
  })();

  const executeOperation = async (operation: { type: string; sourceId?: string; targetId: string; newName?: string }) => {
    if (dataMode === 'demo') {
      return { success: true };
    }

    if (!accessToken) {
      throw new Error('Please sign in with your Google Account first.');
    }

    if (operation.type === 'rename') {
      const newName = getRenamedLabelName(operation.targetId, operation.newName ?? '');
      const result = await applyRenameLabel({
        labelId: operation.targetId,
        newName,
        accessToken,
      });
      if (!result.success) {
        throw new Error(result.error ?? 'Failed to rename label');
      }
      return result;
    }

    if (operation.type === 'merge') {
      const result = await applyMergeLabels({
        sourceId: operation.sourceId ?? '',
        targetId: operation.targetId,
        accessToken,
      });
      if (!result.success) {
        throw new Error(result.error ?? 'Failed to merge labels');
      }
      return result;
    }

    const result = await deleteLabel({
      labelId: operation.targetId,
      accessToken,
    });
    if (!result.success) {
      throw new Error(result.error ?? 'Failed to delete label');
    }
    return result;
  };

  const handleRunOperation = async () => {
    if (executionOperations.length === 0) {
      return;
    }

    if (dataMode !== 'demo' && !accessToken) {
      setApplyMessage({ type: 'error', text: 'Please sign in with your Google Account first.' });
      return;
    }

    try {
      setApplying(true);
      setActiveOperation(null);
      setApplyMessage(null);

      const hydratedCounts = await ensureOperationMailCounts(executionOperations);
      if (!hydratedCounts) {
        return;
      }

      const progressEntries = executionOperations.map((operation) => {
        const id = getProgressItemId(operation);
        const label =
          operation.type === 'merge'
            ? `${findLabelPath(operation.sourceId ?? '') ?? 'source'} → ${findLabelPath(operation.targetId) ?? 'target'}`
            : operation.type === 'rename'
              ? `${findLabelPath(operation.targetId) ?? 'label'} → ${renameMap[operation.targetId] ?? 'new name'}`
              : `Delete ${findLabelPath(operation.targetId) ?? 'label'}`;

        return {
          id,
          label,
          total: getOperationMailCount(operation, hydratedCounts),
          processed: 0,
          status: 'running' as const,
        };
      });

      setOperationProgress(progressEntries);

      for (let index = 0; index < executionOperations.length; index += 1) {
        const operation = executionOperations[index];
        const itemId = getProgressItemId(operation);
        const total = getOperationMailCount(operation, hydratedCounts);

        if (dataMode === 'demo') {
          for (let processed = 0; processed <= total; processed += Math.max(1, Math.ceil(total / 10))) {
            setOperationProgress((current) =>
              current.map((entry) =>
                entry.id === itemId ? { ...entry, processed: Math.min(processed, total), status: 'running' } : entry,
              ),
            );
            await new Promise((resolve) => setTimeout(resolve, 60));
          }
        }

        await executeOperation(operation);

        if (dataMode === 'demo') {
          if (operation.type === 'delete') {
            setLabels((current) => removeNodeById(current, operation.targetId));
          } else {
            setLabels((current) => applyDemoOperation(current, operation));
          }
        } else {
          const refreshedLabels = await loadGmailLabels('gmail', accessToken);
          setLabels(refreshedLabels);
        }

        if (operation.type === 'delete') {
          setSelected((current) => current.filter((id) => id !== operation.targetId));
          setRenameMap((current) => {
            const next = { ...current };
            delete next[operation.targetId];
            return next;
          });
          setTargetLabelId((current) => (current === operation.targetId ? '' : current));
        }

        setOperationProgress((current) =>
          current.map((entry) =>
            entry.id === itemId ? { ...entry, processed: total, status: 'success' } : entry,
          ),
        );

        if (operation.type === 'merge' && operation.sourceId) {
          setSelected((current) => current.filter((id) => id !== operation.sourceId));
        }
      }

      setSelected([]);
      setTargetLabelId('');
      setActiveOperation(null);
      setApplyMessage({ type: 'success', text: `Processed ${executionOperations.length} operation${executionOperations.length > 1 ? 's' : ''}.` });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to process operations.';
      setApplyMessage({ type: 'error', text: message });
      const failedOperation = plan.operations.find((operation) => {
        const itemId = getProgressItemId(operation);
        return operationProgress.some((entry) => entry.id === itemId && entry.status === 'running');
      });
      const failedItemId = failedOperation ? getProgressItemId(failedOperation) : null;

      if (failedItemId) {
        setOperationProgress((current) =>
          current.map((entry) =>
            entry.id === failedItemId ? { ...entry, status: 'error', processed: Math.max(0, Math.min(entry.processed, entry.total)) } : entry,
          ),
        );
      }
    } finally {
      setApplying(false);
    }
  };

  if (loading) {
    return <p className="panel">Loading labels…</p>;
  }

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">Gmail Label Manager</p>
          <h1>Organise labels safely</h1>
          <p className="hero-copy">Preview merges, rename labels, and keep a clear overview of your hierarchy before applying anything.</p>
        </div>
        <div className="actions">
          <div className="account-picker">
            <label className="account-picker-label" htmlFor="data-mode">Data source</label>
            <select id="data-mode" value={dataMode} onChange={(event) => setDataMode(event.target.value as GmailDataMode)}>
            <option value="demo">Demo mode</option>
              <option value="gmail">Google account · OAuth</option>
            </select>
            <span className={`oauth-status ${accessToken ? 'oauth-status-connected' : ''}`}>
              {dataMode === 'gmail' ? (accessToken ? 'OAuth connected' : 'OAuth sign-in required') : 'Local demo data'}
            </span>
            {dataMode === 'gmail' && accessToken && userEmail ? (
              <span className="account-identity" title={userEmail}>
                <span className="account-identity-icon" aria-hidden="true">◉</span>
                {userEmail}
              </span>
            ) : null}
          </div>
          {dataMode === 'gmail' && !accessToken ? (
            <>
              <input
                className="token-input"
                value={clientId}
                onChange={(event) => {
                  const value = event.target.value;
                  setClientId(value);
                  window.localStorage.setItem('gmail-label-manager.client-id', value);
                }}
                placeholder="Enter Google OAuth client ID"
                aria-label="Google OAuth client ID"
                disabled={applying}
              />
              <button onClick={handleGoogleSignIn} disabled={applying} className="sign-in-button">
                {applying ? 'Signing in…' : 'Sign in with Google'}
              </button>
            </>
          ) : accessToken ? (
            <button
              className="sign-out-button"
              onClick={() => {
                setAccessToken('');
                setUserEmail('');
              }}
              disabled={applying}
            >
              Sign out
            </button>
          ) : null}
        </div>
      </header>

      <section className="panel">
        <div className="operation-summary-top">
          <div className="summary-row summary-row-header">
            <div className="summary-label">Operation:</div>
            <div className="summary-value operation-name">
              {operationMode === 'merge' && getSourceNames().length > 0 && getTargetName()
                ? `Merge ${getSourceNames().join(' / ')} → ${getTargetName()}`
                : operationMode === 'rename' && Object.keys(renameMap).length > 0
                  ? `Rename ${Object.entries(renameMap)
                      .filter(([, value]) => value.trim())
                      .map(([id, value]) => `${findLabelPath(id) ?? id} → ${value}`)
                      .join(' ; ')}`
                  : operationMode === 'delete' && selected.length > 0
                    ? `Delete ${selected.map((id) => findLabelPath(id) ?? id).join(' / ')}`
                    : 'No operation configured'}
            </div>
            <div className="operation-actions">
              <button type="button" className="mini-button mini-button-secondary" onClick={resetOperation} disabled={applying}>
                Reset
              </button>
              <button
                type="button"
                className={`run-button ${canRunOperation ? 'run-button-ready' : ''}`}
                onClick={handleRunOperation}
                disabled={applying || !canRunOperation}
              >
                <span aria-hidden="true">▶</span>
                {applying ? 'Running…' : 'Run'}
              </button>
            </div>
          </div>
        </div>

        <div className="panel-content">
          {operationProgress.length > 0 && (
            <div className="progress-stack">
              {operationProgress.map((progress) => (
                <div key={progress.id} className="operation-progress">
                  <div className="operation-progress-label-wrap">
                    <div
                      className="operation-progress-bar"
                      aria-label={`${progress.processed} of ${progress.total} mails processed`}
                    >
                      <span
                        style={{
                          width: `${progress.total === 0 && progress.status === 'success' ? 100 : (progress.processed / Math.max(progress.total, 1)) * 100}%`,
                        }}
                      />
                    </div>
                    <span className="operation-progress-label">{progress.label}</span>
                  </div>
                  <div className="operation-progress-content">
                    <span className="operation-progress-meta">{progress.processed}/{progress.total} mails</span>
                    <div className="operation-progress-status">
                      {progress.status === 'running' && <span className="operation-progress-state">Running</span>}
                      {progress.status === 'success' && <span className="status-icon status-success" aria-label="Succeeded">✓</span>}
                      {progress.status === 'error' && <span className="status-icon status-error" aria-label="Failed">✕</span>}
                      {progress.status === 'error' && (
                        <button type="button" className="progress-retry" onClick={handleRunOperation} aria-label="Retry operation" title="Retry operation">
                          ↻
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {plan.validationErrors.length > 0 ? (
            <div className="validation-errors">
              <p className="error-title">Validation errors:</p>
              <ul>
                {plan.validationErrors.map((error) => (
                  <li key={error}>{error}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {applyMessage ? (
            <div className={`apply-message apply-message-${applyMessage.type}`}>
              {applyMessage.text}
            </div>
          ) : null}
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div className="tree-toolbar">
            <div className="tree-toolbar-left">
              <div className="label-filter-wrap">
                <input
                  className="label-filter-input"
                  type="text"
                  value={labelFilter}
                  onChange={(event) => setLabelFilter(event.target.value)}
                  placeholder="Filter labels"
                  aria-label="Filter labels"
                />
                {labelFilter && (
                  <button
                    type="button"
                    className="label-filter-clear"
                    onClick={() => setLabelFilter('')}
                    aria-label="Clear filter"
                    title="Clear filter"
                  >
                    ×
                  </button>
                )}
              </div>
              <button type="button" className="mini-button" onClick={expandAll}>
                Expand all
              </button>
              <button type="button" className="mini-button" onClick={collapseAll}>
                Collapse all
              </button>
              <button type="button" className="mini-button" onClick={refreshLabels} disabled={applying || refreshingLabels}>
                {refreshingLabels ? 'Refreshing…' : 'Refresh labels'}
              </button>
            </div>
          </div>
        </div>
        <div className="tree-shell">
          <div className="tree-header" role="row">
            <div className="tree-cell" style={{ gridColumn: '1 / 2' }}>Label</div>
            <div className="tree-cell" style={{ gridColumn: '2 / 3' }}>Mails</div>
            <div className="tree-cell" style={{ gridColumn: '3 / 4' }}>Source</div>
            <div className="tree-cell" style={{ gridColumn: '4 / 5' }}>Target</div>
            <div className="tree-cell" style={{ gridColumn: '5 / 6' }}>Actions</div>
          </div>
          <div className="tree-grid" role="tree">
            {filteredLabels.map((label) => (
              <TreeGridRow
                key={label.id}
                node={label}
                depth={0}
                selectedIds={selected}
                onToggleSelection={(id) => {
                  void (async () => {
                    if (!(await ensureLabelMailCount(id))) {
                      return;
                    }
                    clearProgressForNewOperation();
                    toggleSelection(id);
                  })();
                }}
                renameMap={renameMap}
                onRename={updateRename}
                targetLabelId={targetLabelId}
                onTargetSelect={(id) => {
                  if (applying || activeOperation === 'rename' || activeOperation === 'delete') {
                    return;
                  }
                  void (async () => {
                    if (!(await ensureLabelMailCount(id))) {
                      return;
                    }
                    clearProgressForNewOperation();
                    setOperationMode('merge');
                    setActiveOperation('merge');
                    setTargetLabelId((current) => (current === id ? '' : id));
                  })();
                }}
                editingLabelId={editingLabelId}
                onRenameStart={(id) => {
                  if (applying || activeOperation === 'merge' || activeOperation === 'delete') {
                    return;
                  }
                  void (async () => {
                    if (!(await ensureLabelMailCount(id))) {
                      return;
                    }
                    clearProgressForNewOperation();
                    setOperationMode('rename');
                    setActiveOperation('rename');
                    setEditingLabelId(id);
                  })();
                }}
                onRenameEnd={(id) => {
                  const value = (renameMap[id] ?? '').trim();
                  if (value) {
                    setEditingLabelId(null);
                    setActiveOperation(null);
                    return;
                  }
                  setRenameMap((current) => {
                    const next = { ...current };
                    delete next[id];
                    return next;
                  });
                  setEditingLabelId(null);
                  setActiveOperation(null);
                }}
                onDelete={(id) => {
                  if (applying || activeOperation === 'merge' || activeOperation === 'rename') {
                    return;
                  }
                  void (async () => {
                    if (!(await ensureLabelMailCount(id))) {
                      return;
                    }
                    clearProgressForNewOperation();
                    setSelected([id]);
                    setTargetLabelId('');
                    setOperationMode('delete');
                    setActiveOperation('delete');
                  })();
                }}
                expandedIds={expandedIds}
                onToggleExpand={toggleExpand}
                labelFilter={labelFilter}
                isLocked={applying}
                activeOperation={activeOperation}
              />
            ))}
          </div>
        </div>
      </section>
    </main>
  );
};

export default LabelManager;
