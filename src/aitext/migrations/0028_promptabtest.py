from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """A/B prompt testing model for per-network system prompt experiments."""

    dependencies = [
        ("aitext", "0027_usageevent"),
    ]

    operations = [
        migrations.CreateModel(
            name="PromptABTest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, verbose_name="Название теста")),
                ("network", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="ab_tests",
                    to="aitext.neuralnetwork",
                    verbose_name="Нейросеть",
                )),
                ("prompt_a", models.TextField(verbose_name="Вариант A (контроль)")),
                ("prompt_b", models.TextField(verbose_name="Вариант B (тест)")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активен")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("sends_a", models.PositiveIntegerField(default=0)),
                ("sends_b", models.PositiveIntegerField(default=0)),
            ],
            options={
                "verbose_name": "A/B тест промтов",
                "verbose_name_plural": "A/B тесты промтов",
                "ordering": ["-created_at"],
            },
        ),
    ]
