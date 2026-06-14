from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers

from aitext.models import Project


class ProjectSerializer(serializers.ModelSerializer):
    chat_count = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = ['id', 'name', 'system_prompt', 'color', 'icon', 'chat_count', 'created_at']
        read_only_fields = ['id', 'created_at', 'chat_count']

    def get_chat_count(self, obj):
        return obj.chats.count()


class ProjectListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        projects = Project.objects.filter(user=request.user).prefetch_related('chats')
        return Response(ProjectSerializer(projects, many=True).data)

    def post(self, request):
        ser = ProjectSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        project = ser.save(user=request.user)
        return Response(ProjectSerializer(project).data, status=201)


class ProjectDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        project = get_object_or_404(Project, pk=pk, user=request.user)
        ser = ProjectSerializer(project, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ProjectSerializer(project).data)

    def delete(self, request, pk):
        project = get_object_or_404(Project, pk=pk, user=request.user)
        project.delete()
        return Response(status=204)
