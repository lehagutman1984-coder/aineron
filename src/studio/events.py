import json
import redis
from django.conf import settings

_r = redis.Redis.from_url(
    settings.REDIS_URL if hasattr(settings, 'REDIS_URL') else settings.CELERY_BROKER_URL
)


def _channel(project_id):
    return f'studio:events:{project_id}'


def publish_event(project_id, event: dict):
    _r.publish(_channel(project_id), json.dumps(event))


def get_pipeline_events(project_id):
    pubsub = _r.pubsub()
    pubsub.subscribe(_channel(project_id))
    try:
        for message in pubsub.listen():
            if message['type'] == 'message':
                data = message['data']
                yield data.decode() if isinstance(data, bytes) else data
    finally:
        pubsub.close()
