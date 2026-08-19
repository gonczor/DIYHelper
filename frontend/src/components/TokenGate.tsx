import type { SubmitEvent as ReactSubmitEvent } from "react";

import { Brand } from "./Brand";

type TokenGateProps = {
  draftToken: string;
  onDraftTokenChange: (value: string) => void;
  onSubmit: (event: ReactSubmitEvent<HTMLFormElement>) => void;
};

/** Collects the API token before the authenticated workspace is displayed. */
export function TokenGate({ draftToken, onDraftTokenChange, onSubmit }: TokenGateProps) {
  function updateToken(event: React.ChangeEvent<HTMLInputElement>) {
    onDraftTokenChange(event.target.value);
  }

  return (
    <main className="gate">
      <div className="gate-card">
        <Brand />
        <p className="eyebrow">Welcome to the workshop</p>
        <h1>Your practical DIY research assistant.</h1>
        <p>Connect to your local DIY Helper API to ask questions and manage its knowledge library.</p>
        <form onSubmit={onSubmit}>
          <label htmlFor="auth-token">API access token</label>
          <input
            id="auth-token"
            type="password"
            autoComplete="current-password"
            placeholder="Enter X-Auth-Token"
            value={draftToken}
            onChange={updateToken}
            autoFocus
          />
          <button className="primary-button" type="submit" disabled={!draftToken.trim()}>
            Enter workshop <span>→</span>
          </button>
        </form>
        <small>Stored only in this browser. You can remove it at any time.</small>
      </div>
      <div className="gate-decoration" aria-hidden="true">
        <span>01</span><span>MEASURE TWICE</span>
      </div>
    </main>
  );
}
