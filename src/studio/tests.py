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


class SemiManualModeTest(APITestCase):
    """Commit 20 — semi/manual mode pauses after each step; ApproveStepView resumes."""

    def setUp(self):
        self.user = User.objects.create_user(email='semi@t.ru', password='x')
        self.client.force_authenticate(self.user)

    @patch('studio.tasks.next_step')
    @patch('studio.tasks.gitea_client')
    @patch('studio.tasks.StudioVersion')
    @patch('studio.tasks.publish_event')
    @patch('studio.tasks.StudioProject')
    def test_semi_mode_pauses_after_step(self, MockQS, mock_pub, MockVersion, mock_gitea, mock_next):
        from studio.tasks import commit_to_gitea
        project = MagicMock()
        project.id = 'proj-id'
        project.mode = 'semi'
        project.repo_url = ''
        project.user.gitea_username = ''
        project.files.all.return_value = []
        state = MagicMock()
        project.pipeline = state
        MockQS.objects.get.return_value = project

        commit_to_gitea('proj-id', 0)

        self.assertEqual(project.status, 'paused')
        self.assertEqual(state.status, 'paused_manual')
        mock_next.delay.assert_not_called()

    def test_approve_step_dispatches_next_step(self):
        project = StudioProject.objects.create(user=self.user, name='SM', status='paused', mode='semi')
        state = StudioPipelineState.objects.create(project=project, status='paused_manual', step_index=2)

        with patch('studio.tasks.next_step') as mock_next:
            r = self.client.post(f'/api/v1/studio/projects/{project.id}/approve/')

        self.assertEqual(r.status_code, 200)
        state.refresh_from_db()
        self.assertFalse(state.pause_requested)
        self.assertEqual(state.status, 'running')
        mock_next.delay.assert_called_once_with(str(project.id), 2)


class ExportZipTest(APITestCase):
    """Commit 36 — ExportView returns ZIP with all project files."""

    def setUp(self):
        self.user = User.objects.create_user(email='export@t.ru', password='x')
        self.client.force_authenticate(self.user)

    def test_export_returns_zip_with_all_files(self):
        import io
        import zipfile
        from studio.models import StudioFile
        project = StudioProject.objects.create(user=self.user, name='Export Me', status='completed', mode='auto')
        StudioFile.objects.create(project=project, path='index.ts', content='const x = 1')
        StudioFile.objects.create(project=project, path='app/page.tsx', content='export default () => null')

        r = self.client.get(f'/api/v1/studio/projects/{project.id}/export/')

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/zip')
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        names = zf.namelist()
        self.assertIn('index.ts', names)
        self.assertIn('app/page.tsx', names)
        self.assertEqual(zf.read('index.ts').decode(), 'const x = 1')

    def test_export_returns_404_for_other_user(self):
        other = User.objects.create_user(email='other@t.ru', password='x')
        project = StudioProject.objects.create(user=other, name='Private', status='completed', mode='auto')
        r = self.client.get(f'/api/v1/studio/projects/{project.id}/export/')
        self.assertEqual(r.status_code, 404)


class CollaboratorTest(APITestCase):
    """Commit 34 — StudioCollaborator: viewer can read, not write; accessible_projects includes collab projects."""

    def setUp(self):
        self.owner = User.objects.create_user(email='owner@t.ru', password='x')
        self.viewer = User.objects.create_user(email='viewer@t.ru', password='x')
        self.editor = User.objects.create_user(email='editor@t.ru', password='x')
        self.project = StudioProject.objects.create(user=self.owner, name='Collab', status='coding', mode='auto')
        StudioPipelineState.objects.create(project=self.project, status='idle')

    def test_collaborator_sees_project_in_list(self):
        from studio.models import StudioCollaborator
        StudioCollaborator.objects.create(project=self.project, user=self.viewer, role='viewer')
        self.client.force_authenticate(self.viewer)
        r = self.client.get('/api/v1/studio/projects/')
        ids = [p['id'] for p in r.data]
        self.assertIn(str(self.project.id), ids)

    def test_add_collaborator_via_view(self):
        self.client.force_authenticate(self.owner)
        r = self.client.post(
            f'/api/v1/studio/projects/{self.project.id}/collaborators/',
            {'action': 'add', 'email': 'viewer@t.ru', 'role': 'viewer'},
            format='json',
        )
        self.assertEqual(r.status_code, 201)
        from studio.models import StudioCollaborator
        self.assertTrue(StudioCollaborator.objects.filter(project=self.project, user=self.viewer).exists())

    def test_non_owner_cannot_add_collaborator(self):
        self.client.force_authenticate(self.viewer)
        r = self.client.post(
            f'/api/v1/studio/projects/{self.project.id}/collaborators/',
            {'action': 'add', 'email': 'editor@t.ru'},
            format='json',
        )
        self.assertEqual(r.status_code, 404)


class TemplateMarketplaceTest(APITestCase):
    """Commit 35 — publish project as template, create from template slug."""

    def setUp(self):
        self.user = User.objects.create_user(email='tmpl@t.ru', password='x', pages_count=10)
        self.client.force_authenticate(self.user)

    def test_publish_template_creates_public_template(self):
        project = StudioProject.objects.create(
            user=self.user, name='My App', description='A cool app',
            status='completed', mode='auto', target_stack='nextjs',
        )
        r = self.client.post(f'/api/v1/studio/projects/{project.id}/publish-template/')
        self.assertEqual(r.status_code, 201)
        self.assertTrue(StudioTemplate.objects.filter(author=self.user, is_public=True).exists())

    def test_template_list_returns_only_public(self):
        StudioTemplate.objects.create(
            slug='pub', name='Public', description='d', seed_prompt='p', is_public=True,
        )
        StudioTemplate.objects.create(
            slug='priv', name='Private', description='d', seed_prompt='p', is_public=False,
        )
        r = self.client.get('/api/v1/studio/templates/')
        names = [t['name'] for t in r.data]
        self.assertIn('Public', names)
        self.assertNotIn('Private', names)

    def test_create_from_template_increments_usage(self):
        tmpl = StudioTemplate.objects.create(
            slug='starter', name='Starter', description='d',
            seed_prompt='Build a todo app', is_public=True,
        )
        r = self.client.post(
            '/api/v1/studio/projects/',
            {'name': 'New', 'mode': 'auto', 'template_slug': 'starter'},
            format='json',
        )
        self.assertEqual(r.status_code, 201)
        tmpl.refresh_from_db()
        self.assertEqual(tmpl.usage_count, 1)


class VercelDeployTest(APITestCase):
    """Commit 32 — deploy_to_vercel stores deployment URL; DeployView dispatches task."""

    def setUp(self):
        self.user = User.objects.create_user(email='vercel@t.ru', password='x')
        self.client.force_authenticate(self.user)

    @patch('studio.tasks.publish_event')
    def test_deploy_to_vercel_stores_url(self, mock_pub):
        import requests as _rq
        from studio.tasks import deploy_to_vercel
        project = StudioProject.objects.create(user=self.user, name='V', status='completed', mode='auto')

        with self.settings(STUDIO_VERCEL_TOKEN='test-token'):
            with patch('studio.tasks._rq.post') as mock_post:
                mock_post.return_value.json.return_value = {'url': 'app-abc.vercel.app'}
                deploy_to_vercel(str(project.id))

        project.refresh_from_db()
        self.assertEqual(project.vercel_deployment_url, 'https://app-abc.vercel.app')

    def test_deploy_view_dispatches_task(self):
        project = StudioProject.objects.create(user=self.user, name='V2', status='completed', mode='auto')
        with patch('studio.tasks.deploy_to_vercel') as mock_task:
            r = self.client.post(f'/api/v1/studio/projects/{project.id}/deploy/')
        self.assertEqual(r.status_code, 202)
        mock_task.delay.assert_called_once_with(str(project.id))

    @patch('studio.tasks.publish_event')
    def test_deploy_skips_without_token(self, mock_pub):
        from studio.tasks import deploy_to_vercel
        project = StudioProject.objects.create(user=self.user, name='V3', status='completed', mode='auto')
        with self.settings(STUDIO_VERCEL_TOKEN=''):
            deploy_to_vercel(str(project.id))
        project.refresh_from_db()
        self.assertEqual(project.vercel_deployment_url, '')


class ComplexTagRoutingTest(APITestCase):
    """Commit 31 — _pick_model checks [COMPLEX] tag first; PlannerAgent warns on >15 steps."""

    def test_complex_tag_routes_to_model_smart(self):
        from studio.agents.coder import _pick_model
        from studio.agents.base import MODEL_SMART
        self.assertEqual(_pick_model('## [COMPLEX] Auth setup'), MODEL_SMART)

    def test_simple_step_routes_to_model_fast(self):
        from studio.agents.coder import _pick_model
        from studio.agents.base import MODEL_FAST
        self.assertEqual(_pick_model('## Add a button'), MODEL_FAST)

    def test_complex_tag_overrides_length_heuristic(self):
        from studio.agents.coder import _pick_model
        from studio.agents.base import MODEL_SMART
        # Short text with [COMPLEX] tag still routes smart
        self.assertEqual(_pick_model('[COMPLEX] x'), MODEL_SMART)

    def test_planner_warns_on_more_than_15_steps(self):
        from studio.agents.planner import PlannerAgent
        user = User.objects.create_user(email='plan@t.ru', password='x')
        project = StudioProject.objects.create(user=self.user if hasattr(self, 'user') else user,
                                               name='P', status='planning', mode='auto')
        agent = PlannerAgent(project)
        md = '\n'.join(f'## Шаг {i}' for i in range(20))
        agent.run_prompt = MagicMock(return_value=md + '\n<STEPS_COUNT>20</STEPS_COUNT>')
        with patch('studio.events.publish_event') as mock_pub:
            _, steps = agent.run()
        self.assertEqual(steps, 20)
        warning_calls = [c for c in mock_pub.call_args_list
                         if 'warning' in str(c) or 'Предупреждение' in str(c)]
        self.assertTrue(len(warning_calls) > 0)


class FixPlanTargetFilesTest(APITestCase):
    """Commit 30 — CoderAgent filters output to allowed_files in fix mode."""

    def setUp(self):
        self.user = User.objects.create_user(email='fix@t.ru', password='x')

    def test_allowed_files_filters_coder_output(self):
        from studio.agents.coder import CoderAgent
        project = StudioProject.objects.create(user=self.user, name='F', status='coding', mode='auto')
        agent = CoderAgent(project)
        agent.run_json = MagicMock(return_value={'files': {'a.tsx': 'a', 'b.tsx': 'b', 'c.tsx': 'c'}})
        result = agent.run(0, 'fix a', {'a.tsx': '', 'b.tsx': '', 'c.tsx': ''}, allowed_files=['a.tsx'])
        self.assertEqual(list(result.keys()), ['a.tsx'])

    def test_no_allowed_files_returns_all(self):
        from studio.agents.coder import CoderAgent
        project = StudioProject.objects.create(user=self.user, name='F2', status='coding', mode='auto')
        agent = CoderAgent(project)
        agent.run_json = MagicMock(return_value={'files': {'a.tsx': 'a', 'b.tsx': 'b'}})
        result = agent.run(0, 'step', {'a.tsx': '', 'b.tsx': ''})
        self.assertIn('a.tsx', result)
        self.assertIn('b.tsx', result)


class DiffReviewTest(APITestCase):
    """Commit 29 — agent_review passes only changed files to ReviewerAgent."""

    def setUp(self):
        self.user = User.objects.create_user(email='rev@t.ru', password='x')

    @patch('studio.tasks.publish_event')
    @patch('studio.agents.reviewer.ReviewerAgent.run_json')
    def test_reviewer_receives_only_changed_files(self, mock_rj, mock_pub):
        from studio.tasks import agent_review
        from studio.models import StudioFile
        mock_rj.return_value = {'passed': True, 'issues': [], 'summary': 'ok'}
        project = StudioProject.objects.create(
            user=self.user, name='Rev', status='coding', mode='auto',
            interview_data={'last_changed': {'0': ['a.tsx']}, 'planned_steps': 5},
        )
        StudioPipelineState.objects.create(project=project, status='running', step_index=0)
        StudioFile.objects.create(project=project, path='a.tsx', content='const a = 1')
        StudioFile.objects.create(project=project, path='b.tsx', content='const b = 2')

        result = agent_review(str(project.id), 0)

        call_args = mock_rj.call_args
        user_prompt = call_args[0][1]
        self.assertIn('const a = 1', user_prompt)
        self.assertNotIn('const b = 2', user_prompt)
        self.assertIn('b.tsx', user_prompt)  # listed in context


class WaitForReadyTest(APITestCase):
    """Commit 28 — wait_for_ready polls container HTTP until 200 or timeout."""

    def test_returns_true_on_200(self):
        from studio.sandbox import wait_for_ready
        with patch('studio.sandbox.exec_command', side_effect=[
            (0, '000'), (0, '000'), (0, '200'),
        ]) as mock_exec:
            with patch('time.sleep'):
                result = wait_for_ready('container_x', timeout=9)
        self.assertTrue(result)
        self.assertEqual(mock_exec.call_count, 3)

    def test_returns_false_on_timeout(self):
        from studio.sandbox import wait_for_ready
        with patch('studio.sandbox.exec_command', return_value=(0, '000')):
            with patch('time.sleep'):
                result = wait_for_ready('container_x', timeout=9)
        self.assertFalse(result)

    @patch('studio.tasks.sandbox')
    @patch('studio.tasks.publish_event')
    def test_coder_iteration_calls_wait_for_ready(self, mock_pub, mock_sandbox):
        from studio.tasks import coder_iteration
        user = User.objects.create_user(email='wfr@t.ru', password='x', pages_count=100)
        project = StudioProject.objects.create(
            user=user, name='W', status='coding', mode='auto',
            sandbox_container_id='container_wfr',
            stars_reserved=50,
        )
        state = StudioPipelineState.objects.create(project=project, status='running', step_index=0)
        mock_sandbox.write_files.return_value = None
        mock_sandbox.wait_for_ready.return_value = True
        with patch('studio.agents.coder.CoderAgent.run', return_value={'app.ts': 'code'}):
            with patch('studio.tasks.chord') as mock_chord:
                mock_chord.return_value.apply_async.return_value = None
                with patch('studio.tasks.charge_from_reserve', return_value=True):
                    coder_iteration(self, str(project.id), 0)
        mock_sandbox.wait_for_ready.assert_called_once_with('container_wfr', timeout=60)


class RealBuildCheckTest(APITestCase):
    """Commit 27 — agent_test uses run_build_check; TesterAgent exit_code overrides LLM passed."""

    def setUp(self):
        self.user = User.objects.create_user(email='build@t.ru', password='x')

    def test_tester_exit_code_overrides_llm_passed(self):
        from studio.agents.tester import TesterAgent
        project = StudioProject.objects.create(user=self.user, name='T', status='coding', mode='auto')
        agent = TesterAgent(project)
        agent.run_json = MagicMock(return_value={'passed': True, 'build_ok': True, 'errors': [], 'summary': 'ok'})
        report = agent.run('', exit_code=1)
        self.assertFalse(report['passed'])
        self.assertFalse(report['build_ok'])

    def test_tester_exit_code_zero_respects_llm(self):
        from studio.agents.tester import TesterAgent
        project = StudioProject.objects.create(user=self.user, name='T2', status='coding', mode='auto')
        agent = TesterAgent(project)
        agent.run_json = MagicMock(return_value={'passed': True, 'build_ok': True, 'errors': [], 'summary': 'ok'})
        report = agent.run('', exit_code=0)
        self.assertTrue(report['passed'])

    @patch('studio.tasks.sandbox')
    @patch('studio.tasks.publish_event')
    def test_agent_test_calls_run_build_check(self, mock_pub, mock_sandbox):
        from studio.tasks import agent_test
        project = StudioProject.objects.create(
            user=self.user, name='T3', status='coding', mode='auto',
            sandbox_container_id='container_abc',
        )
        StudioPipelineState.objects.create(project=project, status='running', step_index=0)
        mock_sandbox.run_build_check.return_value = (0, 'Build ok')
        with patch('studio.agents.tester.TesterAgent.run_json', return_value={'passed': True, 'build_ok': True, 'errors': [], 'summary': 'ok'}):
            result = agent_test(str(project.id), 0)
        mock_sandbox.run_build_check.assert_called_once_with('container_abc')
        self.assertTrue(result['report']['passed'])


class CoderContextTest(APITestCase):
    """Commit 26 — CoderAgent selects full content of mentioned files, lists all paths."""

    def setUp(self):
        self.user = User.objects.create_user(email='ctx@t.ru', password='x')

    def test_mentioned_file_content_in_prompt(self):
        from studio.agents.coder import CoderAgent
        project = StudioProject.objects.create(user=self.user, name='C', status='coding', mode='auto')
        agent = CoderAgent(project)
        existing = {
            'src/app.ts': 'export const app = 1',
            'src/utils.ts': 'export const util = 2',
            'README.md': '# readme',
        }
        step_text = 'Update src/app.ts to add error handling'
        captured = {}
        original_run_json = agent.run_json

        def mock_run_json(system, user, **kwargs):
            captured['user'] = user
            return {'files': {}}

        agent.run_json = mock_run_json
        agent.run(0, step_text, existing)
        self.assertIn('export const app = 1', captured['user'])
        self.assertIn('src/utils.ts', captured['user'])
        self.assertIn('README.md', captured['user'])
        # Non-mentioned files appear only in listing, not full content
        self.assertNotIn('export const util = 2', captured['user'])

    def test_backtick_file_included_in_context(self):
        from studio.agents.coder import CoderAgent
        project = StudioProject.objects.create(user=self.user, name='C2', status='coding', mode='auto')
        agent = CoderAgent(project)
        existing = {'config.json': '{}', 'index.ts': 'const x = 1'}
        step_text = 'Modify `config.json` to add new settings'
        captured = {}
        agent.run_json = lambda s, u, **kw: captured.update({'user': u}) or {'files': {}}
        agent.run(0, step_text, existing)
        self.assertIn('{}', captured['user'])


class SmartCoderTest(APITestCase):
    """Commit 22 — CoderAgent picks MODEL_SMART for complex steps, bills at smart rate."""

    def test_pick_model_simple_step(self):
        from studio.agents.coder import _pick_model
        from studio.agents.base import MODEL_FAST
        self.assertEqual(_pick_model('Add a button'), MODEL_FAST)

    def test_pick_model_complex_keyword(self):
        from studio.agents.coder import _pick_model
        from studio.agents.base import MODEL_SMART
        self.assertEqual(_pick_model('Implement authentication middleware'), MODEL_SMART)

    def test_pick_model_long_step(self):
        from studio.agents.coder import _pick_model
        from studio.agents.base import MODEL_SMART
        self.assertEqual(_pick_model('x' * 700), MODEL_SMART)

    def test_billing_tier_override_smart(self):
        from studio.billing import STAR_RATE, AGENT_BUDGET
        tier_smart = 'smart'
        _, budget = AGENT_BUDGET['coder']
        cost_smart = max(1, int((budget / 1000.0) * STAR_RATE[tier_smart]))
        cost_fast = max(1, int((budget / 1000.0) * STAR_RATE['fast']))
        self.assertGreater(cost_smart, cost_fast)

    def test_coder_tier_for_model(self):
        from studio.billing import coder_tier_for_model
        from studio.agents.base import MODEL_SMART, MODEL_FAST
        self.assertEqual(coder_tier_for_model(MODEL_SMART), 'smart')
        self.assertEqual(coder_tier_for_model(MODEL_FAST), 'fast')


class StarReservationTest(APITestCase):
    """Commit 25 — reserve/charge_from_reserve/release_reserve billing helpers."""

    def setUp(self):
        self.user = User.objects.create_user(email='res@t.ru', password='x', pages_count=50)
        self.project = StudioProject.objects.create(user=self.user, name='R', status='ready', mode='auto')

    def test_reserve_reduces_balance_and_increases_reserved(self):
        from studio.billing import reserve
        result = reserve(self.user, 20, self.project)
        self.assertTrue(result)
        self.user.refresh_from_db()
        self.assertEqual(self.user.pages_count, 30)
        self.project.refresh_from_db()
        self.assertEqual(self.project.stars_reserved, 20)

    def test_reserve_fails_on_insufficient_balance(self):
        from studio.billing import reserve
        result = reserve(self.user, 100, self.project)
        self.assertFalse(result)
        self.user.refresh_from_db()
        self.assertEqual(self.user.pages_count, 50)

    def test_charge_from_reserve_uses_reserve_first(self):
        from studio.billing import reserve, charge_from_reserve
        reserve(self.user, 20, self.project)
        result = charge_from_reserve(10, self.project)
        self.assertTrue(result)
        self.project.refresh_from_db()
        self.assertEqual(self.project.stars_reserved, 10)
        self.assertEqual(self.project.stars_spent, 10)

    def test_release_reserve_returns_unused_to_balance(self):
        from studio.billing import reserve, release_reserve
        reserve(self.user, 20, self.project)
        self.user.refresh_from_db()
        balance_after_reserve = self.user.pages_count
        release_reserve(self.project)
        self.user.refresh_from_db()
        self.assertEqual(self.user.pages_count, balance_after_reserve + 20)
        self.project.refresh_from_db()
        self.assertEqual(self.project.stars_reserved, 0)

    def test_next_step_calls_release_reserve_on_completion(self):
        from studio.tasks import next_step
        from studio.billing import reserve
        reserve(self.user, 20, self.project)
        self.project.interview_data = {'planned_steps': 1}
        self.project.save(update_fields=['interview_data'])
        state = StudioPipelineState.objects.create(project=self.project, status='running', step_index=0)

        with patch('studio.tasks.publish_event'):
            next_step(str(self.project.id), 0)  # nxt=1 >= total=1 → completed

        self.project.refresh_from_db()
        self.assertEqual(self.project.stars_reserved, 0)
        self.assertEqual(self.project.status, 'completed')


class SandboxLimitTest(APITestCase):
    """Commit 24 — run_pipeline aborts when per-user sandbox limit is reached."""

    def setUp(self):
        self.user = User.objects.create_user(email='limit@t.ru', password='x', pages_count=100)

    @patch('studio.tasks.sandbox')
    @patch('studio.tasks.publish_event')
    def test_sandbox_limit_blocks_spawn(self, mock_pub, mock_sandbox):
        from studio.tasks import run_pipeline
        mock_sandbox.count_user_sandboxes.return_value = 2  # at limit
        project = StudioProject.objects.create(user=self.user, name='L', status='coding', mode='auto')
        StudioPipelineState.objects.create(project=project, status='running', step_index=0)

        with self.settings(STUDIO_MAX_SANDBOXES_PER_USER=2):
            run_pipeline(str(project.id))

        mock_sandbox.spawn_sandbox.assert_not_called()
        project.refresh_from_db()
        self.assertEqual(project.status, 'paused')

    @patch('studio.tasks.sandbox')
    @patch('studio.tasks.publish_event')
    def test_sandbox_spawns_when_under_limit(self, mock_pub, mock_sandbox):
        from studio.tasks import run_pipeline
        mock_sandbox.count_user_sandboxes.return_value = 1
        mock_sandbox.spawn_sandbox.return_value = 'sandbox_abc'
        mock_sandbox.write_files.return_value = None
        mock_sandbox.install_deps.return_value = (0, '')
        mock_sandbox.isolate.return_value = None
        mock_sandbox.start_dev_server.return_value = 3000
        project = StudioProject.objects.create(user=self.user, name='L2', status='coding', mode='auto')
        StudioPipelineState.objects.create(project=project, status='running', step_index=0)

        with self.settings(STUDIO_MAX_SANDBOXES_PER_USER=2):
            with patch('studio.tasks.start_step') as mock_start:
                run_pipeline(str(project.id))

        mock_sandbox.spawn_sandbox.assert_called_once()


class AtomicGiteaCommitTest(APITestCase):
    """Commit 23 — commit_to_gitea uses put_files_batch for a single atomic commit per step."""

    def setUp(self):
        self.user = User.objects.create_user(email='gitea@t.ru', password='x', pages_count=100)
        self.client.force_authenticate(self.user)

    @patch('studio.tasks.gitea_client')
    @patch('studio.tasks.publish_event')
    def test_uses_put_files_batch_not_put_file(self, mock_pub, mock_gitea):
        from studio.tasks import commit_to_gitea
        project = StudioProject.objects.create(user=self.user, name='G', status='coding', mode='auto')
        state = StudioPipelineState.objects.create(project=project, status='running', step_index=1)
        mock_gitea.put_files_batch.return_value = {'commit': {'sha': 'abc123'}}

        commit_to_gitea(str(project.id), 1)

        mock_gitea.put_file.assert_not_called()
        mock_gitea.put_files_batch.assert_called_once()

    @patch('studio.tasks.next_step')
    @patch('studio.tasks.gitea_client')
    @patch('studio.tasks.publish_event')
    def test_git_sha_stored_in_version(self, mock_pub, mock_gitea, mock_next):
        from studio.tasks import commit_to_gitea
        from studio.models import StudioVersion
        project = StudioProject.objects.create(
            user=self.user, name='G2', status='coding', mode='auto',
            repo_url='https://git.example.com/user/repo',
        )
        self.user.gitea_username = 'user'
        self.user.save(update_fields=['gitea_username'])
        project.refresh_from_db()
        StudioPipelineState.objects.create(project=project, status='running', step_index=0)
        mock_gitea.put_files_batch.return_value = {'commit': {'sha': 'deadbeef'}}

        commit_to_gitea(str(project.id), 0)

        version = StudioVersion.objects.filter(project=project, step_index=0).first()
        self.assertIsNotNone(version)
        self.assertEqual(version.git_sha, 'deadbeef')


class SpaCrawlingTest(APITestCase):
    """Commit 19 — crawl_and_analyze falls back to crawl_spa_task when static text is short."""

    def _make_project(self):
        project = MagicMock()
        project.id = 'test-uuid'
        project.target_url = 'https://example.com'
        project.interview_data = {}
        project.status = 'draft'
        return project

    @patch('studio.tasks.crawl_spa_task')
    @patch('studio.tasks.publish_event')
    @patch('studio.tasks.StudioProject')
    @patch('studio.tasks.crawl')
    def test_short_text_triggers_spa_crawl(self, mock_crawl, MockQS, mock_pub, mock_spa_task):
        from studio.tasks import crawl_and_analyze
        project = self._make_project()
        MockQS.objects.get.return_value = project
        mock_crawl.return_value = {'text': '   ', 'title': ''}
        crawl_and_analyze(str(project.id))
        mock_spa_task.delay.assert_called_once_with(str(project.id))

    @patch('studio.tasks.crawl_spa_task')
    @patch('studio.tasks.agent_analyze')
    @patch('studio.tasks.publish_event')
    @patch('studio.tasks.StudioProject')
    @patch('studio.tasks.crawl')
    def test_long_text_skips_spa_crawl(self, mock_crawl, MockQS, mock_pub, mock_analyze, mock_spa_task):
        from studio.tasks import crawl_and_analyze
        project = self._make_project()
        MockQS.objects.get.return_value = project
        mock_crawl.return_value = {'text': 'x' * 500, 'title': 'Test'}
        crawl_and_analyze(str(project.id))
        mock_spa_task.delay.assert_not_called()
        mock_analyze.delay.assert_called_once()


class ContextChatViewTest(APITestCase):
    """Commit 17 — ContextChatView answers via LLM, charges 1 star, saves history."""

    def setUp(self):
        self.user = User.objects.create_user(email='chat@t.ru', password='x', pages_count=10)
        self.client.force_authenticate(self.user)

    @patch('studio.agents.assistant.AssistantAgent.answer', return_value='Вот ответ ассистента')
    @patch('studio.billing.charge')
    def test_chat_returns_answer_and_charges(self, mock_charge, mock_answer):
        project = StudioProject.objects.create(user=self.user, name='C')
        StudioPipelineState.objects.create(project=project)
        r = self.client.post(
            f'/api/v1/studio/projects/{project.id}/chat/',
            {'message': 'Что делать дальше?'},
            format='json',
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['answer'], 'Вот ответ ассистента')
        mock_charge.assert_called_once()
        project.refresh_from_db()
        history = project.interview_data.get('assistant_history', [])
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]['role'], 'user')
        self.assertEqual(history[1]['role'], 'assistant')

    def test_chat_no_stars_returns_402(self):
        self.user.pages_count = 0
        self.user.save()
        project = StudioProject.objects.create(user=self.user, name='C2')
        StudioPipelineState.objects.create(project=project)
        r = self.client.post(
            f'/api/v1/studio/projects/{project.id}/chat/',
            {'message': 'test'},
            format='json',
        )
        self.assertEqual(r.status_code, 402)


class PreviewProxyViewTest(APITestCase):
    """Commit 15 — PreviewProxyView proxies content from sandbox container."""

    def setUp(self):
        self.user = User.objects.create_user(email='preview@t.ru', password='x')
        self.client.force_authenticate(self.user)

    @patch('studio.views.pipeline._rq.get')
    def test_proxy_returns_upstream_content(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.content = b'<html>ok</html>'
        mock_resp.status_code = 200
        mock_resp.headers = {'Content-Type': 'text/html'}
        mock_get.return_value = mock_resp

        project = StudioProject.objects.create(
            user=self.user, name='P', sandbox_container_id='sandbox-cid',
        )
        StudioPipelineState.objects.create(project=project)
        r = self.client.get(f'/api/v1/studio/projects/{project.id}/preview/')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'ok', r.content)

    def test_proxy_no_sandbox_returns_503(self):
        project = StudioProject.objects.create(user=self.user, name='P2')
        StudioPipelineState.objects.create(project=project)
        r = self.client.get(f'/api/v1/studio/projects/{project.id}/preview/')
        self.assertEqual(r.status_code, 503)


class ManualEditSyncTest(APITestCase):
    """Commit 14 — PATCH file enqueues sync_manual_edit; sync pushes to sandbox."""

    def setUp(self):
        self.user = User.objects.create_user(email='edit@t.ru', password='x')
        self.client.force_authenticate(self.user)

    @patch('studio.tasks.sync_manual_edit')
    def test_patch_file_enqueues_sync(self, mock_task):
        from studio.models import StudioFile
        project = StudioProject.objects.create(user=self.user, name='M')
        StudioPipelineState.objects.create(project=project)
        f = StudioFile.objects.create(project=project, path='index.ts', content='old')
        r = self.client.patch(
            f'/api/v1/studio/projects/{project.id}/files/{f.id}/',
            {'content': 'new'},
            format='json',
        )
        self.assertEqual(r.status_code, 200)
        mock_task.delay.assert_called_once_with(str(project.id), f.id)

    @patch('studio.tasks.sandbox')
    @patch('studio.tasks.publish_event')
    @patch('studio.tasks.StudioProject')
    def test_sync_manual_edit_writes_to_sandbox(self, MockQS, mock_pub, mock_sandbox):
        from studio.tasks import sync_manual_edit
        from studio.models import StudioFile
        project = MagicMock()
        project.id = 'proj-id'
        project.sandbox_container_id = 'cid-123'
        project.repo_url = ''
        project.user.gitea_username = ''
        f = MagicMock()
        f.path = 'src/main.ts'
        f.content = 'const x = 1'
        MockQS.objects.get.return_value = project
        with patch('studio.tasks.StudioFile') as MockFile:
            MockFile.objects.get.return_value = f
            sync_manual_edit('proj-id', 1)
        mock_sandbox.write_files.assert_called_once_with('cid-123', {'src/main.ts': 'const x = 1'})


class FileDiffViewTest(APITestCase):
    """Commit 13 — FileDiffView returns old content from Gitea and new from DB."""

    def setUp(self):
        self.user = User.objects.create_user(email='diff@t.ru', password='x')
        self.client.force_authenticate(self.user)

    @patch('studio.gitea_client.get_file_content', return_value='old content')
    def test_diff_returns_old_and_new(self, mock_gc):
        from studio.models import StudioFile
        project = StudioProject.objects.create(
            user=self.user, name='D',
            repo_url='https://gitea.example.com/user/repo',
        )
        self.user.gitea_username = 'user'
        self.user.save()
        StudioPipelineState.objects.create(project=project)
        f = StudioFile.objects.create(project=project, path='src/app.ts', content='new content')
        r = self.client.get(f'/api/v1/studio/projects/{project.id}/files/{f.id}/diff/?ref=abc123')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['old'], 'old content')
        self.assertEqual(r.data['new'], 'new content')


class EstimateViewTest(APITestCase):
    """Commit 8 — EstimateView returns real star estimate, not hardcoded value."""

    def setUp(self):
        self.user = User.objects.create_user(email='est@t.ru', password='x', pages_count=200)
        self.client.force_authenticate(self.user)

    @patch('studio.billing.estimate_stars', return_value=90)
    def test_estimate_returns_correct_fields(self, mock_est):
        project = StudioProject.objects.create(
            user=self.user, name='E',
            interview_data={'planned_steps': 3},
        )
        StudioPipelineState.objects.create(project=project)
        r = self.client.get(f'/api/v1/studio/projects/{project.id}/estimate/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('estimated_stars', r.data)
        self.assertIn('affordable', r.data)
        self.assertEqual(r.data['planned_steps'], 3)
        self.assertEqual(r.data['balance'], 200)


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
