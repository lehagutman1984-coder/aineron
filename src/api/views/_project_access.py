"""
Central access helper for project views.

Rules:
  owner  → all operations
  editor → read + write (upload, sync, commit, delete files)
  viewer → read only
  none   → 404
"""
from rest_framework.exceptions import PermissionDenied
from django.http import Http404

from aitext.models import Project, ProjectCollaborator


def get_project_for_user(pk, user, *, write: bool = False) -> Project:
    """
    Return Project pk if user is allowed.
    Raises Http404 when project doesn't exist or user has no access.
    Raises PermissionDenied when user is a viewer attempting a write.
    """
    try:
        project = Project.objects.get(pk=pk)
    except Project.DoesNotExist:
        raise Http404

    if project.user_id == user.pk:
        return project

    try:
        collab = ProjectCollaborator.objects.get(project_id=pk, user=user)
    except ProjectCollaborator.DoesNotExist:
        raise Http404

    if write and collab.role == 'viewer':
        raise PermissionDenied('Наблюдатели не могут изменять проект.')

    return project


def get_project_owner_only(pk, user) -> Project:
    """For owner-only operations (delete, publish, manage collaborators)."""
    try:
        project = Project.objects.get(pk=pk)
    except Project.DoesNotExist:
        raise Http404

    if project.user_id != user.pk:
        raise PermissionDenied('Только владелец может выполнить это действие.')

    return project


def user_role_for_project(project: Project, user) -> str:
    """Return 'owner' | 'editor' | 'viewer'."""
    if project.user_id == user.pk:
        return 'owner'
    try:
        return ProjectCollaborator.objects.get(project=project, user=user).role
    except ProjectCollaborator.DoesNotExist:
        return 'viewer'
