"""
2026-10-02 (аудит безопасности, LOW): project_file_upload_path() путь был
`project_files/<project_id>/<filename>` - nginx отдаёт /media/project_files/
напрямую без проверки авторизации, <project_id> последовательный PK,
<filename> часто предсказуемое имя ("resume.pdf") - файлы чужого приватного
проекта можно было перебрать. Путь теперь содержит случайный токен.
"""
from django.test import TestCase

from aitext.models import project_file_upload_path


class _FakeInstance:
    def __init__(self, project_id):
        self.project_id = project_id


class ProjectFileUploadPathTests(TestCase):
    def test_path_contains_unpredictable_token(self):
        path = project_file_upload_path(_FakeInstance(42), 'resume.pdf')
        self.assertTrue(path.startswith('project_files/42/'))
        self.assertTrue(path.endswith('_resume.pdf'))
        # Между '42/' и '_resume.pdf' должен быть непустой токен, не просто имя файла.
        middle = path[len('project_files/42/'):-len('_resume.pdf')]
        self.assertGreaterEqual(len(middle), 8)

    def test_two_uploads_get_different_tokens(self):
        """Токен случайный на каждый вызов - не детерминирован по имени файла."""
        p1 = project_file_upload_path(_FakeInstance(1), 'notes.txt')
        p2 = project_file_upload_path(_FakeInstance(1), 'notes.txt')
        self.assertNotEqual(p1, p2)

    def test_original_filename_preserved_as_suffix(self):
        """Расширение/имя файла сохраняются - только с непредсказуемым префиксом,
        не ломает определение типа файла и UX (видно оригинальное имя)."""
        path = project_file_upload_path(_FakeInstance(7), 'Бюджет 2026.xlsx')
        self.assertTrue(path.endswith('_Бюджет 2026.xlsx'))
