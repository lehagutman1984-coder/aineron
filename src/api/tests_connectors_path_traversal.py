"""
2026-10-01 (аудит безопасности, API_SECURITY_AUDIT_2026-10-01.md, пункт 9):
регрессионный тест на path traversal в ConnectorFileContentView — '..' в
query-параметре path больше не уходит в GitHub API URL.

Запуск: python manage.py test api.tests_connectors_path_traversal
"""
from unittest import mock

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status

from aitext.crypto import encrypt_token
from aitext.models import Project, ProjectConnector

User = get_user_model()


class ConnectorPathTraversalTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner', email='owner@test.ru', password='x')
        self.project = Project.objects.create(user=self.owner, name='P1')
        self.connector = ProjectConnector.objects.create(
            project=self.project, connector_type='github',
            repo_url='https://github.com/owner/connected-repo',
            owner='owner', repo='connected-repo', branch='main',
            access_token_enc=encrypt_token('ghp_fake_token'),
        )
        self.client.force_authenticate(user=self.owner)
        self.url = f'/api/v1/projects/{self.project.pk}/connectors/{self.connector.pk}/file/'

    def test_parent_directory_traversal_rejected(self):
        resp = self.client.get(self.url, {'path': '../../other-private-repo/contents/.env'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_absolute_path_rejected(self):
        resp = self.client.get(self.url, {'path': '/etc/passwd'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_query_or_fragment_injection_rejected(self):
        resp = self.client.get(self.url, {'path': 'README.md?foo=bar'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_normal_relative_path_still_works(self):
        with mock.patch('aitext.github_client.get_file_content', return_value='hello world') as mock_get:
            resp = self.client.get(self.url, {'path': 'src/app.py'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['content'], 'hello world')
        mock_get.assert_called_once_with('owner', 'connected-repo', 'ghp_fake_token', 'src/app.py', 'main')
