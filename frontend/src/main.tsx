import { MotionConfig } from 'motion/react'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { CurrentUserProvider } from './context/CurrentUserContext.tsx'
import { ToastProvider } from './context/ToastContext.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {/* reducedMotion="user" : respecte prefers-reduced-motion pour tous les
        composants motion.* de l'app sans avoir à appeler useReducedMotion()
        partout — voir docs/charte-graphique.md > "Chargements et boutons". */}
    <MotionConfig reducedMotion="user" transition={{ duration: 0.15, ease: 'easeOut' }}>
      <ToastProvider>
        <CurrentUserProvider>
          <App />
        </CurrentUserProvider>
      </ToastProvider>
    </MotionConfig>
  </StrictMode>,
)
