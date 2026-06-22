from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0020_collaborators'),
    ]

    operations = [
        migrations.AddField(
            model_name='projectcommit',
            name='kind',
            field=models.CharField(
                choices=[('commit', 'Коммит'), ('pull_request', 'Pull Request')],
                default='commit', max_length=14, verbose_name='Тип',
            ),
        ),
        migrations.AddField(
            model_name='projectcommit',
            name='pr_branch',
            field=models.CharField(blank=True, max_length=200, verbose_name='Ветка PR'),
        ),
        migrations.AddField(
            model_name='projectcommit',
            name='pr_url',
            field=models.URLField(blank=True, verbose_name='URL Pull Request'),
        ),
    ]
