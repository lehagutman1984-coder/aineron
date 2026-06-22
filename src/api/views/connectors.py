import hashlib
import hmac
import re
from urllib.parse import urlparse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import serializers

from aitext.models import Project, ProjectConnector, ProjectCommit
from aitext.crypto import encrypt_token, decrypt_token
from api.views._project_access import get_project_for_user


def _gitea_base_url(connector: 'ProjectConnector') -> str | None:
    """Extract base URL (scheme+host) from Gitea connector repo_url."""
    parsed = urlparse(connector.repo_url)
    if parsed.netloc:
        return f'{parsed.scheme}://{parsed.netloc}'
    return None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _parse_github_url(url: str):
    """github.com/owner/repo → (owner, repo)"""
    m = re.search(r'github\.com[/:]([^/]+)/([^/.]+)', url)
    if m:
        return m.group(1), m.group(2)
    return None, None


def _parse_gitea_url(url: str, base_url: str):
    """gitea.example.com/owner/repo → (owner, repo)"""
    host = base_url.rstrip('/').split('://', 1)[-1]
    m = re.search(rf'{re.escape(host)}/([^/]+)/([^/.]+)', url)
    if m:
        return m.group(1), m.group(2)
    parts = [p for p in url.split('/') if p]
    if len(parts) >= 2:
        return parts[-2], parts[-1].replace('.git', '')
    return None, None


# ── Serializers ───────────────────────────────────────────────────────────────

class ConnectorSerializer(serializers.ModelSerializer):
    webhook_url = serializers.SerializerMethodField()

    class Meta:
        model = ProjectConnector
        fields = [
            'id', 'connector_type', 'repo_url', 'owner', 'repo', 'branch',
            'webhook_url', 'webhook_secret', 'last_synced_at', 'created_at',
            'auto_sync', 'sync_status', 'last_sync_report',
        ]
        read_only_fields = ['id', 'owner', 'repo', 'webhook_url', 'webhook_secret', 'last_synced_at', 'created_at',
                            'sync_status', 'last_sync_report']

    def get_webhook_url(self, obj) -> str:
        request = self.context.get('request')
        if request:
            from django.conf import settings
            base = getattr(settings, 'SITE_URL', request.build_absolute_uri('/').rstrip('/'))
            return f'{base}/api/v1/projects/{obj.project_id}/connectors/{obj.id}/webhook/'
        return ''


class CommitFileSerializer(serializers.Serializer):
    path = serializers.CharField(max_length=500)
    content = serializers.CharField()


class CommitSerializer(serializers.ModelSerializer):
    connector_id = serializers.IntegerField(source='connector.id', read_only=True)

    class Meta:
        model = ProjectCommit
        fields = ['id', 'connector_id', 'commit_message', 'files', 'status', 'kind',
                  'pr_branch', 'pr_url', 'error_message', 'created_at', 'pushed_at']
        read_only_fields = ['id', 'status', 'kind', 'pr_branch', 'pr_url', 'error_message', 'created_at', 'pushed_at']


# ── Views ─────────────────────────────────────────────────────────────────────

class ConnectorListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        project = get_project_for_user(pk, request.user, write=False)
        qs = project.connectors.all()
        return Response(ConnectorSerializer(qs, many=True, context={'request': request}).data)

    def post(self, request, pk):
        project = get_project_for_user(pk, request.user, write=True)
        if project.connectors.count() >= 3:
            return Response({'error': 'Максимум 3 коннектора на проект'}, status=400)

        connector_type = request.data.get('connector_type', '').strip()
        repo_url = request.data.get('repo_url', '').strip()
        access_token = request.data.get('access_token', '').strip()
        branch = request.data.get('branch', 'main').strip() or 'main'

        if connector_type not in ('github', 'gitea'):
            return Response({'error': 'Тип коннектора: github или gitea'}, status=400)
        if not repo_url:
            return Response({'error': 'Укажите URL репозитория'}, status=400)
        if not access_token:
            return Response({'error': 'Укажите Personal Access Token'}, status=400)

        if connector_type == 'github':
            owner, repo = _parse_github_url(repo_url)
        else:
            from django.conf import settings
            gitea_base = getattr(settings, 'STUDIO_GITEA_URL', '')
            owner, repo = _parse_gitea_url(repo_url, gitea_base)

        if not owner or not repo:
            return Response({'error': 'Не удалось разобрать owner/repo из URL'}, status=400)

        try:
            enc_token = encrypt_token(access_token)
        except RuntimeError as e:
            return Response({'error': str(e)}, status=500)

        connector, created = ProjectConnector.objects.get_or_create(
            project=project, owner=owner, repo=repo,
            defaults={
                'connector_type': connector_type,
                'repo_url': repo_url,
                'branch': branch,
                'access_token_enc': enc_token,
            }
        )
        if not created:
            connector.branch = branch
            connector.access_token_enc = enc_token
            connector.repo_url = repo_url
            connector.save(update_fields=['branch', 'access_token_enc', 'repo_url'])

        return Response(ConnectorSerializer(connector, context={'request': request}).data, status=201 if created else 200)


class ConnectorDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, request, pk, connector_id, write=False):
        project = get_project_for_user(pk, request.user, write=write)
        return get_object_or_404(ProjectConnector, pk=connector_id, project=project)

    def patch(self, request, pk, connector_id):
        connector = self._get(request, pk, connector_id, write=True)
        if 'auto_sync' in request.data:
            connector.auto_sync = bool(request.data['auto_sync'])
            connector.save(update_fields=['auto_sync'])
        return Response(ConnectorSerializer(connector, context={'request': request}).data)

    def delete(self, request, pk, connector_id):
        connector = self._get(request, pk, connector_id, write=True)
        connector.delete()
        return Response(status=204)


class ConnectorReadFilesView(APIView):
    """Browse file tree from a connected repo."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, connector_id):
        project = get_project_for_user(pk, request.user, write=False)
        connector = get_object_or_404(ProjectConnector, pk=connector_id, project=project)

        try:
            token = decrypt_token(connector.access_token_enc)
        except Exception as e:
            return Response({'error': f'Ошибка токена: {e}'}, status=500)

        try:
            if connector.connector_type == 'github':
                from aitext.github_client import list_tree
                items = list_tree(connector.owner, connector.repo, token, connector.branch)
            else:
                from studio.gitea_client import list_tree
                items = list_tree(connector.owner, connector.repo, connector.branch,
                                  token=token, base_url=_gitea_base_url(connector))
        except Exception as e:
            return Response({'error': f'Ошибка доступа к репозиторию: {e}'}, status=502)

        return Response({'items': items})


class ConnectorFileContentView(APIView):
    """Get single file content from connected repo."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, connector_id):
        project = get_project_for_user(pk, request.user, write=False)
        connector = get_object_or_404(ProjectConnector, pk=connector_id, project=project)
        path = request.query_params.get('path', '')
        if not path:
            return Response({'error': 'Укажите path'}, status=400)

        try:
            token = decrypt_token(connector.access_token_enc)
        except Exception as e:
            return Response({'error': f'Ошибка токена: {e}'}, status=500)

        try:
            if connector.connector_type == 'github':
                from aitext.github_client import get_file_content
                content = get_file_content(connector.owner, connector.repo, token, path, connector.branch)
            else:
                from studio.gitea_client import get_file_content_ext
                content = get_file_content_ext(connector.owner, connector.repo, path, connector.branch,
                                               token=token, base_url=_gitea_base_url(connector))
        except Exception as e:
            return Response({'error': f'Ошибка чтения файла: {e}'}, status=502)

        return Response({'path': path, 'content': content})


# ── Commits ───────────────────────────────────────────────────────────────────

class CommitListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        project = get_project_for_user(pk, request.user, write=False)
        qs = project.commits.select_related('connector').order_by('-created_at')[:50]
        return Response(CommitSerializer(qs, many=True).data)

    def post(self, request, pk):
        project = get_project_for_user(pk, request.user, write=True)
        connector_id = request.data.get('connector_id')
        commit_message = (request.data.get('commit_message') or '').strip()
        files = request.data.get('files', [])

        if not commit_message:
            return Response({'error': 'Укажите сообщение коммита'}, status=400)
        if not files:
            return Response({'error': 'Добавьте хотя бы один файл'}, status=400)
        if len(files) > 50:
            return Response({'error': 'Максимум 50 файлов на коммит'}, status=400)

        connector = None
        if connector_id:
            connector = get_object_or_404(ProjectConnector, pk=connector_id, project=project)

        for f in files:
            if not isinstance(f, dict) or 'path' not in f or 'content' not in f:
                return Response({'error': 'Каждый файл должен содержать path и content'}, status=400)

        commit = ProjectCommit.objects.create(
            project=project,
            connector=connector,
            commit_message=commit_message,
            files=files,
            status='pending',
        )
        return Response(CommitSerializer(commit).data, status=201)


class CommitConfirmView(APIView):
    """Confirm (push) or reject a pending commit."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, commit_id):
        project = get_project_for_user(pk, request.user, write=True)
        commit = get_object_or_404(ProjectCommit, pk=commit_id, project=project)

        if commit.status != 'pending':
            return Response({'error': f'Коммит уже обработан: {commit.status}'}, status=400)

        action = request.data.get('action', '')
        if action == 'reject':
            commit.status = 'rejected'
            commit.save(update_fields=['status'])
            return Response(CommitSerializer(commit).data)

        if action in ('push', 'pr'):
            if not commit.connector:
                return Response({'error': 'Нет коннектора для пуша'}, status=400)
            if action == 'pr':
                from django.conf import settings
                if not getattr(settings, 'PROJECT_PR_PROPOSALS', False):
                    return Response({'error': 'PR-режим отключён (PROJECT_PR_PROPOSALS=0)'}, status=400)
                commit.kind = 'pull_request'
                commit.save(update_fields=['kind'])
            from aitext.tasks import push_project_commit
            push_project_commit.delay(commit.id)
            return Response({'status': 'queued', 'commit_id': commit.id, 'kind': commit.kind})

        return Response({'error': 'action должен быть push, pr или reject'}, status=400)


# ── Inbound Sync (Sprint 4.2) ─────────────────────────────────────────────────

class ConnectorSyncView(APIView):
    """POST /projects/<pk>/connectors/<connector_id>/sync/ — запустить синхронизацию немедленно."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, connector_id):
        project = get_project_for_user(pk, request.user, write=True)
        connector = get_object_or_404(ProjectConnector, pk=connector_id, project=project)
        from aitext.tasks import sync_connector_task
        sync_connector_task.delay(connector.id)
        return Response({'status': 'queued', 'connector_id': connector.id})


class ConnectorDeployView(APIView):
    """POST .../connectors/<cid>/deploy/ — триггер внешнего deploy-вебхука (HMAC).
    GET  .../connectors/<cid>/deploy/ — статус деплоя (полинг).

    Sprint 7.2. Флаг: PROJECT_DEPLOY_HOOK=1.
    Авторизация: владелец проекта (write access).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, connector_id):
        from django.conf import settings
        if not getattr(settings, 'PROJECT_DEPLOY_HOOK', False):
            return Response({'error': 'deploy hook disabled'}, status=503)
        project = get_project_for_user(pk, request.user)
        connector = get_object_or_404(ProjectConnector, pk=connector_id, project=project)
        return Response({
            'deploy_status': connector.deploy_status,
            'last_deploy_at': connector.last_deploy_at.isoformat() if connector.last_deploy_at else None,
            'last_deploy_log': connector.last_deploy_log[-2000:] if connector.last_deploy_log else '',
        })

    def post(self, request, pk, connector_id):
        from django.conf import settings
        if not getattr(settings, 'PROJECT_DEPLOY_HOOK', False):
            return Response({'error': 'deploy hook disabled'}, status=503)

        project = get_project_for_user(pk, request.user, write=True)
        connector = get_object_or_404(ProjectConnector, pk=connector_id, project=project)

        if not connector.deploy_webhook_url:
            return Response({'error': 'deploy_webhook_url not configured'}, status=400)

        # Decrypt deploy secret
        deploy_secret = ''
        if connector.deploy_secret_enc:
            try:
                deploy_secret = decrypt_token(connector.deploy_secret_enc)
            except Exception:
                pass

        # Build signed payload
        import json
        payload = json.dumps({
            'project_id': project.id,
            'connector_id': connector.id,
            'repo': f'{connector.owner}/{connector.repo}',
            'branch': connector.branch,
        }).encode()

        # HMAC-sign with deploy_secret (same pattern as services/webhooks.py:25)
        sig = hmac.new(
            deploy_secret.encode() if deploy_secret else b'',
            payload,
            hashlib.sha256,
        ).hexdigest()

        try:
            import requests as _req
            resp = _req.post(
                connector.deploy_webhook_url,
                data=payload,
                headers={
                    'Content-Type': 'application/json',
                    'X-Aineron-Signature': f'sha256={sig}',
                    'X-Aineron-Event': 'deploy',
                },
                timeout=15,
            )
            connector.deploy_status = 'success' if resp.ok else 'error'
            connector.last_deploy_log = resp.text[:2000]
        except Exception as e:
            connector.deploy_status = 'error'
            connector.last_deploy_log = str(e)[:2000]

        connector.last_deploy_at = timezone.now()
        connector.save(update_fields=['deploy_status', 'last_deploy_at', 'last_deploy_log'])

        return Response({
            'deploy_status': connector.deploy_status,
            'last_deploy_at': connector.last_deploy_at.isoformat(),
            'log': connector.last_deploy_log,
        })


@method_decorator(csrf_exempt, name='dispatch')
class ConnectorWebhookView(APIView):
    """POST /projects/<pk>/connectors/<connector_id>/webhook/ — GitHub/Gitea push webhook.

    GitHub: X-Hub-Signature-256: sha256=<hmac>
    Gitea:  X-Gitea-Signature: <hmac>
    """
    permission_classes = [AllowAny]
    authentication_classes = []  # no session / JWT — it's a public webhook

    def _verify_signature(self, request, secret: str) -> bool:
        body = request.body
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        sig = (
            request.META.get('HTTP_X_HUB_SIGNATURE_256', '')
            or request.META.get('HTTP_X_GITEA_SIGNATURE', '')
        )
        if sig.startswith('sha256='):
            sig = sig[7:]
        if not sig:
            return False
        return hmac.compare_digest(sig, expected)

    def post(self, request, pk, connector_id):
        try:
            connector = ProjectConnector.objects.select_related('project').get(id=connector_id, project_id=pk)
        except ProjectConnector.DoesNotExist:
            return Response(status=404)

        if not connector.webhook_secret:
            return Response({'error': 'webhook not configured'}, status=400)

        if not self._verify_signature(request, connector.webhook_secret):
            return Response({'error': 'invalid signature'}, status=401)

        event = (
            request.META.get('HTTP_X_GITHUB_EVENT', '')
            or request.META.get('HTTP_X_GITEA_EVENT', '')
        )
        if event not in ('', 'push'):
            return Response({'status': 'ignored', 'event': event})

        from aitext.tasks import sync_connector_task
        sync_connector_task.delay(connector.id)
        return Response({'status': 'queued'})
