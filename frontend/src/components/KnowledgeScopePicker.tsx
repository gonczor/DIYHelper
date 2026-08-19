import { KnowledgeScope } from "../types";

type KnowledgeScopePickerProps = {
  scope: KnowledgeScope;
  onChange: (scope: KnowledgeScope) => void;
};

/** Lets the user choose which knowledge source should constrain answers. */
export function KnowledgeScopePicker({ scope, onChange }: KnowledgeScopePickerProps) {
  return (
    <section className="sidebar-section">
      <p className="eyebrow">Knowledge scope</p>
      <ScopeOption value="all" label="All DIY knowledge" scope={scope} onChange={onChange} />
      <ScopeOption value="hackaday" label="Hackaday only" scope={scope} onChange={onChange} />
      <ScopeOption value="general" label="General knowledge" scope={scope} onChange={onChange} />
    </section>
  );
}

type ScopeOptionProps = {
  value: KnowledgeScope;
  label: string;
  scope: KnowledgeScope;
  onChange: (scope: KnowledgeScope) => void;
};

/** Displays one selectable knowledge scope. */
function ScopeOption({ value, label, scope, onChange }: ScopeOptionProps) {
  function selectScope() {
    onChange(value);
  }

  return (
    <button
      className={scope === value ? "scope-option active" : "scope-option"}
      type="button"
      onClick={selectScope}
    >
      <span className="scope-radio" />{label}
    </button>
  );
}
