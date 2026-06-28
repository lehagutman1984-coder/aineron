from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0040_generatedimage_progress'),
    ]

    operations = [
        migrations.AddField(
            model_name='generatedimage',
            name='is_public',
            field=models.BooleanField(default=False, verbose_name='Публичное (в галерее)'),
        ),
        migrations.AddField(
            model_name='generatedimage',
            name='share_slug',
            field=models.CharField(
                blank=True, max_length=12, null=True, unique=True,
                verbose_name='Slug для шеринга',
            ),
        ),
    ]
