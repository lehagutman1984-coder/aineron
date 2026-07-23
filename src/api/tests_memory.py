"""
API-тесты для Persistent Memory views (B12 — регрессия дублей content_key).

Что тестируем:
- POST /v1/memory/ дублирующего факта в одном скоупе -> 400, не 500 IntegrityError
- POST /v1/memory/ факта в другом проекте с тем же текстом -> 201, отдельная запись
- PATCH /v1/memory/<id>/ на текст, совпадающий с другим фактом того же скоупа -> 400
- GET /v1/memory/?scope=project:<id> фильтрует по проекту

Запуск: python manage.py test api.tests_memory
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from aitext.models import Project, UserMemory

User = get_user_model()


class MemoryViewScopeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='memapi', email='memapi@test.com', password='x'
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.project_a = Project.objects.create(user=self.user, name='A')
        self.project_b = Project.objects.create(user=self.user, name='B')

    def test_duplicate_in_same_scope_returns_400_not_500(self):
        resp1 = self.client.post('/api/v1/memory/', {'content': 'Использует Vue'}, format='json')
        self.assertEqual(resp1.status_code, 201)

        resp2 = self.client.post('/api/v1/memory/', {'content': 'Использует Vue'}, format='json')
        self.assertEqual(resp2.status_code, 400)
        self.assertEqual(UserMemory.objects.filter(user=self.user).count(), 1)

    def test_same_text_different_projects_both_created(self):
        r1 = self.client.post(
            '/api/v1/memory/', {'content': 'Стек: FastAPI', 'project': self.project_a.id}, format='json'
        )
        r2 = self.client.post(
            '/api/v1/memory/', {'content': 'Стек: FastAPI', 'project': self.project_b.id}, format='json'
        )
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)
        self.assertEqual(
            UserMemory.objects.filter(user=self.user, content='Стек: FastAPI').count(), 2
        )

    def test_patch_content_colliding_with_other_fact_returns_400(self):
        self.client.post('/api/v1/memory/', {'content': 'Факт раз'}, format='json')
        r2 = self.client.post('/api/v1/memory/', {'content': 'Факт два'}, format='json')
        fact2_id = r2.data['id']

        resp = self.client.patch(f'/api/v1/memory/{fact2_id}/', {'content': 'Факт раз'}, format='json')
        self.assertEqual(resp.status_code, 400)
        # факт не потерялся и не сменил текст молча
        fact2 = UserMemory.objects.get(pk=fact2_id)
        self.assertEqual(fact2.content, 'Факт два')

    def test_scope_filter_returns_only_that_projects_facts(self):
        self.client.post(
            '/api/v1/memory/', {'content': 'A-факт', 'project': self.project_a.id}, format='json'
        )
        self.client.post(
            '/api/v1/memory/', {'content': 'B-факт', 'project': self.project_b.id}, format='json'
        )
        self.client.post('/api/v1/memory/', {'content': 'Глобальный факт'}, format='json')

        resp = self.client.get(f'/api/v1/memory/?scope=project:{self.project_a.id}')
        contents = {f['content'] for f in resp.data}
        self.assertEqual(contents, {'A-факт'})

    def test_project_not_owned_by_user_rejected(self):
        other = User.objects.create_user(username='other', email='other@test.com', password='x')
        foreign_project = Project.objects.create(user=other, name='Foreign')

        resp = self.client.post(
            '/api/v1/memory/', {'content': 'факт', 'project': foreign_project.id}, format='json'
        )
        self.assertEqual(resp.status_code, 400)
