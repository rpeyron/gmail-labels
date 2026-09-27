import type { LabelNode, OperationMode } from '../../domain/labelOperations';

export type LabelTreeRowProps = {
  node: LabelNode;
  depth: number;
  parentId?: string;
  selectedIds: string[];
  onToggleSelection: (id: string) => void;
  onLabelClick: (id: string) => void;
  onLabelDoubleClick: (id: string) => void;
  renameMap: Record<string, string>;
  onRename: (id: string, value: string) => void;
  targetLabelId: string;
  onTargetSelect: (id: string) => void;
  editingLabelId: string | null;
  onRenameStart: (id: string) => void;
  onRenameEnd: (id: string) => void;
  onDelete: (id: string) => void;
  onOpenInGmail: (id: string) => void;
  onRefreshMailCount: (id: string) => void;
  expandedIds: Record<string, boolean>;
  onToggleExpand: (id: string) => void;
  labelFilter: string;
  isLocked: boolean;
  activeOperation: OperationMode | null;
};

const hasMatchingDescendantPath = (node: LabelNode, query: string): boolean =>
  (node.children ?? []).some((child) => child.name.toLowerCase().includes(query) || hasMatchingDescendantPath(child, query));

const LabelTreeRow = ({
  node,
  depth,
  parentId,
  selectedIds,
  onToggleSelection,
  onLabelClick,
  onLabelDoubleClick,
  renameMap,
  onRename,
  targetLabelId,
  onTargetSelect,
  editingLabelId,
  onRenameStart,
  onRenameEnd,
  onDelete,
  onOpenInGmail,
  onRefreshMailCount,
  expandedIds,
  onToggleExpand,
  labelFilter,
  isLocked,
  activeOperation,
}: LabelTreeRowProps) => {
  const isSystemLabel = Boolean(node.isSystem);
  const isSource = selectedIds.includes(node.id);
  const isTarget = targetLabelId === node.id;
  const isInternal = (node.children?.length ?? 0) > 0;
  const isRenameActive = !isSystemLabel && node.mailCount !== 0;
  const isDeleteActive = !isSystemLabel && node.mailCount === 0 && !isInternal;
  const currentRenameValue = renameMap[node.id] ?? node.name;
  const labelIndent = depth * 18;
  const hasTargetSelection = Boolean(targetLabelId);
  const normalizedFilter = labelFilter.trim().toLowerCase();
  const rowMatchesFilter = !normalizedFilter || node.name.toLowerCase().includes(normalizedFilter);
  const hasMatchingDescendant = !normalizedFilter ? false : hasMatchingDescendantPath(node, normalizedFilter);
  const isFilterParentDimmed = Boolean(normalizedFilter) && !rowMatchesFilter && hasMatchingDescendant;

  return (
    <>
      <div
        className={`tree-row ${isTarget ? 'tree-row-targeted' : ''} ${isFilterParentDimmed ? 'tree-row-filter-dimmed' : ''} ${isSystemLabel ? 'tree-row-system' : ''}`}
        data-tree-label-id={node.id}
        data-tree-parent-id={parentId ?? ''}
        role="row"
      >
        <div
          className={`tree-cell tree-label-cell ${isSystemLabel ? 'tree-label-cell-system' : ''}`}
          style={{ paddingLeft: `${labelIndent}px` }}
          role="treeitem"
          aria-level={depth + 1}
          onClick={() => onLabelClick(node.id)}
          onDoubleClick={() => onLabelDoubleClick(node.id)}
        >
          {isInternal ? (
            <button
              type="button"
              className="tree-toggle"
              onClick={(event) => {
                event.stopPropagation();
                onToggleExpand(node.id);
              }}
              onDoubleClick={(event) => event.stopPropagation()}
              aria-label={expandedIds[node.id] ? 'Collapse' : 'Expand'}
            >
              {expandedIds[node.id] ? '▾' : '▸'}
            </button>
          ) : (
            <span className="tree-toggle tree-toggle-leaf">•</span>
          )}
          <span className="tree-label-icon" aria-hidden="true">🏷️</span>
          <span className="tree-label">{node.name}</span>
        </div>
        <div
          className="tree-cell tree-meta tree-meta-refreshable"
          role="button"
          tabIndex={0}
          onClick={() => onRefreshMailCount(node.id)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault();
              onRefreshMailCount(node.id);
            }
          }}
          aria-label={`Refresh mail count for ${node.name}`}
          title="Refresh mail count"
        >
          {node.mailCount === undefined ? '—' : `${node.mailCount} mails`}
        </div>
        <div className="tree-cell" role="cell">
          <label className={`tree-checkbox ${isSource ? 'is-selected' : ''}`}>
            <input type="checkbox" checked={isSource} disabled={isSystemLabel || isLocked || Boolean(activeOperation && activeOperation !== 'merge')} onChange={() => onToggleSelection(node.id)} />
            <span>Source</span>
          </label>
        </div>
        <div className="tree-cell" role="cell">
          <label className={`tree-radio ${isTarget ? 'is-selected' : ''} ${hasTargetSelection && !isTarget ? 'is-dimmed' : ''}`}>
            <input type="radio" name="target-label" checked={isTarget} disabled={isSystemLabel || isLocked || Boolean(activeOperation && activeOperation !== 'merge')} onClick={() => onTargetSelect(node.id)} />
            <span>Target</span>
          </label>
        </div>
        <div className="tree-cell tree-actions-cell" role="cell">
          <button
            type="button"
            className="action-button action-button-open"
            onClick={() => onOpenInGmail(node.id)}
            aria-label={`Open ${node.name} in Gmail`}
            title="Open in Gmail"
          >
            <span aria-hidden="true">↗</span>
          </button>
          {editingLabelId === node.id ? (
            <input
              className="rename-input"
              value={currentRenameValue}
              onChange={(event) => onRename(node.id, event.target.value)}
              onBlur={() => onRenameEnd(node.id)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') onRenameEnd(node.id);
              }}
              autoFocus
              placeholder="New name"
            />
          ) : (
            <>
              {isRenameActive && <button type="button" className="action-button action-button-rename" onClick={() => onRenameStart(node.id)} disabled={isSystemLabel || isLocked || Boolean(activeOperation && activeOperation !== 'rename')} aria-label={`Rename ${node.name}`} title="Rename"><span aria-hidden="true">✏️</span></button>}
              {isDeleteActive && <button type="button" className="action-button action-button-delete" onClick={() => onDelete(node.id)} disabled={isSystemLabel || isLocked || Boolean(activeOperation && activeOperation !== 'delete')} aria-label={`Delete ${node.name}`} title="Delete"><span aria-hidden="true">🗑️</span></button>}
            </>
          )}
        </div>
      </div>
      {isInternal && expandedIds[node.id] && (node.children ?? []).map((child) => (
        <LabelTreeRow
          key={child.id}
          node={child}
          depth={depth + 1}
          parentId={node.id}
          selectedIds={selectedIds}
          onToggleSelection={onToggleSelection}
          onLabelClick={onLabelClick}
          onLabelDoubleClick={onLabelDoubleClick}
          renameMap={renameMap}
          onRename={onRename}
          targetLabelId={targetLabelId}
          onTargetSelect={onTargetSelect}
          editingLabelId={editingLabelId}
          onRenameStart={onRenameStart}
          onRenameEnd={onRenameEnd}
          onDelete={onDelete}
          onOpenInGmail={onOpenInGmail}
          onRefreshMailCount={onRefreshMailCount}
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

export default LabelTreeRow;
