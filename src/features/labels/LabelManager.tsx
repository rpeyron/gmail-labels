import { useEffect, useMemo, useState } from 'react';
import { buildLabelPlan, flattenLabelTree, type LabelNode } from '../../domain/labelOperations';
import { loadGmailLabels, type GmailDataMode } from '../../infrastructure/gmailApi';
import { requestGoogleAccessToken } from '../../infrastructure/googleAuth';
import { applyMergeLabels, applyRenameLabel } from '../../infrastructure/gmailOperations';

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
}: TreeRowProps) => {
  const isSource = selectedIds.includes(node.id);
  const isTarget = targetLabelId === node.id;
  const isInternal = (node.children?.length ?? 0) > 0;
  const hasChildLabels = isInternal;
  const isRenameActive = (node.mailCount ?? 0) !== 0;
  const isDeleteActive = (node.mailCount ?? 0) === 0 && !hasChildLabels;
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
        <div className="tree-cell tree-meta" role="cell">{node.mailCount ?? 0} mails</div>
        <div className="tree-cell" role="cell">
          <label className={`tree-checkbox ${isSource ? 'is-selected' : ''}`}>
            <input type="checkbox" checked={isSource} onChange={() => onToggleSelection(node.id)} />
            <span>Source</span>
          </label>
        </div>
        <div className="tree-cell" role="cell">
          <label className={`tree-radio ${isTarget ? 'is-selected' : ''} ${hasTargetSelection && !isTarget ? 'is-dimmed' : ''}`}>
            <input type="radio" name="target-label" checked={isTarget} onClick={() => onTargetSelect(node.id)} />
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
                <button type="button" className="action-button action-button-rename" onClick={() => onRenameStart(node.id)} aria-label={`Rename ${node.name}`} title="Rename">
                  <span aria-hidden="true">✏️</span>
                </button>
              )}
              {isDeleteActive && (
                <button type="button" className="action-button action-button-delete" onClick={() => onDelete(node.id)} aria-label={`Delete ${node.name}`} title="Delete">
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
  const [mode, setMode] = useState<'preview' | 'apply'>('preview');
  const [dataMode, setDataMode] = useState<GmailDataMode>('demo');
  const [accessToken, setAccessToken] = useState('');
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);
  const [clientId, setClientId] = useState('');
  const [applyMessage, setApplyMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [editingLabelId, setEditingLabelId] = useState<string | null>(null);
  const [expandedIds, setExpandedIds] = useState<Record<string, boolean>>({});
  const [labelFilter, setLabelFilter] = useState('');

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
    loadGmailLabels(dataMode, accessToken).then((items) => {
      if (active) {
        setLabels(items);
        setLoading(false);
      }
    });

    return () => {
      active = false;
    };
  }, [dataMode, accessToken]);

  const flattened = useMemo(() => flattenLabelTree(labels), [labels]);

  const plan = useMemo(
    () =>
      buildLabelPlan({
        labels,
        selectedLabelIds: selected,
        targetLabelId,
        renameMap,
        dryRun: mode === 'preview',
      }),
    [labels, selected, targetLabelId, renameMap, mode],
  );

  const toggleSelection = (id: string) => {
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

  const handleGoogleSignIn = async () => {
    if (!clientId.trim()) {
      setApplyMessage({ type: 'error', text: 'Please enter your Google OAuth client ID first.' });
      return;
    }

    try {
      setApplying(true);
      const token = await requestGoogleAccessToken(clientId);
      setAccessToken(token);
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

  const handleApplyChanges = async () => {
    if (!accessToken || dataMode === 'demo') {
      setApplyMessage({ type: 'error', text: 'Please sign in with your Google Account first.' });
      return;
    }

    if (plan.validationErrors.length > 0) {
      setApplyMessage({ type: 'error', text: 'Cannot apply changes: validation errors exist.' });
      return;
    }

    try {
      setApplying(true);

      for (const operation of plan.operations) {
        if (operation.type === 'rename') {
          const result = await applyRenameLabel({
            labelId: operation.targetId,
            newName: renameMap[operation.targetId] ?? '',
            accessToken,
          });
          if (!result.success) {
            throw new Error(result.error ?? 'Failed to rename label');
          }
        } else if (operation.type === 'merge') {
          const result = await applyMergeLabels({
            sourceId: operation.sourceId,
            targetId: operation.targetId,
            accessToken,
          });
          if (!result.success) {
            throw new Error(result.error ?? 'Failed to merge labels');
          }
        }
      }

      setApplyMessage({ type: 'success', text: `Applied ${plan.operations.length} operations successfully.` });
      setTimeout(() => {
        setSelected([]);
        setRenameMap({});
        setMode('preview');
        setApplyMessage(null);
      }, 2000);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to apply changes.';
      setApplyMessage({ type: 'error', text: message });
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
          <select value={dataMode} onChange={(event) => setDataMode(event.target.value as GmailDataMode)}>
            <option value="demo">Demo mode</option>
            <option value="gmail">Google account</option>
          </select>
          {dataMode === 'gmail' && !accessToken ? (
            <>
              <input
                className="token-input"
                value={clientId}
                onChange={(event) => setClientId(event.target.value)}
                placeholder="Enter Google OAuth client ID"
                aria-label="Google OAuth client ID"
                disabled={applying}
              />
              <button onClick={handleGoogleSignIn} disabled={applying} className="sign-in-button">
                {applying ? 'Signing in…' : 'Sign in with Google'}
              </button>
            </>
          ) : accessToken ? (
            <button className="sign-out-button" onClick={() => setAccessToken('')} disabled={applying}>
              Sign out
            </button>
          ) : null}
          <button className={mode === 'preview' ? 'active' : ''} onClick={() => setMode('preview')} disabled={applying}>
            Preview
          </button>
          <button
            className={mode === 'apply' ? 'active' : ''}
            onClick={() => setMode('apply')}
            disabled={applying || dataMode === 'demo'}
          >
            Review
          </button>
          {mode === 'apply' && accessToken && (
            <button className="apply-button" onClick={handleApplyChanges} disabled={applying || plan.operations.length === 0}>
              {applying ? 'Applying…' : 'Apply now'}
            </button>
          )}
        </div>
      </header>

      <section className="panel">
        <div className="operation-summary-top">
          <div className="summary-row">
            <div className="summary-label">Sources:</div>
            <div className="summary-value">
              {getSourceNames().length > 0 ? `${getSourceNames().length} selected · ${getSourceNames().join(', ')}` : '(none selected)'}
            </div>
          </div>
          <div className="summary-row">
            <div className="summary-label">Target:</div>
            <div className="summary-value">{getTargetName() ?? '(none selected)'}</div>
          </div>
          {plan.operations.length > 0 && (
            <div className="summary-row">
              <div className="summary-label">Operations:</div>
              <div className="summary-value">{plan.operations.length} planned</div>
            </div>
          )}
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
                onToggleSelection={toggleSelection}
                renameMap={renameMap}
                onRename={updateRename}
                targetLabelId={targetLabelId}
                onTargetSelect={(id) => setTargetLabelId((current) => (current === id ? '' : id))}
                editingLabelId={editingLabelId}
                onRenameStart={(id) => setEditingLabelId(id)}
                onRenameEnd={(id) => {
                  const value = (renameMap[id] ?? '').trim();
                  if (value) {
                    setEditingLabelId(null);
                    return;
                  }
                  setRenameMap((current) => {
                    const next = { ...current };
                    delete next[id];
                    return next;
                  });
                  setEditingLabelId(null);
                }}
                onDelete={handleDeleteLabel}
                expandedIds={expandedIds}
                onToggleExpand={toggleExpand}
                labelFilter={labelFilter}
              />
            ))}
          </div>
        </div>
        <div className="panel-content">
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
    </main>
  );
};

export default LabelManager;
