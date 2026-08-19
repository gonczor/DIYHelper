import type { SubmitEvent as ReactSubmitEvent } from "react";

import { Task } from "../api";

type KnowledgeIngestionProps = {
  month: string;
  task: Task | undefined;
  busy: boolean;
  onMonthChange: (month: string) => void;
  onSubmit: (event: ReactSubmitEvent<HTMLFormElement>) => void;
};

/** Provides controls and current status for importing Hackaday knowledge. */
export function KnowledgeIngestion({
  month,
  task,
  busy,
  onMonthChange,
  onSubmit,
}: KnowledgeIngestionProps) {
  function updateMonth(event: React.ChangeEvent<HTMLInputElement>) {
    onMonthChange(event.target.value);
  }

  return (
    <section className="ingestion-card">
      <div className="ingestion-heading">
        <span className="tool-icon">↻</span>
        <div>
          <p className="eyebrow">Knowledge library</p>
          <h2>Import Hackaday</h2>
        </div>
      </div>
      <p>Collect articles for a month. Leave it blank to import last month.</p>
      <form onSubmit={onSubmit}>
        <label htmlFor="target-month">Target month</label>
        <input id="target-month" type="month" value={month} onChange={updateMonth} />
        <button className="secondary-button" disabled={busy} type="submit">
          {busy ? "Starting…" : "Start import"}
        </button>
      </form>
      {task && <TaskStatus task={task} />}
    </section>
  );
}

/** Displays the latest state returned by an ingestion task. */
function TaskStatus({ task }: { task: Task }) {
  return (
    <div className={`task-status ${task.status.toLowerCase()}`} aria-live="polite">
      <i /> Import {task.status.toLowerCase()}
    </div>
  );
}
