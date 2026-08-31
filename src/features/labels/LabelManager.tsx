import { useEffect, useMemo, useState } from 'react';
import { Tree } from 'react-arborist';
import { buildLabelPlan, flattenLabelTree, type LabelNode } from '../../domain/labelOperations';
import { loadGmailLabels, type GmailDataMode } from '../../infrastructure/gmailApi';
import { requestGoogleAccessToken } from '../../infrastructure/googleAuth';
import { applyMergeLabels, applyRenameLabel } from '../../infrastructure/gmailOperations';

type ArboristNode = LabelNode & {
  children?: ArboristNode[];
};

type TreeRowProps = {
  node: ArboristNode;
  style: React.CSSProperties;
  selectedIds: string[];
  onToggleSelection: (id: string) => void;
  renameMap: Record<string, string>;
  onRename: (id: string, value: string) => void;
  targetLabelId: string;
  onTargetSelect: (id: string) => void;
  showTargetColumn?: boolean;
};

const TreeRow = ({ node, style, selectedIds, onToggleSelection, renameMap, onRename, targetLabelId, onTargetSelect, showTargetColumn = false }: TreeRowProps) => {
  return (
    <div style={style} className="tree-row">
      <div className="tree-cell">
        <label className="tree-item">
          {showTargetColumn ? (
            <input
              type="radio"
              name="target-label"
              checked={targetLabelId === node.id}
              onChange={() => onTargetSelect(node.id)}
            />
          ) : (
            <input type="checkbox" checked={selectedIds.includes(node.id)} onChange={() => onToggleSelection(node.id)} />
          )}
          <span className="tree-label">{node.name}</span>
        </label>
      </div>
      <div className="tree-cell tree-meta">{node.mailCount ?? 0} mails</div>
      <div className="tree-cell">
        {showTargetColumn ? (
          <span className="tree-pill">Target</span>
        ) : renameMap[node.id] !== undefined ? (
          <input
            className="rename-input"
            value={renameMap[node.id] ?? ''}
            onChange={(event) => onRename(node.id, event.target.value)}
            placeholder="Rename"
          />
        ) : (
          <span className="tree-pill">Source</span>
        )}
      </div>
    </div>
  );
};

type Props = {
  initialLabels?: LabelNode[];
};

const LabelManager = ({ initialLabels }: Props) => {
  const [labels, setLabels] = useState<LabelNode[]>(initialLabels ?? []);
  const [selected, setSelected] = useState<string[]>([]);
  const [targetLabelId, setTargetLabelId] = useState('work');
  const [renameMap, setRenameMap] = useState<Record<string, string>>({});
  const [mode, setMode] = useState<'preview' | 'apply'>('preview');
  const [dataMode, setDataMode] = useState<GmailDataMode>('demo');
  const [accessToken, setAccessToken] = useState('');
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);
  const [clientId, setClientId] = useState('');
  const [applyMessage, setApplyMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

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
        <div className="panel-header">
          <h2>Label tree</h2>
          <span>{selected.length} selected</span>
        </div>
        <div className="tree-shell">
          <div className="tree-header">
            <div className="tree-cell">Label</div>
            <div className="tree-cell">Mails</div>
            <div className="tree-cell">Selection</div>
          </div>
          <Tree<ArboristNode>
            data={labels as ArboristNode[]}
            openByDefault
            width="100%"
            height={360}
            rowHeight={44}
            paddingTop={8}
            paddingBottom={8}
            children={(node) => (
              <TreeRow
                node={node.node.data}
                style={node.style}
                selectedIds={selected}
                onToggleSelection={toggleSelection}
                renameMap={renameMap}
                onRename={updateRename}
                targetLabelId={targetLabelId}
                onTargetSelect={setTargetLabelId}
                showTargetColumn={false}
              />
            )}
          />
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h2>Target label</h2>
          <select value={targetLabelId} onChange={(event) => setTargetLabelId(event.target.value)}>
            {flattened.map((label) => (
              <option key={label.id} value={label.id}>
                {label.name}
              </option>
            ))}
          </select>
        </div>
        <div className="tree-shell">
          <div className="tree-header">
            <div className="tree-cell">Label</div>
            <div className="tree-cell">Mails</div>
            <div className="tree-cell">Target</div>
          </div>
          <Tree<ArboristNode>
            data={labels as ArboristNode[]}
            openByDefault
            width="100%"
            height={240}
            rowHeight={44}
            paddingTop={8}
            paddingBottom={8}
            children={(node) => (
              <TreeRow
                node={node.node.data}
                style={node.style}
                selectedIds={selected}
                onToggleSelection={toggleSelection}
                renameMap={renameMap}
                onRename={updateRename}
                targetLabelId={targetLabelId}
                onTargetSelect={setTargetLabelId}
                showTargetColumn
              />
            )}
          />
        </div>
        <div className="panel-content">
          <div className="operation-summary">
            <p>Mode: {mode === 'preview' ? 'Preview only' : 'Apply changes'}</p>
            <p>{dataMode === 'demo' ? 'Demo mode is active. No Google account is required.' : 'Google account mode is selected.'}</p>
            <p>{plan.canApply ? 'Plan is valid' : 'Plan contains validation errors'}</p>
          </div>
          {plan.validationErrors.length > 0 ? (
            <ul>
              {plan.validationErrors.map((error) => (
                <li key={error}>{error}</li>
              ))}
            </ul>
          ) : null}
          <ul>
            {plan.operations.map((operation) => (
              <li key={`${operation.type}-${'targetId' in operation ? operation.targetId : ''}-${'sourceId' in operation ? operation.sourceId : ''}`}>
                {operation.type === 'rename'
                  ? `Rename ${operation.targetId} -> ${renameMap[operation.targetId] ?? ''}`
                  : `Merge ${operation.sourceId} into ${operation.targetId}`}
              </li>
            ))}
          </ul>
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
