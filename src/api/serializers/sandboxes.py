"""
Сериализаторы Sandbox API (/api/v1/sandboxes/) — валидация пользовательского ввода.
Границы безопасности: пути файлов, env-ключи, размеры, таймауты.
"""
import re

from django.conf import settings
from rest_framework import serializers

from sandboxes.models import SandboxSession

_ENV_KEY_RE = re.compile(r'^[A-Z_][A-Z0-9_]*$')
_MAX_FILE_BYTES = 5 * 1024 * 1024
_ALLOWED_PATH_ROOTS = ('/home/user', '/tmp', '/app')


def validate_sandbox_path(path: str) -> str:
    """Абсолютные пути — только под разрешёнными корнями; '..' запрещён везде."""
    if not path or len(path) > 512:
        raise serializers.ValidationError('path: length must be 1..512')
    if '..' in path.split('/'):
        raise serializers.ValidationError('path: ".." is not allowed')
    if '\x00' in path:
        raise serializers.ValidationError('path: invalid characters')
    if path.startswith('/') and not any(
        path == root or path.startswith(root + '/') for root in _ALLOWED_PATH_ROOTS
    ):
        raise serializers.ValidationError(
            f'path: absolute paths must be under {", ".join(_ALLOWED_PATH_ROOTS)}'
        )
    return path


class SandboxCreateSerializer(serializers.Serializer):
    template = serializers.ChoiceField(
        choices=[c[0] for c in SandboxSession.Template.choices], default='base',
    )
    size = serializers.ChoiceField(
        choices=[c[0] for c in SandboxSession.Size.choices], default='standard',
    )
    timeout_seconds = serializers.IntegerField(min_value=60, required=False)
    env = serializers.DictField(
        child=serializers.CharField(max_length=4096, allow_blank=True),
        required=False, default=dict,
    )
    metadata = serializers.DictField(required=False, default=dict)

    def validate_timeout_seconds(self, value):
        max_ttl = int(getattr(settings, 'SANDBOX_MAX_TTL', 3600))
        if value > max_ttl:
            raise serializers.ValidationError(f'timeout_seconds must be ≤ {max_ttl}')
        return value

    def validate_env(self, value):
        if len(value) > 20:
            raise serializers.ValidationError('env: maximum 20 variables')
        for key in value:
            if not _ENV_KEY_RE.match(key):
                raise serializers.ValidationError(
                    f'env: invalid variable name "{key}" (expected [A-Z_][A-Z0-9_]*)'
                )
        return value

    def validate_metadata(self, value):
        import json
        if len(json.dumps(value)) > 2048:
            raise serializers.ValidationError('metadata: maximum 2 KB')
        return value


class SandboxExecSerializer(serializers.Serializer):
    command = serializers.CharField(max_length=8192, required=False, allow_blank=True, default='')
    code = serializers.CharField(max_length=256 * 1024, required=False, allow_blank=True, default='')
    language = serializers.ChoiceField(choices=['python', 'bash', 'node'], default='python')
    timeout_seconds = serializers.IntegerField(min_value=1, required=False, default=60)
    cwd = serializers.CharField(max_length=512, required=False, default='/home/user')
    background = serializers.BooleanField(default=False)

    def validate_timeout_seconds(self, value):
        max_exec = int(getattr(settings, 'SANDBOX_EXEC_TIMEOUT_MAX', 300))
        if value > max_exec:
            raise serializers.ValidationError(f'timeout_seconds must be ≤ {max_exec}')
        return value

    def validate_cwd(self, value):
        return validate_sandbox_path(value)

    def validate(self, attrs):
        if bool(attrs.get('command')) == bool(attrs.get('code')):
            raise serializers.ValidationError(
                'Provide exactly one of "command" or "code".'
            )
        return attrs


class SandboxFileItemSerializer(serializers.Serializer):
    path = serializers.CharField(max_length=512)
    content = serializers.CharField(allow_blank=True, trim_whitespace=False)
    encoding = serializers.ChoiceField(choices=['utf-8', 'base64'], default='utf-8')

    def validate_path(self, value):
        return validate_sandbox_path(value)

    def validate(self, attrs):
        content = attrs.get('content', '')
        # base64 расширяет ~4/3 — проверяем фактический размер полезной нагрузки
        approx = len(content) * 3 // 4 if attrs.get('encoding') == 'base64' else len(content.encode('utf-8'))
        if approx > _MAX_FILE_BYTES:
            raise serializers.ValidationError('content: maximum 5 MB per file')
        return attrs


class SandboxWriteFilesSerializer(serializers.Serializer):
    files = SandboxFileItemSerializer(many=True, min_length=1, max_length=50)


class SandboxTimeoutSerializer(serializers.Serializer):
    timeout_seconds = serializers.IntegerField(min_value=60)

    def validate_timeout_seconds(self, value):
        max_ttl = int(getattr(settings, 'SANDBOX_MAX_TTL', 3600))
        if value > max_ttl:
            raise serializers.ValidationError(f'timeout_seconds must be ≤ {max_ttl}')
        return value
