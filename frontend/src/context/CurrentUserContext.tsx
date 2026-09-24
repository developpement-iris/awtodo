import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { getMe, getUsers, login as loginRequest, setAccessToken } from "../api/client";
import type { Me, User } from "../types/watodo";
import { applyAccentColor } from "../theme/accentColor";

const ACCESS_TOKEN_STORAGE_KEY = "watodo-access-token";

interface CurrentUserContextValue {
  users: User[];
  currentUser: Me | null;
  /** Toujours vrai dès que `currentUser` est non nul — le sélecteur de test
   * "mode démo" a été retiré (session du 2026-09-18, remontée directe :
   * exposait la liste de tous les comptes de l'organisation sur l'écran de
   * connexion). Conservé comme champ distinct plutôt que déduit inline pour
   * ne pas casser les appelants existants. */
  isAuthenticated: boolean;
  /** Vrai le temps de la restauration initiale (liste des utilisateurs +
   * tentative de reprise d'un token stocké) — évite à `App.tsx` de flasher
   * l'écran de connexion avant de savoir si une identité existe déjà. */
  isRestoring: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  /** Recharge `currentUser` depuis `/accounts/me/` — utilisé après un
   * changement de préférence personnelle (ex. couleur d'accent, écran
   * Réglages) pour que le reste de l'app reflète le changement sans
   * recharger la page. */
  refreshCurrentUser: () => Promise<void>;
}

const CurrentUserContext = createContext<CurrentUserContextValue | null>(null);

export function CurrentUserProvider({ children }: { children: ReactNode }) {
  const [users, setUsers] = useState<User[]>([]);
  const [authUser, setAuthUser] = useState<Me | null>(null);
  const [usersLoaded, setUsersLoaded] = useState(false);
  const [authRestored, setAuthRestored] = useState(false);

  // Couleur d'accent par utilisateur (session du 2026-09-23) — appliquée
  // dès que l'identité courante change, retirée à la déconnexion.
  useEffect(() => {
    applyAccentColor(authUser?.accent_color ?? "");
  }, [authUser?.accent_color]);

  // Restauration d'une connexion réelle déjà en cours (token stocké) — un
  // token invalide/expiré est purgé silencieusement, l'utilisateur retombe
  // sur le sélecteur de test s'il en avait un.
  useEffect(() => {
    const storedToken = window.localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY);
    if (!storedToken) {
      setAuthRestored(true);
      return;
    }
    setAccessToken(storedToken);
    getMe()
      .then(setAuthUser)
      .catch(() => {
        window.localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY);
        setAccessToken(null);
      })
      .finally(() => setAuthRestored(true));
  }, []);

  // La liste des utilisateurs n'est chargée qu'une fois le token restauré (et
  // rechargée après une connexion) : en prod l'endpoint exige l'authentification
  // (`IsAuthenticated`), un fetch au tout premier rendu partirait sans en-tête
  // `Authorization` et échouerait en 401 — laissant `users` vide (sélecteur de
  // partage de calendrier, palette de commandes… tous vides).
  useEffect(() => {
    if (!authRestored) return;
    getUsers()
      .then(setUsers)
      .catch(() => setUsers([]))
      .finally(() => setUsersLoaded(true));
  }, [authRestored, authUser?.id]);

  function logout() {
    window.localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY);
    setAccessToken(null);
    setAuthUser(null);
  }

  async function login(username: string, password: string) {
    const response = await loginRequest(username, password);
    window.localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, response.access);
    setAccessToken(response.access);
    setAuthUser(response.user);
  }

  async function refreshCurrentUser() {
    if (!authUser) return;
    setAuthUser(await getMe());
  }

  return (
    <CurrentUserContext.Provider
      value={{
        users,
        currentUser: authUser,
        isAuthenticated: authUser !== null,
        isRestoring: !usersLoaded || !authRestored,
        login,
        logout,
        refreshCurrentUser,
      }}
    >
      {children}
    </CurrentUserContext.Provider>
  );
}

export function useCurrentUser(): CurrentUserContextValue {
  const context = useContext(CurrentUserContext);
  if (!context) {
    throw new Error("useCurrentUser doit être utilisé à l'intérieur de <CurrentUserProvider>.");
  }
  return context;
}
