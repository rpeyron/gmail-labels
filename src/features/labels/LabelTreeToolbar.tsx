type LabelTreeToolbarProps = {
  labelFilter: string;
  refreshingLabels: boolean;
  applying: boolean;
  onFilterChange: (value: string) => void;
  onExpandAll: () => void;
  onCollapseAll: () => void;
  onRefresh: () => void;
};

const LabelTreeToolbar = ({
  labelFilter,
  refreshingLabels,
  applying,
  onFilterChange,
  onExpandAll,
  onCollapseAll,
  onRefresh,
}: LabelTreeToolbarProps) => (
  <div className="panel-header">
    <div className="tree-toolbar">
      <div className="tree-toolbar-left">
        <div className="label-filter-wrap">
          <input className="label-filter-input" type="text" value={labelFilter} onChange={(event) => onFilterChange(event.target.value)} placeholder="Filter labels" aria-label="Filter labels" />
          {labelFilter && <button type="button" className="label-filter-clear" onClick={() => onFilterChange('')} aria-label="Clear filter" title="Clear filter">×</button>}
        </div>
        <button type="button" className="mini-button" onClick={onExpandAll}>Expand all</button>
        <button type="button" className="mini-button" onClick={onCollapseAll}>Collapse all</button>
        <button type="button" className="mini-button" onClick={onRefresh} disabled={applying || refreshingLabels}>{refreshingLabels ? 'Refreshing…' : 'Refresh labels'}</button>
      </div>
    </div>
  </div>
);

export default LabelTreeToolbar;
