from django.db import migrations, models


class Migration(migrations.Migration):
    """Sprint 6.5 fix: chunk_index must be IntegerField (allows -1 for summary embeddings)."""

    dependencies = [
        ('aitext', '0024_connector_deploy'),
    ]

    operations = [
        migrations.AlterField(
            model_name='projectchunk',
            name='chunk_index',
            field=models.IntegerField(),
        ),
    ]
