import secrets
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.conf import settings

logger = logging.getLogger('studio.signals')

User = get_user_model()


@receiver(post_save, sender=User)
def ensure_gitea_account(sender, instance, created, **kwargs):
    """Create a Gitea user account when a new site user registers.

    aineron.net (INTL_MODE=1) не разворачивает Gitea вообще (см. CLAUDE.md,
    «Два инстанса, один репозиторий») — Studio там использует GitHub, не
    самохостed git. Без этой проверки каждая регистрация на .net кидала
    перехваченную, но шумную ошибку резолва хоста 'gitea' в лог.
    """
    if not created or instance.gitea_username or getattr(settings, 'INTL_MODE', False):
        return
    username = f'u{instance.id}'
    password = secrets.token_urlsafe(16)
    try:
        from . import gitea_client
        gitea_client.create_user(
            username,
            instance.email or f'{username}@aineron.local',
            password,
        )
        instance.gitea_username = username
        instance.gitea_password = password
        instance.save(update_fields=['gitea_username', 'gitea_password'])
        logger.info('Gitea account created: %s', username)
    except Exception as exc:
        logger.warning('Failed to create Gitea account for user %s: %s', instance.id, exc)


@receiver(post_save, sender='studio.StudioProject')
def ensure_repo(sender, instance, created, **kwargs):
    """Create a private Gitea repo when a new StudioProject is created."""
    if not created or instance.repo_url or not instance.user.gitea_username or getattr(settings, 'INTL_MODE', False):
        return
    repo_name = f'project-{str(instance.id)[:8]}'
    try:
        from . import gitea_client
        gitea_client.create_repo(instance.user.gitea_username, repo_name, private=True)
        instance.repo_url = (
            f'{settings.STUDIO_GITEA_URL}/{instance.user.gitea_username}/{repo_name}'
        )
        instance.save(update_fields=['repo_url'])
        logger.info('Gitea repo created: %s/%s', instance.user.gitea_username, repo_name)
    except Exception as exc:
        logger.warning('Failed to create Gitea repo for project %s: %s', instance.id, exc)
