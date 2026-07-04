from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0049_neuralnetwork_provider_openrouter_free'),
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
                    ('zai_free', 'Z.ai (бесплатные модели GLM-*-Flash)'),
                ],
                default='openrouter',
                max_length=20,
                verbose_name='Провайдер',
            ),
        ),
    ]
