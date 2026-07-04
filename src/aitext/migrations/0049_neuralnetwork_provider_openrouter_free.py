from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0048_neuralnetwork_is_free'),
    ]

    operations = [
        migrations.AlterField(
            model_name='neuralnetwork',
            name='provider',
            field=models.CharField(
                choices=[
                    ('openrouter', 'laozhang.ai (текст)'),
                    ('fal-ai', 'laozhang.ai (изображения/видео)'),
                    ('groq', 'Groq (бесплатные текстовые модели, заблокирован из РФ)'),
                    ('openrouter_free', 'OpenRouter (бесплатные текстовые модели :free)'),
                ],
                default='openrouter',
                max_length=20,
                verbose_name='Провайдер',
            ),
        ),
    ]
