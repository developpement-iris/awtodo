import { AnimatePresence, motion } from "motion/react";
import type { ReactNode } from "react";

interface LoadingTransitionProps {
  loading: boolean;
  skeleton: ReactNode;
  children: ReactNode;
}

// Fondu + légère mise à l'échelle entre le skeleton et le contenu réel (voir
// docs/charte-graphique.md > "Chargements et boutons") — prolonge les
// skeletons dimensionnés déjà en place sans les refaire. `reducedMotion`
// (voir MotionConfig dans main.tsx) désactive automatiquement l'animation
// pour un utilisateur qui préfère moins de mouvement.
export function LoadingTransition({ loading, skeleton, children }: LoadingTransitionProps) {
  return (
    <AnimatePresence mode="wait" initial={false}>
      {loading ? (
        <motion.div key="skeleton" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          {skeleton}
        </motion.div>
      ) : (
        <motion.div
          key="content"
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0 }}
        >
          {children}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
