from unittest.mock import patch, MagicMock
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from studio.models import StudioProject, StudioPipelineState, StudioTemplate
from studio.security import is_safe_url

User = get_user_model()


class StudioAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='t@t.ru', password='x')
        self.client.force_authenticate(self.user)

    def test_create_project(self):
        r = self.client.post(
            '/api/v1/studio/projects/',
            {'name': 'Test', 'description': 'desc', 'mode': 'auto'},
            format='json',
        )
        self.assertEqual(r.status_code, 201)
        self.assertTrue(StudioProject.objects.filter(user=self.user).exists())

    def test_create_project_creates_pipeline(self):
        r = self.client.post(
            '/api/v1/studio/projects/',
            {'name': 'Test2', 'mode': 'auto'},
            format='json',
        )
        self.assertEqual(r.status_code, 201)
        project_id = r.data['id']
        self.assertTrue(StudioPipelineState.objects.filter(project_id=project_id).exists())

    def test_list_isolated_per_user(self):
        StudioProject.objects.create(user=self.user, name='A')
        other = User.objects.create_user(email='o@o.ru', password='x')
        StudioProject.objects.create(user=other, name='B')
        r = self.client.get('/api/v1/studio/projects/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)

    def test_pipeline_state(self):
        p = StudioProject.objects.create(user=self.user, name='B')
        StudioPipelineState.objects.create(project=p)
        r = self.client.get(f'/api/v1/studio/projects/{p.id}/pipeline/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('status', r.data)

    def test_file_tree_empty(self):
        p = StudioProject.objects.create(user=self.user, name='C')
        StudioPipelineState.objects.create(project=p)
        r = self.client.get(f'/api/v1/studio/projects/{p.id}/files/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, [])

    def test_clone_rejects_private_url(self):
        r = self.client.post(
            '/api/v1/studio/clone/',
            {'url': 'http://localhost/secret'},
            format='json',
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn('error', r.data)

    @patch('studio.tasks.crawl_and_analyze.delay')
    def test_clone_valid_url(self, mock_delay):
        r = self.client.post(
            '/api/v1/studio/clone/',
            {'url': 'https://example.com', 'name': 'Clone Test'},
            format='json',
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['entry_mode'], 'clone_url')
        mock_delay.assert_called_once()

    def test_templates_list(self):
        StudioTemplate.objects.create(
            slug='test-tpl', name='Test', description='d', stack='nextjs', seed_prompt='p',
        )
        r = self.client.get('/api/v1/studio/templates/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)


class SSRFGuardTests(APITestCase):
    def test_localhost_blocked(self):
        self.assertFalse(is_safe_url('http://localhost'))

    def test_private_ip_blocked(self):
        self.assertFalse(is_safe_url('http://192.168.1.1'))

    def test_loopback_blocked(self):
        self.assertFalse(is_safe_url('http://127.0.0.1'))

    def test_public_url_allowed(self):
        self.assertTrue(is_safe_url('https://example.com'))

    def test_invalid_scheme_blocked(self):
        self.assertFalse(is_safe_url('ftp://example.com'))


class BillingChargeOrderTest(APITestCase):
    """Commit 2 — charge must be last action; no charge on agent failure (no double-charge on retry)."""

    def _make_project(self, uid='test-uuid'):
        project = MagicMock()
        project.id = uid
        project.interview_data = {}
        project.sandbox_container_id = None
        pipeline = MagicMock()
        pipeline.iteration_count = 0
        pipeline.fix_plan = None
        project.pipeline = pipeline
        return project

    @patch('studio.tasks.agent_plan')
    @patch('studio.tasks.charge')
    @patch('studio.tasks.can_afford', return_value=True)
    @patch('studio.tasks.publish_event')
    @patch('studio.tasks.StudioProject')
    def test_agent_analyze_charge_called_once_on_success(self, MockQS, mock_pub, mock_afford, mock_charge, mock_plan):
        from studio.tasks import agent_analyze
        project = self._make_project()
        MockQS.objects.get.return_value = project

        with patch('studio.tasks.AnalystAgent') as MockAgent:
            MockAgent.return_value.run.return_value = None
            agent_analyze(str(project.id))

        mock_charge.assert_called_once()
        mock_plan.delay.assert_called_once()

    @patch('studio.tasks.charge')
    @patch('studio.tasks.can_afford', return_value=True)
    @patch('studio.tasks.publish_event')
    @patch('studio.tasks.StudioProject')
    def test_agent_analyze_no_charge_when_agent_fails(self, MockQS, mock_pub, mock_afford, mock_charge):
        """If AnalystAgent.run raises, charge must NOT be called — prevents double-charge on retry."""
        from studio.tasks import agent_analyze
        project = self._make_project()
        MockQS.objects.get.return_value = project

        with patch('studio.tasks.AnalystAgent') as MockAgent:
            MockAgent.return_value.run.side_effect = RuntimeError('LLM timeout')
            with self.assertRaises(Exception):
                agent_analyze(str(project.id))

        mock_charge.assert_not_called()


class SandboxFailureTest(APITestCase):
    """Commit 4 — sandbox setup failure sets project.status='failed', not leaves it as 'coding'."""

    def _make_project(self):
        project = MagicMock()
        project.id = 'test-uuid'
        user = MagicMock()
        user.pages_count = 9999
        project.user = user
        project.status = 'coding'
        state = MagicMock()
        state.status = 'running'
        project.pipeline = state
        return project

    @patch('studio.tasks.can_afford', return_value=True)
    @patch('studio.tasks.publish_event')
    @patch('studio.tasks.StudioProject')
    @patch('studio.tasks.sandbox')
    def test_run_pipeline_sandbox_failure_sets_project_failed(
        self, mock_sandbox, MockQS, mock_pub, mock_afford
    ):
        from studio.tasks import run_pipeline
        project = self._make_project()
        MockQS.objects.get.return_value = project
        mock_sandbox.spawn_sandbox.side_effect = RuntimeError('Docker not available')

        run_pipeline(str(project.id))

        self.assertEqual(project.status, 'failed')

    @patch('studio.tasks.can_afford', return_value=True)
    @patch('studio.tasks.publish_event')
    @patch('studio.tasks.StudioProject')
    @patch('studio.tasks.sandbox')
    def test_run_pipeline_sandbox_failure_sets_state_failed(
        self, mock_sandbox, MockQS, mock_pub, mock_afford
    ):
        from studio.tasks import run_pipeline
        project = self._make_project()
        MockQS.objects.get.return_value = project
        mock_sandbox.spawn_sandbox.side_effect = RuntimeError('Docker not available')

        run_pipeline(str(project.id))

        self.assertEqual(project.pipeline.status, 'failed')
