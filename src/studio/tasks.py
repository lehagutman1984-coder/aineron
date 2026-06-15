from celery import shared_task
from .models import StudioProject
from .events import publish_event

QUEUE = 'studio_queue'


def _set_status(project, status):
    project.status = status
    project.save(update_fields=['status'])


@shared_task(bind=True, max_retries=3, queue=QUEUE)
def agent_interview(self, project_id):
    project = StudioProject.objects.get(id=project_id)
    from .agents.interviewer import InterviewerAgent
    try:
        InterviewerAgent(project).run()
        publish_event(project_id, {'agent': 'interviewer', 'level': 'info', 'text': 'Вопросы готовы'})
    except Exception as e:
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3, queue=QUEUE)
def agent_analyze(self, project_id):
    project = StudioProject.objects.get(id=project_id)
    from .agents.analyst import AnalystAgent
    try:
        publish_event(project_id, {'agent': 'analyst', 'level': 'info', 'text': 'Анализирую требования...'})
        AnalystAgent(project).run()
        publish_event(project_id, {'agent': 'analyst', 'level': 'info', 'text': 'PROJECT.md готов'})
        agent_plan.delay(project_id)
    except Exception as e:
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3, queue=QUEUE)
def agent_plan(self, project_id):
    project = StudioProject.objects.get(id=project_id)
    from .agents.planner import PlannerAgent
    try:
        publish_event(project_id, {'agent': 'planner', 'level': 'info', 'text': 'Составляю план...'})
        md, steps = PlannerAgent(project).run()
        state = project.pipeline
        state.review_report = {}
        state.save()
        project.interview_data['planned_steps'] = steps
        project.save(update_fields=['interview_data'])
        _set_status(project, 'ready')
        publish_event(project_id, {
            'agent': 'planner', 'level': 'info',
            'text': f'COMMITS.md готов: {steps} шагов',
        })
    except Exception as e:
        raise self.retry(exc=e, countdown=60)


@shared_task(queue=QUEUE)
def run_pipeline(project_id):
    project = StudioProject.objects.get(id=project_id)
    _set_status(project, 'coding')
    publish_event(project_id, {
        'agent': 'system', 'level': 'info',
        'text': 'Кодинг будет доступен в Спринте B',
    })
