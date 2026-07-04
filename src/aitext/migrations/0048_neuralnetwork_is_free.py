from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0047_unified_memory_recall_research'),
    ]

    operations = [
        migrations.AddField(
            model_name='neuralnetwork',
            name='is_free',
            field=models.BooleanField(
                default=False,
                help_text='Показывать только во вкладке «Бесплатные» (скрыта из общего каталога). '
                          'Бесплатна для всех пользователей в пределах дневного лимита (messages_limit). '
                          'Обычно провайдер = Groq, стоимость = 0.',
                verbose_name='Бесплатная модель',
            ),
        ),
        migrations.AlterField(
            model_name='neuralnetwork',
            name='provider',
            field=models.CharField(
                choices=[
                    ('openrouter', 'laozhang.ai (текст)'),
                    ('fal-ai', 'laozhang.ai (изображения/видео)'),
                    ('groq', 'Groq (бесплатные текстовые модели)'),
                ],
                default='openrouter',
                max_length=20,
                verbose_name='Провайдер',
            ),
        ),
    ]
