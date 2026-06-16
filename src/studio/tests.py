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


class InsufficientStarsTest(APITestCase):
    """Commit 3 — InsufficientStars pauses pipeline; no charge on empty wallet."""

    def _make_project(self):
        project = MagicMock()
        project.id = 'test-uuid'
        project.interview_data = {}
        project.sandbox_container_id = None
        project.commits_md_content = '## Step 0\ndo something'
        state = MagicMock()
        state.iteration_count = 0
        state.fix_plan = None
        state.pause_reason = ''
        project.pipeline = state
        return project

    @patch('studio.tasks.charge')
    @patch('studio.tasks.can_afford', return_value=False)
    @patch('studio.tasks.publish_event')
    @patch('studio.tasks.StudioProject')
    def test_coder_iteration_no_funds_sets_paused(self, MockQS, mock_pub, mock_afford, mock_charge):
        from studio.tasks import coder_iteration
        project = self._make_project()
        MockQS.objects.get.return_value = project

        with patch('studio.tasks.CoderAgent') as MockCoder:
            MockCoder.return_value.run.return_value = {}
            coder_iteration(str(project.id), 0)

        mock_charge.assert_not_called()
        self.assertEqual(project.status, 'paused')
        self.assertEqual(project.pipeline.status, 'paused_on_loop')


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


class SplitStepsTest(APITestCase):
    """Commit 6 — _split_steps counts sections; planner prefers section count over marker."""

    def test_split_steps_counts_headers(self):
        from studio.tasks import _split_steps
        md = '## Step 1\ndo a\n## Step 2\ndo b\n## Step 3\ndo c'
        self.assertEqual(len(_split_steps(md)), 3)

    def test_split_steps_empty_returns_empty(self):
        from studio.tasks import _split_steps
        self.assertEqual(_split_steps(''), [])

    @patch('studio.agents.planner.PlannerAgent.run_prompt')
    def test_planner_uses_section_count_not_marker(self, mock_prompt):
        """Planner must return steps=3 (sections) even when marker says 7."""
        from studio.agents.planner import PlannerAgent
        md_with_wrong_marker = (
            '## Step 1\ndo a\n## Step 2\ndo b\n## Step 3\ndo c\n'
            '<STEPS_COUNT>7</STEPS_COUNT>'
        )
        mock_prompt.return_value = md_with_wrong_marker
        project = MagicMock()
        project.project_md_content = 'PROJECT.md content'
        agent = PlannerAgent(project)
        _, steps = agent.run()
        self.assertEqual(steps, 3)


class PauseResumeTest(APITestCase):
    """Commit 5 — pause sets flag and stops further task dispatch."""

    def setUp(self):
        self.user = User.objects.create_user(email='pause@t.ru', password='x')
        self.client.force_authenticate(self.user)

    def test_pause_sets_pause_requested_and_project_paused(self):
        project = StudioProject.objects.create(user=self.user, name='P', status='coding')
        state = StudioPipelineState.objects.create(project=project, status='running', current_task_id='abc-123')

        with patch('studio.views.pipeline.current_app') as mock_app:
            r = self.client.post(f'/api/v1/studio/projects/{project.id}/pipeline/pause/')

        self.assertEqual(r.status_code, 200)
        state.refresh_from_db()
        project.refresh_from_db()
        self.assertTrue(state.pause_requested)
        self.assertEqual(state.status, 'paused_manual')
        self.assertEqual(project.status, 'paused')

    @patch('studio.tasks.coder_iteration')
    @patch('studio.tasks.publish_event')
    @patch('studio.tasks.StudioProject')
    def test_start_step_respects_pause_requested(self, MockQS, mock_pub, mock_coder):
        """start_step must NOT dispatch coder_iteration when pause_requested=True."""
        from studio.tasks import start_step
        project = MagicMock()
        project.id = 'test-uuid'
        state = MagicMock()
        state.pause_requested = True
        state.status = 'paused_manual'
        project.pipeline = state
        MockQS.objects.get.return_value = project

        start_step(str(project.id), 0)

        mock_coder.delay.assert_not_called()
