import { Brand } from "./Brand";

type HeaderProps = {
  onChangeToken: () => void;
};

/** Shows the application identity and the current API authentication state. */
export function Header({ onChangeToken }: HeaderProps) {
  return (
    <header className="topbar">
      <Brand />
      <div className="topbar-actions">
        <span className="api-status"><i /> API token saved</span>
        <button className="button-link" type="button" onClick={onChangeToken}>Change</button>
      </div>
    </header>
  );
}
