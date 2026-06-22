from django.test import TestCase
from .models import StudioProject, StudioPipelineState
from .billing import estimate_stars, _billing_charge, release_reserve

class BillingTests(TestCase):
    def setUp(self):
        self.project = StudioProject.objects.create(
            ai_model='fast',
            stars_balance=100,
            stars_reserved=0,
            interview_data={},
        )
        self.pipeline = StudioPipelineState.objects.create(
            project=self.project,
            status='running',
        )

    def test_estimate_stars_uses_planned_steps(self):
        stars_5 = estimate_stars('fast', planned_steps=5)
        stars_8 = estimate_stars('fast', planned_steps=8)
        self.assertGreater(stars_8, stars_5)

    def test_billing_charge_and_reserve(self):
        self.project.stars_reserved = 10
        self.project.stars_balance = 50
        self.project.save()
        usage = {'completion_tokens': 200, 'prompt_tokens': 50}
        res = _billing_charge(self.project, 'coder', 1, usage=usage)
        self.assertTrue(res)
        log = self.project.interview_data.get('billing_log', [])
        self.assertEqual(log[-1]['tokens'], 250)
        self.assertIn('stars', log[-1])

    def test_release_reserve(self):
        self.project.stars_reserved = 30
        self.project.stars_balance = 15
        self.project.save()
        release_reserve(self.project)
        self.project.refresh_from_db()
        self.assertEqual(self.project.stars_reserved, 0)
        self.assertEqual(self.project.stars_balance, 45)
