# Instructions Claude Code — Implémentation de la charte graphique Watodo

Ce fichier complète le `CLAUDE.md` (section "Charte graphique"). À suivre pour la prochaine session de travail front-end.

## Avant de commencer

1. Lire la section **"Charte graphique"** du `CLAUDE.md` en entier, ainsi que la section **"Skills installés"** pour savoir lesquels sont disponibles et leur rôle respectif.
2. Les valeurs hex qui s'y trouvent sont **validées et figées** — ne pas les réinterpréter, ajuster, ou "améliorer" silencieusement, même si un skill de design suggère une autre direction. En cas de conflit entre une recommandation de skill et une valeur du `CLAUDE.md`, la valeur du `CLAUDE.md` gagne toujours. Signaler le conflit plutôt que de trancher seul.

## Retour de revue — v1 implémentée (à corriger en priorité)

Une première implémentation a été livrée (écrans Projets et Tâches). Revue effectuée sur captures d'écran réelles. Constats à corriger avant de poursuivre le développement de nouveaux écrans :

### Régression critique — badges de statut

**Une seule et même teinte (orange, vert...) est réutilisée pour désigner des axes différents** : orange sert à la fois pour la priorité "Haute", le type "Correction" ET le statut "En cours". Vert sert à la fois pour "Actif", le type "Ajout" ET le statut "Disponible". C'est exactement la "soupe de badges colorés" que le `CLAUDE.md` interdit explicitement (principe : "une teinte = un seul axe de sens"). Le skill de design n'avait probablement pas ce principe en contexte au moment de construire les composants — le lui donner explicitement avant de corriger (voir prompt à transmettre, plus bas).

### Typographie

Le serif éditorial actuellement utilisé pour les titres (type Playfair/Lora) ne convient pas — associé à un fond violet/cyan, c'est devenu une combinaison très reconnaissable de "design généré par IA", et raconte la mauvaise histoire pour un outil qui manipule des tickets/statuts techniques. Reprendre le choix typographique avec `impeccable`, en excluant explicitement les serifs éditoriaux pour les titres.

### Manques fonctionnels visibles à l'écran

- **Aucune référence externe visible** (ID de ticket d'origine) sur les tâches, alors que c'est une donnée clé du modèle (voir `CLAUDE.md`, section API/Intégration ticketing). À afficher sur chaque tâche.
- **Aucune identité utilisateur visible** (avatar, nom, menu de déconnexion) — problématique pour un outil SSO d'entreprise où on doit toujours savoir qui est connecté.
- **Carte projet sans hiérarchie secondaire** : pas de compteur de tâches, pas de barre de progression, pas d'indication des chefs de projet du projet.
- **Aucun état interactif visible** : pas de hover, pas de transition, pas d'indicateur de chargement.

## Étape 1 — Typographie et UX (délégué aux skills)

Utiliser `impeccable` (et `frontend-design` en complément) pour définir :
- La ou les polices de l'interface — **exclure les serifs éditoriaux** (voir "Retour de revue" ci-dessus)
- Les décisions UX détaillées : layout des écrans principaux, densité des tableaux, composants (cartes, boutons, badges, navigation)

Contrainte imposée à ces skills, à leur donner explicitement en contexte avant de les lancer : **la palette de couleurs cyan/violet-galaxie du CLAUDE.md est une contrainte de départ non négociable**, pas une suggestion parmi d'autres. Les skills doivent construire la typographie et les composants en cohérence avec cette palette, pas proposer une palette alternative.

**Une fois les choix faits :** reporter le résultat (polices retenues, principes UX actés) dans la section "Charte graphique" du `CLAUDE.md`, sous "Ce qui reste ouvert" → à faire passer en "actée". Ne pas laisser ces décisions vivre uniquement dans le code — elles doivent rester traçables dans le fichier de contexte, au même titre que les couleurs.

## Étape 2 — Sidebar fixe

Implémenter la sidebar comme un composant dont la couleur **ne dépend pas** du contexte/state de thème clair-sombre de l'application :
- `background: #1E1345` (galaxy-800) en toutes circonstances
- Texte : `#EDEBF7` (star)
- État actif/hover : `#7DC7C3` (cyan)

Concrètement : si le thème est géré via une classe ou un attribut `data-theme` sur un élément racine avec des variables CSS qui changent de valeur selon le mode, la sidebar doit soit utiliser des valeurs codées en dur (pas les variables thémées), soit ses propres variables non affectées par le toggle. Vérifier visuellement que basculer le thème clair/sombre ne change strictement rien à l'apparence de la sidebar.

Le logo/nom "Watodo" en haut de la sidebar doit être cliquable et renvoyer vers l'écran d'accueil (voir Étape 5).

## Étape 3 — Couleurs sémantiques (statut, priorité, type, incident)

**Constat : cette étape a été mal exécutée dans la v1 livrée (voir "Retour de revue" ci-dessus) — à refaire, pas seulement à compléter.**

Marche à suivre :
1. Proposer une palette sémantique cohérente avec le système cyan/galaxie déjà en place (dérivée des tokens existants autant que possible plutôt que d'introduire des teintes complètement déconnectées).
2. **Règle non négociable : une couleur ne porte jamais deux significations différentes.** Le type de tâche, la priorité, le statut et les incidents doivent chacun avoir leur propre famille de teinte (ou un mécanisme non coloré — glyphe, icône, poids de texte — si le nombre de couleurs distinctes devient difficile à tenir cohérent avec la palette de base).
3. Présenter cette proposition avant de l'implémenter dans les composants — même logique de validation que pour la palette de base.
4. Une fois validée, l'ajouter au `CLAUDE.md`.

Rappel des axes à couvrir (voir `CLAUDE.md`) :
- Type de tâche : `CORRECTION` / `AJOUT` / `ÉVOLUTION`
- Priorité : basse / moyenne / haute / critique
- Statut de tâche : `en_attente_validation` / `disponible` / `assignée` / `en_cours` / `archivée` / `rejetée`
- Incidents : famille de couleur dédiée, visuellement distincte des tâches (exigence produit actée — écrans séparés, priorité visuelle immédiate)

## Étape 4 — Écran Tâches : passage en Kanban avec panneau de détail

L'écran Tâches actuel (tableau statique) doit évoluer vers :
- **Vue Kanban** organisée par colonnes de statut (ou de priorité, à trancher — proposer une option par défaut avec un sélecteur pour basculer entre les deux si simple à faire), avec **glisser-déposer** pour changer le statut/la priorité d'une tâche. `dnd-kit` est disponible dans l'environnement.
- **Clic sur une carte de tâche → panneau de détail en drawer latéral** (pas une nouvelle page), qui garde la liste/le Kanban visible en arrière-plan. Le drawer affiche : description complète, référence externe (ticket), historique de statut, et une **zone de commentaires** (l'ajout de commentaires n'est pas encore dans le modèle de données back — si le backend n'a pas encore ce endpoint, construire l'UI et le désactiver/mocker proprement plutôt que bloquer tout l'écran ; signaler le manque plutôt que d'improviser un modèle de données côté front).

## Étape 5 — Écran d'accueil

Actuellement absent — à créer, accessible en cliquant sur "Watodo" dans la sidebar.

Contenu attendu (deux blocs, pas uniquement un sommaire de navigation) :
1. **Une bande "à traiter"** en haut : tâches prioritaires assignées à l'utilisateur connecté + incidents en cours qui le concernent. Doit donner envie de rester sur cet écran pour démarrer sa journée, pas juste rediriger ailleurs.
2. **Les sections principales sous forme de cards** (Projets, Tâches, Incidents) en dessous, comme prévu initialement.

## Étape 6 — Identité utilisateur et états interactifs

- Ajouter un élément d'identité utilisateur visible en permanence (avatar + nom, menu avec déconnexion) — zone à définir mais probablement en bas de la sidebar ou en haut à droite de la topbar, à côté du toggle de thème.
- S'assurer que tous les éléments interactifs (lignes de tableau, cartes, boutons, items de sidebar) ont un état hover visible et une transition courte — pas d'interface statique.
- Ajouter des indicateurs de chargement (skeleton ou spinner sobre, cohérent avec la palette) pour les listes qui chargent des données.

## Rappel — ce qui reste bloqué indépendamment de ce chantier

Le blocage sur BDD détaillée et déploiement AWS (voir `CLAUDE.md`, section "Stack technique") reste en vigueur et n'est pas concerné par ce chantier design. Ne pas en profiter pour introduire des dépendances ou fichiers de settings liés à l'infra à cette occasion.
