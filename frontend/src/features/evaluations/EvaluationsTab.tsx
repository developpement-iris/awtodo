import { ArrowLeft, ClipboardList, Plus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { createEvaluationSheet, getEvaluationSheet, getEvaluationSheets } from "../../api/client";
import { Checkbox } from "../../components/Checkbox";
import { PromptDialog } from "../../components/PromptDialog";
import { StatusBadge } from "../../components/StatusBadge";
import { useToast } from "../../context/ToastContext";
import type { Project } from "../../types/watodo";
import type { EvaluationSheetDetail, EvaluationSheetStatus, EvaluationSheetSummary } from "../../types/watodo";
import { InternalEvaluationForm } from "./InternalEvaluationForm";
import { SheetEditor } from "./SheetEditor";
import { SheetResults } from "./SheetResults";
import "./EvaluationsTab.css";

const SHEET_STATUS: Record<EvaluationSheetStatus, { label: string; tone: "neutral" | "positive" | "taskAssigned" }> = {
  brouillon: { label: "Brouillon", tone: "neutral" },
  ouverte: { label: "Ouverte", tone: "positive" },
  close: { label: "Close", tone: "taskAssigned" },
  archivee: { label: "Archivée", tone: "neutral" },
};

const DATE = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short", year: "numeric" });

type SubTab = "questions" | "internal" | "results";

interface EvaluationsTabProps {
  project: Project;
}

/** Fiches d'évaluation d'un projet (session du 2026-11-13) : satisfaction
 * client par lien public, et évaluation chef de projet remplie ici. */
export function EvaluationsTab({ project }: EvaluationsTabProps) {
  const { showToast } = useToast();
  const [sheets, setSheets] = useState<EvaluationSheetSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [creating, setCreating] = useState(false);
  const [openSheet, setOpenSheet] = useState<EvaluationSheetDetail | null>(null);
  const [subTab, setSubTab] = useState<SubTab>("questions");
  const canManage = project.permissions.can_manage_evaluations;

  const reload = useCallback(() => {
    getEvaluationSheets(project.id)
      .then((list) => {
        setSheets(list);
        setError(null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Impossible de charger les fiches."));
  }, [project.id]);

  useEffect(() => {
    reload();
  }, [reload]);

  async function open(id: string, tab: SubTab = "questions") {
    try {
      setOpenSheet(await getEvaluationSheet(id));
      setSubTab(tab);
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Impossible d'ouvrir la fiche.");
    }
  }

  async function handleCreate(title: string) {
    setCreating(false);
    try {
      const sheet = await createEvaluationSheet(project.id, title.trim());
      showToast("Fiche créée avec les questions du catalogue.");
      reload();
      setOpenSheet(sheet);
      setSubTab("questions");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Création impossible.");
    }
  }

  function updateSheet(sheet: EvaluationSheetDetail) {
    setOpenSheet(sheet);
    reload();
  }

  if (openSheet) {
    const status = SHEET_STATUS[openSheet.status];
    return (
      <div className="evaluations-tab">
        <button type="button" className="evaluations-tab__back" onClick={() => setOpenSheet(null)}>
          <ArrowLeft size={14} strokeWidth={1.75} aria-hidden="true" />
          Toutes les fiches
        </button>
        <div className="evaluations-tab__sheet-head">
          <h3>{openSheet.title}</h3>
          <StatusBadge label={status.label} tone={status.tone} />
        </div>
        <div className="evaluations-tab__subtabs" role="tablist" aria-label="Parties de la fiche">
          {(
            [
              ["questions", "Questions"],
              ["internal", "Évaluation chef de projet"],
              ["results", `Résultats (${openSheet.response_count})`],
            ] as [SubTab, string][]
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={subTab === id}
              className={subTab === id ? "is-active" : undefined}
              onClick={() => setSubTab(id)}
            >
              {label}
            </button>
          ))}
        </div>
        {subTab === "questions" && <SheetEditor sheet={openSheet} onChange={updateSheet} />}
        {subTab === "internal" && <InternalEvaluationForm sheet={openSheet} onChange={updateSheet} />}
        {subTab === "results" && (
          <SheetResults
            sheet={openSheet}
            projectName={project.name}
            onChanged={() => void open(openSheet.id, "results")}
            onGoToInternal={() => setSubTab("internal")}
          />
        )}
      </div>
    );
  }

  const shown = (sheets ?? []).filter((sheet) => showArchived || sheet.status !== "archivee");
  const archivedCount = (sheets ?? []).filter((sheet) => sheet.status === "archivee").length;

  return (
    <div className="evaluations-tab">
      <div className="evaluations-tab__head">
        <div>
          <h3>Fiches d'évaluation</h3>
          <p>
            Une fiche a deux parties : la satisfaction client, remplie par le client via un lien, et l'évaluation chef
            de projet, remplie ici.
          </p>
        </div>
        {canManage && (
          <button type="button" className="evaluations-tab__new" onClick={() => setCreating(true)}>
            <Plus size={15} strokeWidth={2} aria-hidden="true" />
            Nouvelle fiche
          </button>
        )}
      </div>

      {error && <p className="evaluations-tab__muted">{error}</p>}
      {!error && sheets === null && <p className="evaluations-tab__muted">Chargement…</p>}
      {!error && sheets !== null && shown.length === 0 && (
        <div className="evaluations-tab__empty">
          <ClipboardList size={26} strokeWidth={1.5} aria-hidden="true" />
          <p>
            {canManage
              ? "Aucune fiche pour l'instant. Créez-en une : elle reprend les questions du catalogue, que vous pouvez compléter avant d'envoyer le lien au client."
              : "Aucune fiche d'évaluation pour ce projet."}
          </p>
        </div>
      )}

      {shown.length > 0 && (
        <div className="evaluations-tab__scroll">
          <table className="evaluations-tab__table">
            <thead>
              <tr>
                <th scope="col">Fiche</th>
                <th scope="col">Statut</th>
                <th scope="col">Créée le</th>
                <th scope="col">Réponses</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((sheet) => {
                const status = SHEET_STATUS[sheet.status];
                return (
                  <tr key={sheet.id}>
                    <th scope="row">
                      <button type="button" onClick={() => void open(sheet.id)}>
                        {sheet.title}
                      </button>
                    </th>
                    <td>
                      <StatusBadge label={status.label} tone={status.tone} />
                    </td>
                    <td>{DATE.format(new Date(sheet.created_at))}</td>
                    <td>
                      <button type="button" className="evaluations-tab__count" onClick={() => void open(sheet.id, "results")}>
                        {sheet.response_count}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {archivedCount > 0 && (
        <label className="evaluations-tab__toggle">
          <Checkbox checked={showArchived} onCheckedChange={setShowArchived} aria-label="Afficher les fiches archivées" />
          <span>Afficher les fiches archivées ({archivedCount})</span>
        </label>
      )}

      {creating && (
        <PromptDialog
          title="Nouvelle fiche d'évaluation"
          label="Titre de la fiche"
          placeholder="Ex. Bilan de livraison, vague 1"
          confirmLabel="Créer la fiche"
          onCancel={() => setCreating(false)}
          onConfirm={(value) => {
            if (value.trim()) void handleCreate(value);
          }}
        />
      )}
    </div>
  );
}
