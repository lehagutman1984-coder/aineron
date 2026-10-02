"""
2026-10-02 (аудит безопасности, LOW): KnowledgeGraphView.get() звал
get_project_for_user(request, pk) - сигнатура функции (pk, user) - аргументы
были перепутаны местами. Эндпоинт падал 500 на КАЖДОМ вызове (fail-closed,
не дыра, но мёртвая фича - Knowledge Graph никогда не отдавал данные).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from aitext.models import Project

User = get_user_model()


class KnowledgeGraphViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='kg', email='kg@t.ru', password='x')
        self.project = Project.objects.create(user=self.user, name='P')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_owner_gets_200_not_500(self):
        resp = self.client.get(f'/api/v1/projects/{self.project.id}/graph/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('nodes', resp.json())
        self.assertIn('edges', resp.json())

    def test_other_user_gets_404_not_500(self):
        other = User.objects.create_user(username='other', email='other@t.ru', password='x')
        other_client = APIClient()
        other_client.force_authenticate(other)
        resp = other_client.get(f'/api/v1/projects/{self.project.id}/graph/')
        self.assertEqual(resp.status_code, 404)
