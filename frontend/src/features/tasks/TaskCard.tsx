import { useDraggable } from "@dnd-kit/core";
import { XCircle } from "lucide-react";
import { InlineEditableText } from "../../components/InlineEditableText";
import { StatusBadge } from "../../components/StatusBadge";
import { TypeBadge } from "../../components/TypeBadge";
import { priorityTone } from "../../lib/badges";
import type { Task } from "../../types/watodo";
import "./TaskCard.css";

interface TaskCardProps {
  task: Task;
  onOpen: (task: Task) => void;
  onReject?: (task: Task) => void;
  onRename: (task: Task, title: string) => void;
  pending?: boolean;
}

export function TaskCard({ task, onOpen, onReject, onRename, pending = false }: TaskCardProps) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: task.id,
    data: { task },
    disabled: pending,
  });

  const style = transform
    ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` }
    : undefined;

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`task-card${isDragging ? " task-card--dragging" : ""}${pending ? " task-card--pending" : ""}`}
      {...listeners}
      {...attributes}
    >
      <div
        className="task-card__body"
        role="button"
        tabIndex={0}
        onClick={() => onOpen(task)}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            onOpen(task);
          }
        }}
      >
        <InlineEditableText
          value={task.title}
          onSave={(title) => onRename(task, title)}
          ariaLabel="Titre de la tâche"
          disabled={pending || !task.permissions.can_rename}
          className="task-card__title"
        />
        {task.external_reference_id && <span className="task-card__ref">{task.external_reference_id}</span>}
        <span className="task-card__badges">
          <TypeBadge type={task.task_type} label={task.task_type_display} />
          <StatusBadge label={task.priority_display} tone={priorityTone(task.priority)} />
        </span>
        {task.assignee && (
          <span className="task-card__assignee">
            {`${task.assignee.first_name} ${task.assignee.last_name}`.trim() || task.assignee.username}
          </span>
        )}
      </div>
      {onReject && (
        <button
          type="button"
          className="task-card__reject"
          onClick={() => onReject(task)}
          aria-label="Rejeter la tâche"
          title="Rejeter"
          disabled={pending}
        >
          <XCircle size={14} strokeWidth={1.75} aria-hidden="true" />
        </button>
      )}
    </div>
  );
}
