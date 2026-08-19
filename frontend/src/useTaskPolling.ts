import { Dispatch, SetStateAction, useEffect } from "react";

import { getTask, Task } from "./api";

const POLLING_INTERVAL_MS = 2_000;

/** Polls an active ingestion task until it succeeds or fails. */
export function useTaskPolling(
  token: string,
  task: Task | undefined,
  setTask: Dispatch<SetStateAction<Task | undefined>>,
  setError: Dispatch<SetStateAction<string>>,
): void {
  useEffect(pollActiveTask, [token, task, setTask, setError]);

  function pollActiveTask() {
    if (!task || !isActive(task)) return;

    const activeTask = task;
    let cancelled = false;
    let timeout: ReturnType<typeof setTimeout>;

    async function refreshTask() {
      try {
        const updatedTask = await getTask(token, activeTask.id);
        if (cancelled) return;
        setTask(updatedTask);
        if (isActive(updatedTask)) scheduleRefresh();
      } catch (caughtError) {
        if (cancelled) return;
        setError(errorMessage(caughtError));
        scheduleRefresh();
      }
    }

    function scheduleRefresh() {
      timeout = setTimeout(refreshTask, POLLING_INTERVAL_MS);
    }

    function stopPolling() {
      cancelled = true;
      clearTimeout(timeout);
    }

    scheduleRefresh();
    return stopPolling;
  }
}

function isActive(task: Task): boolean {
  return task.status === "PENDING" || task.status === "RUNNING";
}

function errorMessage(error: unknown): string {
  return error instanceof Error
    ? `Could not refresh import status: ${error.message}`
    : "Could not refresh import status.";
}
