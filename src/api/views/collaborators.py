"""
Sprint 5.1 — Collaborative Spaces.

Endpoints (owner-only for mutations):
  GET    /api/v1/projects/<pk>/collaborators/           — list
  POST   /api/v1/projects/<pk>/collaborators/           — invite by email
  PATCH  /api/v1/projects/<pk>/collaborators/<cid>/     — change role
  DELETE /api/v1/projects/<pk>/collaborators/<cid>/     — remove
"""
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers

from aitext.models import ProjectCollaborator
from api.views._project_access import get_project_for_user, get_project_owner_only


class CollaboratorSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    invited_by_email = serializers.EmailField(source='invited_by.email', read_only=True, default=None)

    class Meta:
        model = ProjectCollaborator
        fields = ['id', 'email', 'username', 'role', 'invited_by_email', 'created_at']
        read_only_fields = ['id', 'email', 'username', 'invited_by_email', 'created_at']


class CollaboratorListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        project = get_project_for_user(pk, request.user, write=False)
        qs = project.collaborators.select_related('user', 'invited_by')
        return Response(CollaboratorSerializer(qs, many=True).data)

    def post(self, request, pk):
        project = get_project_owner_only(pk, request.user)

        email = (request.data.get('email') or '').strip().lower()
        role = request.data.get('role', 'viewer')

        if not email:
            return Response({'error': 'Укажите email'}, status=400)
        if role not in ('viewer', 'editor'):
            return Response({'error': 'role: viewer или editor'}, status=400)

        from users.models import CustomUser
        try:
            target = CustomUser.objects.get(email__iexact=email)
        except CustomUser.DoesNotExist:
            return Response({'error': f'Пользователь {email} не найден'}, status=404)

        if target == request.user:
            return Response({'error': 'Нельзя добавить себя'}, status=400)
        if target == project.user:
            return Response({'error': 'Пользователь уже является владельцем'}, status=400)

        collab, created = ProjectCollaborator.objects.get_or_create(
            project=project,
            user=target,
            defaults={'role': role, 'invited_by': request.user},
        )
        if not created:
            collab.role = role
            collab.save(update_fields=['role'])

        collab_qs = ProjectCollaborator.objects.select_related('user', 'invited_by').get(pk=collab.pk)
        return Response(CollaboratorSerializer(collab_qs).data, status=201 if created else 200)


class CollaboratorDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, request, pk, cid):
        project = get_project_owner_only(pk, request.user)
        return get_object_or_404(
            ProjectCollaborator.objects.select_related('user', 'invited_by'),
            pk=cid, project=project,
        )

    def patch(self, request, pk, cid):
        collab = self._get(request, pk, cid)
        role = request.data.get('role')
        if role not in ('viewer', 'editor'):
            return Response({'error': 'role: viewer или editor'}, status=400)
        collab.role = role
        collab.save(update_fields=['role'])
        return Response(CollaboratorSerializer(collab).data)

    def delete(self, request, pk, cid):
        collab = self._get(request, pk, cid)
        collab.delete()
        return Response(status=204)
