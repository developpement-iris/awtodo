import { useState } from "react";
import { assignTask, claimTask, completeTask, rejectTask, startTask, validateTask } from "../../api/client";
import type { Task } from "../../types/watodo";

export function useTaskTransitions(
  onUpdated: (task: Task) => void,
  onRemoved: (taskId: string) => void,
  onSuccess?: (message: string) => void,
) {
  const [rejectingTask, setRejectingTask] = useState<Task | null>(null);
  const [completingTask, setCompletingTask] = useState<Task | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingTaskId, setPendingTaskId] = useState<string | null>(null);

  async function handleValidate(task: Task) {
    setActionError(null);
    setPendingTaskId(task.id);
    try {
      onUpdated(await validateTask(task.id));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "La validation a échoué.");
    } finally {
      setPendingTaskId(null);
    }
  }

  async function handleClaim(task: Task) {
    setActionError(null);
    setPendingTaskId(task.id);
    try {
      onUpdated(await claimTask(task.id));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "L'auto-attribution a échoué.");
    } finally {
      setPendingTaskId(null);
    }
  }

  async function handleAssign(task: Task, assigneeId: string) {
    setActionError(null);
    setPendingTaskId(task.id);
    try {
      onUpdated(await assignTask(task.id, assigneeId));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "L'attribution a échoué.");
    } finally {
      setPendingTaskId(null);
    }
  }

  async function handleStart(task: Task) {
    setActionError(null);
    setPendingTaskId(task.id);
    try {
      onUpdated(await startTask(task.id));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Le démarrage a échoué.");
    } finally {
      setPendingTaskId(null);
    }
  }

  async function handleReject(reason: string) {
    if (!rejectingTask) return;
    const task = rejectingTask;
    setRejectingTask(null);
    setActionError(null);
    setPendingTaskId(task.id);

    try {
      await rejectTask(task.id, reason);
      onRemoved(task.id);
      onSuccess?.("Tâche rejetée.");
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Le rejet a échoué.");
    } finally {
      setPendingTaskId(null);
    }
  }

  async function handleComplete(timeSpent: string) {
    if (!completingTask) return;
    const task = completingTask;
    setCompletingTask(null);
    setActionError(null);
    setPendingTaskId(task.id);

    try {
      await completeTask(task.id, timeSpent);
      onRemoved(task.id);
      onSuccess?.("Tâche clôturée.");
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "La clôture a échoué.");
    } finally {
      setPendingTaskId(null);
    }
  }

  return {
    rejectingTask,
    setRejectingTask,
    completingTask,
    setCompletingTask,
    actionError,
    setActionError,
    pendingTaskId,
    handleValidate,
    handleClaim,
    handleAssign,
    handleStart,
    handleReject,
    handleComplete,
  };
}
