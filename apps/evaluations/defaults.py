"""Questions génériques livrées à chaque nouveau groupe / projet sans groupe.
`condition` = (index dans cette liste de la question cible, valeurs qui
affichent la question)."""

_PRESTA = ["Par un prestataire", "Mixte"]
_INTERNE = ["En interne", "Mixte"]

DEFAULT_CATALOG = [
    # --- Satisfaction client ---
    {"section": "client", "label": "Globalement, êtes-vous satisfait de la façon dont le projet a été mené ?",
     "answer_type": "note_5", "required": True},
    {"section": "client", "label": "Le résultat livré répond-il à votre besoin ?",
     "answer_type": "note_5", "required": True},
    {"section": "client", "label": "Les délais annoncés ont-ils été respectés ?",
     "answer_type": "oui_non", "required": True},
    {"section": "client", "label": "Comment jugez-vous la communication pendant le projet ?",
     "answer_type": "note_5", "required": True},
    {"section": "client", "label": "Recommanderiez-vous l'équipe projet à un collègue ?",
     "answer_type": "nps_10", "required": True},
    {"section": "client", "label": "Remarques ou suggestions", "answer_type": "texte_long"},
    # --- Évaluation chef de projet ---
    {"section": "interne", "label": "Le projet a été réalisé", "answer_type": "choix_unique",
     "options": ["En interne", "Par un prestataire", "Mixte"], "required": True},
    {"section": "interne", "label": "Nom du prestataire", "answer_type": "texte_court",
     "condition": (6, _PRESTA)},
    {"section": "interne",
     "label": "Comment la prestation a-t-elle été gérée (suivi, qualité, respect du contrat) ?",
     "answer_type": "texte_long", "condition": (6, _PRESTA)},
    {"section": "interne", "label": "Note de la prestation", "answer_type": "note_5", "condition": (6, _PRESTA)},
    {"section": "interne", "label": "Difficultés rencontrées en interne", "answer_type": "texte_long",
     "condition": (6, _INTERNE)},
    {"section": "interne", "label": "Le budget prévu a-t-il été respecté ?", "answer_type": "oui_non"},
    {"section": "interne", "label": "Le planning prévu a-t-il été respecté ?", "answer_type": "oui_non"},
    {"section": "interne", "label": "Points forts du projet", "answer_type": "texte_long"},
    {"section": "interne", "label": "Axes d'amélioration, retours d'expérience", "answer_type": "texte_long"},
]
