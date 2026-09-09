import "./Skeleton.css";

interface SkeletonProps {
  width?: string;
  height?: string;
}

export function Skeleton({ width = "100%", height = "14px" }: SkeletonProps) {
  return <span className="skeleton" style={{ width, height }} />;
}

interface SkeletonRowsProps {
  rows?: number;
}

export function SkeletonRows({ rows = 4 }: SkeletonRowsProps) {
  return (
    <div className="skeleton-rows">
      {Array.from({ length: rows }).map((_, index) => (
        <Skeleton key={index} height="18px" />
      ))}
    </div>
  );
}

interface SkeletonTableProps {
  columns?: number;
  rows?: number;
}

/** Occupe les mêmes dimensions qu'un tableau réel (padding/hauteur de ligne
 * identiques) pour éviter le saut visuel au remplacement par les données. */
export function SkeletonTable({ columns = 5, rows = 4 }: SkeletonTableProps) {
  return (
    <table className="skeleton-table" aria-hidden="true">
      <tbody>
        {Array.from({ length: rows }).map((_, rowIndex) => (
          <tr key={rowIndex}>
            {Array.from({ length: columns }).map((_, colIndex) => (
              <td key={colIndex}>
                <Skeleton height="14px" width={colIndex === 0 ? "80%" : "55%"} />
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

interface SkeletonKanbanProps {
  columns?: number;
  cardsPerColumn?: number;
}

/** Mêmes proportions que `.kanban-board__columns` / `.kanban-column` / `.task-card`. */
export function SkeletonKanban({ columns = 4, cardsPerColumn = 3 }: SkeletonKanbanProps) {
  return (
    <div className="skeleton-kanban" aria-hidden="true">
      {Array.from({ length: columns }).map((_, columnIndex) => (
        <div key={columnIndex} className="skeleton-kanban__column">
          <Skeleton height="12px" width="50%" />
          <div className="skeleton-kanban__cards">
            {Array.from({ length: cardsPerColumn }).map((_, cardIndex) => (
              <div key={cardIndex} className="skeleton-kanban__card">
                <Skeleton height="13px" width="85%" />
                <Skeleton height="11px" width="40%" />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

interface SkeletonCardsProps {
  count?: number;
}

/** Mêmes proportions que `.project-card` — utilisé partout où une grille de
 * cartes se charge (au-delà de ProjectsGrid, qui a son propre skeleton inline). */
export function SkeletonCards({ count = 3 }: SkeletonCardsProps) {
  return (
    <div className="skeleton-cards" aria-hidden="true">
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="skeleton-cards__card">
          <Skeleton width="70%" height="19px" />
          <Skeleton width="90%" />
          <Skeleton width="40%" />
        </div>
      ))}
    </div>
  );
}
