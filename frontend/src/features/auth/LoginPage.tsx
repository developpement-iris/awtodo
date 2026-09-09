import { useEffect, useRef, useState } from "react";
import { useCurrentUser } from "../../context/CurrentUserContext";
import { useToast } from "../../context/ToastContext";
import "./LoginPage.css";

function initials(label: string): string {
  const parts = label.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

function displayName(user: { username: string; first_name: string; last_name: string }): string {
  return `${user.first_name} ${user.last_name}`.trim() || user.username;
}

// Portage direct de `watodo-logo-animation.html` (fourni par l'utilisateur,
// vérifié fonctionnel de son côté) — la première tentative en `motion`
// déclaratif (`pathLength` + tableau `times`) ne rejouait pas correctement.
// Reproduit donc le mécanisme d'origine tel quel : transition CSS sur
// `stroke-dashoffset` pilotée à la main (pas le prop `pathLength` de motion),
// classe CSS togglée pour le rebond du point. `motion/react` n'est plus
// utilisé ici — `prefers-reduced-motion` est donc vérifié manuellement
// (le réglage global `reducedMotion="user"` de `main.tsx` ne s'applique
// qu'aux composants `motion.*`, pas à cette animation DOM directe).
const DRAW_DURATION = 1900;
const HOLD_DURATION = 1600;

function AwtodoSignature() {
  const pathRef = useRef<SVGPathElement>(null);
  const dotRef = useRef<SVGCircleElement>(null);

  useEffect(() => {
    const path = pathRef.current;
    const dot = dotRef.current;
    if (!path || !dot) return;

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      path.style.strokeDasharray = "none";
      path.style.strokeDashoffset = "0";
      dot.style.opacity = "1";
      return;
    }

    let cancelled = false;
    let loopTimer = 0;
    let jumpTimer = 0;
    const length = path.getTotalLength();

    function reset() {
      path!.style.transition = "none";
      path!.style.strokeDasharray = String(length);
      path!.style.strokeDashoffset = String(length);
      dot!.classList.remove("login-page__signature-dot--jump");
      path!.getBoundingClientRect();
    }

    function play() {
      reset();
      requestAnimationFrame(() => {
        if (cancelled) return;
        path!.style.transition = `stroke-dashoffset ${DRAW_DURATION}ms cubic-bezier(0.65, 0, 0.35, 1)`;
        path!.style.strokeDashoffset = "0";
      });
      jumpTimer = window.setTimeout(() => {
        if (!cancelled) dot!.classList.add("login-page__signature-dot--jump");
      }, DRAW_DURATION - 150);
    }

    function loop() {
      play();
      loopTimer = window.setTimeout(loop, DRAW_DURATION + HOLD_DURATION);
    }

    loop();

    return () => {
      cancelled = true;
      window.clearTimeout(loopTimer);
      window.clearTimeout(jumpTimer);
    };
  }, []);

  return (
    <svg viewBox="0 0 1222 916" className="login-page__signature-svg" aria-hidden="true">
      <path
        ref={pathRef}
        className="login-page__signature-path"
        d="M 110 250
          C 20 400, 20 610, 130 690
          C 210 750, 300 630, 360 480
          C 395 400, 420 370, 455 415
          C 495 470, 515 610, 560 690
          C 600 750, 660 705, 685 600
          C 705 510, 695 400, 705 320
          C 715 235, 760 140, 860 105
          C 955 70, 1080 100, 1115 185
          C 1145 255, 1115 325, 1045 345
          C 995 360, 955 335, 945 285"
      />
      <circle ref={dotRef} className="login-page__signature-dot" cx={895} cy={785} r={58} />
    </svg>
  );
}

interface LoginPageProps {
  onSuccess: () => void;
  /** Absent quand cette page est le point d'entrée obligatoire du site (pas
   * encore connecté — rien à "annuler" pour y retourner). Présent quand elle
   * est atteinte volontairement depuis `UserMenu` en étant déjà identifié
   * (démo ou connexion réelle) — voir `App.tsx`. */
  onCancel?: () => void;
}

export function LoginPage({ onSuccess, onCancel }: LoginPageProps) {
  const { users, login, setCurrentUserId } = useCurrentUser();
  const { showToast } = useToast();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Mode démo (voir CLAUDE.md — mécanisme d'identification temporaire) :
  // même liste/filtre que le sélecteur de UserMenu, dupliqué ici plutôt que
  // factorisé — rendu très différent (page pleine vs menu déroulant),
  // cohérent avec le reste du projet qui duplique ce genre de petit bloc.
  const selectableUsers = users.filter((user) => user.account_status === "active");

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(username, password);
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "La connexion a échoué.");
    } finally {
      setSubmitting(false);
    }
  }

  function handleDebugSelect(userId: string) {
    setCurrentUserId(userId);
    onSuccess();
  }

  return (
    <div className="login-page">
      <div className="login-page__panel-left" />
      <div className="login-page__panel-seam" />
      <div className="login-page__panel-right" />

      <div className="login-page__brand">
        <AwtodoSignature />
        <p className="login-page__tagline">
          Bienvenue sur Awtodo.
          <br />
          Ici, je gère mes projets !
        </p>
      </div>

      <div className="login-page__stage">
        <form className="login-page__card" onSubmit={handleSubmit}>
          <h1 className="login-page__card-title">Bon retour</h1>
          <p className="login-page__card-subtitle">Connectez-vous pour accéder à vos projets.</p>

          {error && <p className="login-page__error">{error}</p>}

          <label className="login-page__field">
            <span>Identifiant</span>
            <input
              type="text"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoFocus
              disabled={submitting}
            />
          </label>

          <label className="login-page__field">
            <span>Mot de passe</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              disabled={submitting}
            />
          </label>

          <button type="submit" className="login-page__submit" disabled={submitting || !username || !password}>
            {submitting ? "Connexion…" : "Se connecter"}
          </button>

          <div className="login-page__divider">ou</div>

          <button
            type="button"
            className="login-page__sso"
            onClick={() => showToast("Pas encore disponible.")}
          >
            <span className="login-page__sso-logo">
              <span />
              <span />
              <span />
              <span />
            </span>
            Continuer avec Microsoft
          </button>

          {onCancel && (
            <button type="button" className="login-page__cancel" onClick={onCancel} disabled={submitting}>
              Annuler
            </button>
          )}

          <p className="login-page__hint">
            Pas encore de compte ? Utilisez le lien reçu par email pour l'activer.
          </p>
        </form>

        {selectableUsers.length > 0 && (
          <div className="login-page__demo">
            <p className="login-page__demo-title">Mode démo — continuer en tant que</p>
            <ul className="login-page__demo-list">
              {selectableUsers.map((user) => (
                <li key={user.id}>
                  <button
                    type="button"
                    className="login-page__demo-option"
                    onClick={() => handleDebugSelect(user.id)}
                  >
                    <span className="login-page__demo-avatar">{initials(displayName(user))}</span>
                    {displayName(user)}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
