import django.dispatch

# kwargs: task (Task), actor (User) — émis quand une tâche est assignée à
# quelqu'un d'autre que l'acteur (jamais sur une auto-attribution via
# `claim_task`, voir apps/tasks/services.py).
task_assigned = django.dispatch.Signal()

# kwargs: task (Task), comment (TaskComment), actor (User)
task_commented = django.dispatch.Signal()

# kwargs: task (Task), actor (User) — émis quand une tâche passe en statut
# terminal "archivee" via complete_task. Consommé par apps.documentation
# (file "À documenter" de l'onglet Documentation du hub projet). apps.tasks
# n'importe jamais apps.documentation — lien par signal.
task_completed = django.dispatch.Signal()
