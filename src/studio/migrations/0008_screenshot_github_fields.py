from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0007_studioproject_forked_from'),
    ]

    operations = [
        migrations.AddField(
            model_name='studioproject',
            name='screenshot',
            field=models.ImageField(blank=True, null=True, upload_to='studio/screenshots/'),
        ),
        migrations.AddField(
            model_name='studioproject',
            name='github_repo_url',
            field=models.CharField(blank=True, max_length=500),
        ),
    ]
