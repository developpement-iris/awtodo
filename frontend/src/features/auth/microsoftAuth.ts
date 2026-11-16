import { PublicClientApplication, type AuthenticationResult } from "@azure/msal-browser";
import { getSsoConfig } from "../../api/client";

/** Connexion Microsoft (session du 2026-11-16). Flux par redirection, pas par
 * fenêtre surgissante : l'en-tête `Cross-Origin-Opener-Policy: same-origin`
 * du site couperait le lien avec la fenêtre de connexion. MSAL ne sert qu'à
 * obtenir le jeton d'identité ; la session Awtodo reste celle du backend. */

let msalPromise: Promise<PublicClientApplication | null> | null = null;
let redirectPromise: Promise<AuthenticationResult | null> | null = null;

const SCOPES = ["openid", "profile", "email"];

function getMsal(): Promise<PublicClientApplication | null> {
  if (!msalPromise) {
    msalPromise = getSsoConfig()
      .then(async (config) => {
        if (!config.enabled) return null;
        const msal = new PublicClientApplication({
          auth: {
            clientId: config.client_id,
            authority: `https://login.microsoftonline.com/${config.tenant_id}`,
            redirectUri: `${window.location.origin}/`,
          },
          cache: { cacheLocation: "sessionStorage" },
        });
        await msal.initialize();
        return msal;
      })
      .catch(() => {
        msalPromise = null;
        return null;
      });
  }
  return msalPromise;
}

/** Jeton d'identité rapporté par le retour de Microsoft, s'il y en a un.
 * Mémorisé : le double montage de React en développement ne doit pas
 * traiter deux fois la même réponse. */
export function consumeMicrosoftRedirect(): Promise<AuthenticationResult | null> {
  if (!redirectPromise) {
    redirectPromise = getMsal().then((msal) => (msal ? msal.handleRedirectPromise() : null));
  }
  return redirectPromise;
}

/** Part vers la page de connexion Microsoft. Renvoie `false` si la connexion
 * Microsoft n'est pas configurée sur ce serveur. */
export async function startMicrosoftLogin(): Promise<boolean> {
  const msal = await getMsal();
  if (!msal) return false;
  redirectPromise = null;
  await msal.loginRedirect({ scopes: SCOPES, prompt: "select_account" });
  return true;
}
