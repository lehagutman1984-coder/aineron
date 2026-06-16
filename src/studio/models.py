import uuid
from django.db import models
from django.conf import settings


class StudioProject(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('interview', 'Интервью'),
        ('planning', 'Планирование'),
        ('ready', 'Готов к кодингу'),
        ('coding', 'Кодинг'),
        ('paused', 'Пауза'),
        ('completed', 'Завершён'),
        ('failed', 'Ошибка'),
    ]
    MODE_CHOICES = [('auto', 'Авто'), ('semi', 'Полу-авто'), ('manual', 'Ручной')]
    ENTRY_CHOICES = [('description', 'С нуля'), ('clone_url', 'Клон по URL')]
    STACK_CHOICES = [
        ('nextjs', 'Next.js'), ('react', 'React'), ('vue', 'Vue'), ('html', 'HTML'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='studio_projects'
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default='auto')
    entry_mode = models.CharField(max_length=20, choices=ENTRY_CHOICES, default='description')
    target_url = models.URLField(blank=True)
    target_stack = models.CharField(max_length=10, choices=STACK_CHOICES, default='nextjs')
    interview_data = models.JSONField(default=dict, blank=True)
    project_md_content = models.TextField(blank=True)
    commits_md_content = models.TextField(blank=True)
    sandbox_container_id = models.CharField(max_length=128, blank=True)
    preview_port = models.IntegerField(null=True, blank=True)
    repo_url = models.URLField(blank=True)
    stars_reserved = models.IntegerField(default=0)
    stars_spent = models.IntegerField(default=0)
    vercel_deployment_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.user_id})'


class StudioFile(models.Model):
    project = models.ForeignKey(StudioProject, on_delete=models.CASCADE, related_name='files')
    path = models.CharField(max_length=512)
    content = models.TextField(blank=True)
    language = models.CharField(max_length=40, blank=True)
    last_modified_by = models.CharField(max_length=40, default='agent')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('project', 'path')]
        ordering = ['path']

    def __str__(self):
        return f'{self.project_id}/{self.path}'


class StudioPipelineState(models.Model):
    STATUS_CHOICES = [
        ('idle', 'idle'),
        ('running', 'running'),
        ('paused_on_loop', 'paused_on_loop'),
        ('paused_manual', 'paused_manual'),
        ('completed', 'completed'),
        ('failed', 'failed'),
    ]
    project = models.OneToOneField(
        StudioProject, on_delete=models.CASCADE, related_name='pipeline'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='idle')
    step_index = models.IntegerField(default=0)
    iteration_count = models.IntegerField(default=0)
    review_report = models.JSONField(default=dict, blank=True)
    test_report = models.JSONField(default=dict, blank=True)
    fix_plan = models.JSONField(default=dict, blank=True)
    last_error = models.TextField(blank=True)
    pause_reason = models.TextField(blank=True)
    resume_hint = models.TextField(blank=True)
    pause_requested = models.BooleanField(default=False)
    current_task_id = models.CharField(max_length=64, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Pipeline[{self.project_id}] {self.status}'


class StudioVersion(models.Model):
    project = models.ForeignKey(
        StudioProject, on_delete=models.CASCADE, related_name='versions'
    )
    git_sha = models.CharField(max_length=64, blank=True)
    step_index = models.IntegerField(default=0)
    step_name = models.CharField(max_length=200, blank=True)
    stars_spent_at_version = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'v{self.step_index} ({self.git_sha[:7] if self.git_sha else "—"})'


class StudioCollaborator(models.Model):
    ROLE_CHOICES = [('viewer', 'Просмотр'), ('editor', 'Редактирование')]
    project = models.ForeignKey(StudioProject, on_delete=models.CASCADE, related_name='collaborators')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='studio_collabs'
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='viewer')

    class Meta:
        unique_together = [('project', 'user')]

    def __str__(self):
        return f'{self.user_id}@{self.project_id} ({self.role})'


class StudioTemplate(models.Model):
    STACK_CHOICES = [
        ('nextjs', 'Next.js'), ('react', 'React'), ('vue', 'Vue'), ('html', 'HTML'),
    ]

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField()
    stack = models.CharField(max_length=10, choices=STACK_CHOICES, default='nextjs')
    preview_image = models.CharField(max_length=300, blank=True)
    seed_prompt = models.TextField()
    order = models.IntegerField(default=0)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='studio_templates',
    )
    is_public = models.BooleanField(default=False)
    usage_count = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.name
