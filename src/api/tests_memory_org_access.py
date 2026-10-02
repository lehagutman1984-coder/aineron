"""
2026-10-02 (аудит безопасности, №26): MemoryDetailView.get_queryset() фильтровал
только по user=request.user - создатель орг-факта (UserMemory.organization задан)
сохранял право PATCH/DELETE через общий /v1/memory/<id>/ даже после выхода из
организации. Правильный org-aware путь (OrgMemoryView, owner/admin) не был
единственным маршрутом к тем же строкам.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from aitext.models import UserMemory
from teams.models import Organization, OrganizationMember

User = get_user_model()


class OrgMemoryDetailAccessTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(
            username='creator', email='creator@t.ru', password='x'
        )
        self.owner = User.objects.create_user(
            username='owner', email='owner@t.ru', password='x'
        )
        self.org = Organization.objects.create(name='Acme', owner=self.owner, balance_rub=0)
        self.membership = OrganizationMember.objects.create(
            organization=self.org, user=self.creator, role=OrganizationMember.Role.MEMBER
        )
        self.fact = UserMemory.objects.create(
            user=self.creator, content='Общий факт команды', organization=self.org,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.creator)

    def test_member_can_edit_org_fact(self):
        resp = self.client.patch(f'/api/v1/memory/{self.fact.id}/', {'content': 'Новый текст'}, format='json')
        self.assertEqual(resp.status_code, 200)

    def test_former_member_loses_access_after_leaving(self):
        """Ровно баг из аудита: membership удалена (вышел/исключён) - но
        fact.user всё ещё creator - доступ через общий эндпоинт должен исчезнуть."""
        self.membership.delete()
        resp = self.client.patch(f'/api/v1/memory/{self.fact.id}/', {'content': 'Новый текст'}, format='json')
        self.assertEqual(resp.status_code, 404)

        resp2 = self.client.delete(f'/api/v1/memory/{self.fact.id}/')
        self.assertEqual(resp2.status_code, 404)

        self.fact.refresh_from_db()
        self.assertEqual(self.fact.content, 'Общий факт команды')  # не изменилось

    def test_org_owner_keeps_access_without_explicit_membership_row(self):
        """Owner организации не обязан иметь OrganizationMember-строку."""
        fact_by_owner = UserMemory.objects.create(
            user=self.owner, content='Факт владельца', organization=self.org,
        )
        owner_client = APIClient()
        owner_client.force_authenticate(self.owner)
        resp = owner_client.patch(f'/api/v1/memory/{fact_by_owner.id}/', {'content': 'Правка'}, format='json')
        self.assertEqual(resp.status_code, 200)

    def test_personal_non_org_fact_unaffected(self):
        """Обычный личный факт (organization=None) - поведение не меняется."""
        personal = UserMemory.objects.create(user=self.creator, content='Личный факт')
        resp = self.client.patch(f'/api/v1/memory/{personal.id}/', {'content': 'Правка'}, format='json')
        self.assertEqual(resp.status_code, 200)
