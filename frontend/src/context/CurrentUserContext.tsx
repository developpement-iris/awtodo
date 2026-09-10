import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { getMe, getUsers, login as loginRequest, setAccessToken, setDebugUserId } from "../api/client";
import type { User } from "../types/watodo";

const DEBUG_USER_STORAGE_KEY = "watodo-current-user";
const ACCESS_TOKEN_STORAGE_KEY = "watodo-access-token";

interface CurrentUserContextValue {
  users: User[];
  currentUser: User | null;
  /** Vrai si `currentUser` vient d'une connexion réelle (mot de passe), pas
   * du sélecteur de test — voir docs/organisation-et-comptes.md > "Comptes
   * et invitations" > authentification. */
  isAuthenticated: boolean;
  /** Vrai le temps de la restauration initiale (liste des utilisateurs +
   * tentative de reprise d'un token stocké) — évite à `App.tsx` de flasher
   * l'écran de connexion avant de savoir si une identité existe déjà. */
  isRestoring: boolean;
  setCurrentUserId: (id: string) => void;
  clearCurrentUser: () => void;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const CurrentUserContext = createContext<CurrentUserContextValue | null>(null);

export function CurrentUserProvider({ children }: { children: ReactNode }) {
  const [users, setUsers] = useState<User[]>([]);
  const [currentUserId, setCurrentUserIdState] = useState<string | null>(() =>
    window.localStorage.getItem(DEBUG_USER_STORAGE_KEY),
  );
  const [authUser, setAuthUser] = useState<User | null>(null);
  const [usersLoaded, setUsersLoaded] = useState(false);
  const [authRestored, setAuthRestored] = useState(false);

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
    // Un seul mécanisme d'identité actif à la fois — la connexion réelle
    // prime sur une éventuelle sélection de test en cours.
    window.localStorage.removeItem(DEBUG_USER_STORAGE_KEY);
    setCurrentUserIdState(null);
  }

  function setCurrentUserId(id: string) {
    logout();
    window.localStorage.setItem(DEBUG_USER_STORAGE_KEY, id);
    setCurrentUserIdState(id);
  }

  function clearCurrentUser() {
    window.localStorage.removeItem(DEBUG_USER_STORAGE_KEY);
    setCurrentUserIdState(null);
  }

  const debugUser = users.find((user) => user.id === currentUserId) ?? null;
  const currentUser = authUser ?? debugUser;

  useEffect(() => {
    setDebugUserId(authUser ? null : (currentUser?.id ?? null));
  }, [authUser, currentUser?.id]);

  return (
    <CurrentUserContext.Provider
      value={{
        users,
        currentUser,
        isAuthenticated: authUser !== null,
        isRestoring: !usersLoaded || !authRestored,
        setCurrentUserId,
        clearCurrentUser,
        login,
        logout,
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
