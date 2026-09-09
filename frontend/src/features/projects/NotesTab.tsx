import { updateProjectNotepad } from "../../api/client";
import { InlineEditableTextarea } from "../../components/InlineEditableTextarea";
import { formatRelativeTime } from "../../lib/relativeTime";
import type { Project } from "../../types/watodo";
import "./NotesTab.css";

interface NotesTabProps {
  project: Project;
  onSaved: (project: Project) => void;
}

export function NotesTab({ project, onSaved }: NotesTabProps) {
  const content = project.notepad_content;
  const updatedAt = project.notepad_updated_at;
  const canEdit = project.permissions.can_edit_notepad;

  async function handleSave(next: string) {
    const updated = await updateProjectNotepad(project.id, { notepad_content: next });
    onSaved(updated);
  }

  return (
    <div className="notes-tab">
      <div className="notes-tab__header">
        <span className="notes-tab__updated">
          {updatedAt ? <>Dernière modification {formatRelativeTime(updatedAt)}</> : "Jamais modifié"}
        </span>
      </div>

      <InlineEditableTextarea
        value={content}
        onSave={handleSave}
        ariaLabel="Bloc-notes du projet"
        disabled={!canEdit}
        emptyLabel="Notes en vrac, idées, points à ne pas oublier… cliquez pour commencer."
        rows={16}
      />
    </div>
  );
}
