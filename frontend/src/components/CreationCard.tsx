import { Plus } from "lucide-react";
import { motion } from "motion/react";
import "./CreationCard.css";

interface CreationCardProps {
  label: string;
  onClick: () => void;
  compact?: boolean;
}

export function CreationCard({ label, onClick, compact = false }: CreationCardProps) {
  return (
    <motion.button
      type="button"
      className={`creation-card${compact ? " creation-card--compact" : ""}`}
      onClick={onClick}
      whileTap={{ scale: 0.96 }}
    >
      <Plus size={compact ? 16 : 20} strokeWidth={1.75} aria-hidden="true" />
      <span>{label}</span>
    </motion.button>
  );
}
