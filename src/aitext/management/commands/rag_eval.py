"""U6 (UNIFIED_SUPREMACY) — eval-suite качества RAG.

Golden-set: JSON-файл [{"query": "...", "expected_files": ["substr1", ...]}] —
для каждого запроса перечислены подстроки имён файлов, которые ДОЛЖНЫ попасть
в top-k выдачи hybrid_search. Метрики: recall@k (доля запросов, где найден
хотя бы один ожидаемый файл) и MRR (средний обратный ранг первого попадания).

Запуск:
  python manage.py rag_eval --project <id> --golden path/to/golden.json [--top-k 15]

Порог качества: recall@15 >= 0.85 — не должен падать между релизами
(запускать при изменении retrieval-кода). Шаблон: aitext/eval/golden_example.json
"""
import json

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Считает recall@k и MRR гибридного RAG по golden-set'

    def add_arguments(self, parser):
        parser.add_argument('--project', type=int, required=True,
                            help='ID проекта с проиндексированной базой знаний')
        parser.add_argument('--golden', type=str, required=True,
                            help='Путь к golden-set JSON')
        parser.add_argument('--top-k', type=int, default=15)

    def handle(self, *args, **options):
        from aitext.models import Project
        from aitext.search import hybrid_search

        project = Project.objects.filter(pk=options['project']).first()
        if project is None:
            raise CommandError(f'Проект {options["project"]} не найден')

        try:
            with open(options['golden'], encoding='utf-8') as f:
                golden = json.load(f)
        except Exception as e:
            raise CommandError(f'Не удалось прочитать golden-set: {e}')
        if not isinstance(golden, list) or not golden:
            raise CommandError('Golden-set пуст или не является списком')

        top_k = options['top_k']
        hits = 0
        rr_sum = 0.0
        failures = []

        for case in golden:
            query = case.get('query', '')
            expected = [e.lower() for e in case.get('expected_files', [])]
            if not query or not expected:
                continue
            try:
                chunks = hybrid_search(project, [query], top_k=top_k)
            except Exception as e:
                failures.append((query, f'ошибка поиска: {e}'))
                continue

            found_rank = None
            seen_files = []
            for rank, c in enumerate(chunks, 1):
                fname = str(c.get('filename', '')).lower()
                if fname not in seen_files:
                    seen_files.append(fname)
                if found_rank is None and any(exp in fname for exp in expected):
                    found_rank = rank
            if found_rank is not None:
                hits += 1
                rr_sum += 1.0 / found_rank
            else:
                failures.append((query, f'ожидалось {expected}, '
                                        f'найдено {seen_files[:5]}'))

        total = hits + len(failures)
        if total == 0:
            raise CommandError('Ни одного валидного кейса в golden-set')
        recall = hits / total
        mrr = rr_sum / total

        self.stdout.write(f'\nRAG eval — проект «{project.name}», top_k={top_k}')
        self.stdout.write(f'  Кейсов:     {total}')
        self.stdout.write(f'  recall@{top_k}: {recall:.3f}  (порог 0.85)')
        self.stdout.write(f'  MRR:        {mrr:.3f}')

        if failures:
            self.stdout.write(self.style.WARNING(f'\nПромахи ({len(failures)}):'))
            for query, why in failures[:10]:
                self.stdout.write(f'  - «{query[:60]}» — {why[:120]}')

        if recall < 0.85:
            self.stdout.write(self.style.ERROR('\nFAIL: recall ниже порога 0.85'))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS('\nPASS'))
