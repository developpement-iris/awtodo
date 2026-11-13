from apps.accounts.models import Team, TeamMembership, User
from apps.projects.models import Project, ProjectMembership


def make_user(username, **kwargs):
    return User.objects.create_user(username=username, **kwargs)


def make_team_project(name="Collab"):
    """Groupe + projet collaboratif + un chef de projet, un membre, un admin de groupe."""
    manager = make_user(f"{name.lower()}-cp")
    member = make_user(f"{name.lower()}-membre")
    team_admin = make_user(f"{name.lower()}-admin-groupe")
    team = Team.objects.create(name=f"Groupe {name}", created_by=team_admin)
    TeamMembership.objects.create(team=team, user=team_admin, role="administrateur")
    TeamMembership.objects.create(team=team, user=manager)
    TeamMembership.objects.create(team=team, user=member)
    project = Project.objects.create(name=name, team=team)
    ProjectMembership.objects.create(project=project, user=manager, role="chef_de_projet")
    ProjectMembership.objects.create(project=project, user=member, role="membre")
    return {"team": team, "project": project, "manager": manager, "member": member, "team_admin": team_admin}


def make_individual_project(name="Perso"):
    manager = make_user(f"{name.lower()}-cp")
    project = Project.objects.create(name=name, project_type="individuel")
    ProjectMembership.objects.create(project=project, user=manager, role="chef_de_projet")
    return {"project": project, "manager": manager}
