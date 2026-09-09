import { PublicClientApplication, type Configuration } from "@azure/msal-browser";

// SSO Microsoft (Azure AD / Entra ID, OIDC) — stub de config uniquement.
// Pas de tenant/client ID réels disponibles à ce stade : ces valeurs sont à
// renseigner via les variables d'environnement VITE_AZURE_* (voir .env.example).
// Aucune de ces valeurs n'est un secret : le client ID et l'authority sont
// publics par design OIDC pour une application SPA (PKCE, pas de client secret).
export const msalConfig: Configuration = {
  auth: {
    clientId: import.meta.env.VITE_AZURE_CLIENT_ID ?? "",
    authority: `https://login.microsoftonline.com/${import.meta.env.VITE_AZURE_TENANT_ID ?? ""}`,
    redirectUri: import.meta.env.VITE_AZURE_REDIRECT_URI ?? "http://localhost:5173",
  },
  cache: {
    cacheLocation: "sessionStorage",
  },
};

export const msalInstance = new PublicClientApplication(msalConfig);
