import { Check, Copy, Eye, EyeOff } from "lucide-react";
import { useState } from "react";
import {
  addSheetQuestion,
  archiveSheetQuestion,
  getEvaluationSheet,
  moveSheetQuestion,
  transitionEvaluationSheet,
  updateEvaluationSheet,
  updateSheetQuestion,
} from "../../api/client";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { InlineEditableText } from "../../components/InlineEditableText";
import { InlineEditableTextarea } from "../../components/InlineEditableTextarea";
import { useToast } from "../../context/ToastContext";
import type {
  EvaluationAnswerValue,
  EvaluationQuestion,
  EvaluationSection,
  EvaluationSheetDetail,
} from "../../types/watodo";
import { AnswerField } from "./AnswerField";
import { SECTION_LABELS } from "./answerFormat";
import { QuestionSectionList } from "./QuestionSectionList";
import { visibleQuestionIds } from "./visibility";

type Transition = "open" | "close" | "reopen" | "archive" | "rotate-link";

const CONFIRMATIONS: Partial<Record<Transition, { title: string; message: string; label: string; danger?: boolean }>> = {
  open: {
    title: "Ouvrir la fiche ?",
    message: "Le lien client sera créé et les questions ne seront plus modifiables.",
    label: "Ouvrir et créer le lien",
  },
  "rotate-link": {
    title: "Régénérer le lien ?",
    message: "L'ancien lien cessera aussitôt de fonctionner. Envoyez le nouveau aux clients qui n'ont pas encore répondu.",
    label: "Régénérer",
    danger: true,
  },
  close: {
    title: "Clôturer la fiche ?",
    message: "Le formulaire client n'acceptera plus de réponses. Vous pourrez la rouvrir.",
    label: "Clôturer",
  },
  archive: {
    title: "Archiver la fiche ?",
    message: "Elle sort de la liste. Ses résultats restent comptés dans les statistiques.",
    label: "Archiver",
  },
};

const SUCCESS: Record<Transition, string> = {
  open: "Fiche ouverte : le lien client est prêt.",
  close: "Fiche close.",
  reopen: "Fiche rouverte.",
  archive: "Fiche archivée.",
  "rotate-link": "Nouveau lien créé.",
};

interface SheetEditorProps {
  sheet: EvaluationSheetDetail;
  onChange: (sheet: EvaluationSheetDetail) => void;
}

export function SheetEditor({ sheet, onChange }: SheetEditorProps) {
  const { showToast } = useToast();
  const [confirm, setConfirm] = useState<Transition | null>(null);
  const [copied, setCopied] = useState(false);
  const [preview, setPreview] = useState(false);
  const [previewAnswers, setPreviewAnswers] = useState<Record<string, EvaluationAnswerValue>>({});
  const canManage = sheet.permissions.can_manage;
  const draft = sheet.status === "brouillon";
  const editable = canManage && sheet.status !== "archivee";
  const link = sheet.public_path ? `${window.location.origin}${sheet.public_path}` : null;
  const active = sheet.questions.filter((question) => question.status === "active");
  const clientQuestions = active.filter((question) => question.section === "client");

  async function refresh() {
    onChange(await getEvaluationSheet(sheet.id));
  }

  async function transition(action: Transition) {
    setConfirm(null);
    try {
      onChange(await transitionEvaluationSheet(sheet.id, action));
      showToast(SUCCESS[action]);
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Action impossible.");
    }
  }

  async function save(changes: { title?: string; client_intro?: string }) {
    try {
      onChange(await updateEvaluationSheet(sheet.id, changes));
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Enregistrement impossible.");
    }
  }

  async function copyLink() {
    if (!link) return;
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      showToast("Copie impossible : sélectionnez le lien à la main.");
    }
  }

  async function act(action: () => Promise<unknown>) {
    try {
      await action();
      await refresh();
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Action impossible.");
    }
  }

  const previewVisible = visibleQuestionIds(clientQuestions, previewAnswers);
  const confirmation = confirm ? CONFIRMATIONS[confirm] : null;

  return (
    <div className="sheet-editor">
      <div className="sheet-editor__fields">
        <label className="sheet-editor__field">
          <span>Titre</span>
          <InlineEditableText
            value={sheet.title}
            onSave={(title) => void save({ title })}
            ariaLabel="Titre de la fiche"
            disabled={!editable}
          />
        </label>
        <div className="sheet-editor__field">
          <span>Message d'accueil affiché au client</span>
          <InlineEditableTextarea
            value={sheet.client_intro}
            onSave={(client_intro) => void save({ client_intro })}
            ariaLabel="Message d'accueil affiché au client"
            disabled={!editable}
            rows={3}
            placeholder="Ex. Merci de prendre 2 minutes pour nous dire comment s'est passé le projet."
            emptyLabel="Aucun message d'accueil."
          />
        </div>
      </div>

      {canManage && (
        <div className="sheet-editor__lifecycle">
          {draft && (
            <>
              <p>
                Complétez les questions, puis ouvrez la fiche pour obtenir le lien à envoyer au client. Une fois ouverte,
                les questions ne changent plus.
              </p>
              <div className="sheet-editor__buttons">
                <button type="button" className="sheet-editor__primary" onClick={() => setConfirm("open")}>
                  Ouvrir et créer le lien
                </button>
                <button type="button" onClick={() => setConfirm("archive")}>
                  Archiver
                </button>
              </div>
            </>
          )}
          {sheet.status === "ouverte" && link && (
            <>
              <span className="sheet-editor__link-label">Lien à envoyer au client</span>
              <div className="sheet-editor__link">
                <input type="text" readOnly value={link} aria-label="Lien client" onFocus={(event) => event.target.select()} />
                <button type="button" onClick={() => void copyLink()}>
                  {copied ? <Check size={14} strokeWidth={2} aria-hidden="true" /> : <Copy size={14} strokeWidth={1.75} aria-hidden="true" />}
                  {copied ? "Copié" : "Copier"}
                </button>
              </div>
              <div className="sheet-editor__buttons">
                <button type="button" onClick={() => setConfirm("close")}>
                  Clôturer
                </button>
                <button type="button" onClick={() => setConfirm("rotate-link")}>
                  Régénérer le lien
                </button>
              </div>
            </>
          )}
          {sheet.status === "close" && (
            <>
              <p>Le formulaire client n'accepte plus de réponses.</p>
              <div className="sheet-editor__buttons">
                <button type="button" className="sheet-editor__primary" onClick={() => void transition("reopen")}>
                  Rouvrir
                </button>
                <button type="button" onClick={() => setConfirm("archive")}>
                  Archiver
                </button>
              </div>
            </>
          )}
          {sheet.status === "archivee" && <p>Fiche archivée : consultation seule.</p>}
        </div>
      )}

      {(["client", "interne"] as EvaluationSection[]).map((section) => (
        <QuestionSectionList
          key={section}
          section={section}
          title={SECTION_LABELS[section]}
          questions={active.filter((question) => question.section === section)}
          all={active}
          editable={(question: EvaluationQuestion) => canManage && draft && !question.is_generic}
          canAdd={canManage && draft}
          canReorder={canManage && draft}
          onCreate={async (input) => {
            await addSheetQuestion(sheet.id, input);
            await refresh();
            showToast("Question ajoutée à la fiche.");
          }}
          onUpdate={async (question, input) => {
            const { section: _section, ...changes } = input;
            void _section;
            await updateSheetQuestion(sheet.id, question.id, changes);
            await refresh();
          }}
          onArchive={(question) => act(() => archiveSheetQuestion(sheet.id, question.id))}
          onMove={(question, direction) => act(() => moveSheetQuestion(sheet.id, question.id, direction))}
          emptyLabel={section === "client" ? "Ajoutez au moins une question client avant d'ouvrir la fiche." : "Aucune question."}
        />
      ))}
      {draft && canManage && (
        <p className="sheet-editor__hint">
          Les questions marquées « Générique » viennent du catalogue du groupe : elles ne se modifient pas ici, pour que
          les statistiques restent comparables d'une fiche à l'autre.
        </p>
      )}

      {clientQuestions.length > 0 && (
        <section className="sheet-editor__preview">
          <button type="button" className="sheet-editor__preview-toggle" onClick={() => setPreview((value) => !value)} aria-expanded={preview}>
            {preview ? <EyeOff size={14} strokeWidth={1.75} aria-hidden="true" /> : <Eye size={14} strokeWidth={1.75} aria-hidden="true" />}
            {preview ? "Masquer l'aperçu" : "Aperçu du formulaire client"}
          </button>
          {preview && (
            <div className="sheet-editor__preview-body">
              <p className="sheet-editor__hint">Aperçu : rien n'est enregistré. Testez les questions conditionnelles.</p>
              {clientQuestions
                .filter((question) => previewVisible.has(question.id))
                .map((question) => (
                  <AnswerField
                    key={question.id}
                    question={question}
                    value={previewAnswers[question.id]}
                    onChange={(value) => setPreviewAnswers((current) => ({ ...current, [question.id]: value }))}
                  />
                ))}
            </div>
          )}
        </section>
      )}

      {confirm && confirmation && (
        <ConfirmDialog
          title={confirmation.title}
          message={confirmation.message}
          confirmLabel={confirmation.label}
          danger={confirmation.danger}
          onCancel={() => setConfirm(null)}
          onConfirm={() => void transition(confirm)}
        />
      )}
    </div>
  );
}
