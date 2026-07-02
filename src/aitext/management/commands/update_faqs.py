"""
Обновляет FAQ: заменяет «Нейросети.com» на aineron.ru и заменяет
устаревшие записи актуальными вопросами для платформы aineron.ru.
"""
from django.core.management.base import BaseCommand
from aitext.models import FAQ


GLOBAL_FAQS = [
    {
        "question": "Что такое aineron.ru?",
        "answer": (
            "aineron.ru — российский SaaS-сервис для доступа к лучшим AI-нейросетям без VPN. "
            "Вы общаетесь с GPT-4o, Claude, Gemini, DeepSeek, Flux и другими моделями прямо "
            "в браузере, оплачивая рублями без иностранных карт."
        ),
        "order": 1,
    },
    {
        "question": "Как работает оплата и подписка на платформе?",
        "answer": (
            "Вы пополняете баланс в рублях и платите только за отправленные сообщения: "
            "каждое сообщение к нейросети стоит 1–5 ₽ в зависимости от модели. Средства "
            "не сгорают и не ограничены по времени. Подписка пополняет баланс "
            "и открывает безлимитный доступ к базовым моделям."
        ),
        "order": 2,
    },
    {
        "question": "Нужен ли VPN для использования сервиса?",
        "answer": (
            "Нет. aineron.ru — российский сервис с серверами в России. "
            "Доступ без VPN, оплата картами РФ (Visa / MasterCard / Мир, ЮMoney, СБП), "
            "работает в любом браузере."
        ),
        "order": 3,
    },
    {
        "question": "На каких языках я могу делать запрос в нейросеть?",
        "answer": (
            "На любом языке. Все модели принимают русскоязычные запросы. "
            "Для моделей генерации изображений автоматически включается перевод промта "
            "на английский — вы пишете по-русски, модель получает оптимальный запрос."
        ),
        "order": 4,
    },
    {
        "question": "Есть ли бесплатный доступ?",
        "answer": (
            "Да. Новым пользователям начисляется стартовый баланс 10 ₽, которого хватает "
            "на первые сообщения без оплаты. Некоторые модели также имеют бесплатный дневной "
            "лимит сообщений."
        ),
        "order": 5,
    },
    {
        "question": "Каким образом оформить платный доступ?",
        "answer": (
            "Перейдите в «Кабинет» → «Пополнение». Доступно пополнение баланса на любую сумму "
            "или подписки со скидкой. Принимаем карты Visa / MasterCard / Мир, ЮMoney, СБП. "
            "Для юридических лиц — счёт и договор."
        ),
        "order": 6,
    },
    {
        "question": "Есть ли API для разработчиков?",
        "answer": (
            "Да. API совместим с OpenAI SDK — смените base_url на aineron.ru/api/v1/ "
            "и добавьте свой ключ. Работает с Cursor, VS Code (Continue), и любым "
            "OpenAI-совместимым приложением. Ключи доступны в «Кабинет» → «API-ключи»."
        ),
        "order": 7,
    },
]


class Command(BaseCommand):
    help = "Обновляет глобальные FAQ: убирает Нейросети.com, добавляет актуальный контент aineron.ru"

    def handle(self, *args, **options):
        # 1. Точечная замена во всех существующих записях
        replaced = 0
        for faq in FAQ.objects.filter(question__icontains="Нейросети.com"):
            faq.question = faq.question.replace("Нейросети.com", "aineron.ru")
            faq.answer = faq.answer.replace("Нейросети.com", "aineron.ru")
            faq.save(update_fields=["question", "answer"])
            replaced += 1
            self.stdout.write(f"  Обновлён: {faq.question[:60]}")

        for faq in FAQ.objects.filter(answer__icontains="Нейросети.com"):
            faq.answer = faq.answer.replace("Нейросети.com", "aineron.ru")
            faq.save(update_fields=["answer"])
            replaced += 1

        self.stdout.write(self.style.SUCCESS(f"Замена в существующих FAQ: {replaced} записей"))

        # 2. Удалить глобальные FAQ (show_everywhere=True или show_on_main=True, без привязки к модели)
        deleted, _ = FAQ.objects.filter(
            neural_network__isnull=True,
            show_everywhere=True,
        ).delete()
        self.stdout.write(f"Удалено устаревших глобальных FAQ: {deleted}")

        # 3. Создать актуальные глобальные FAQ
        for item in GLOBAL_FAQS:
            FAQ.objects.create(
                question=item["question"],
                answer=item["answer"],
                show_everywhere=True,
                show_on_main=False,
                order=item["order"],
            )

        self.stdout.write(
            self.style.SUCCESS(f"Создано {len(GLOBAL_FAQS)} актуальных глобальных FAQ для aineron.ru")
        )
