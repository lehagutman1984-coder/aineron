from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0005_studiocollaborator'),
    ]

    operations = [
        migrations.AlterField(
            model_name='studiocollaborator',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
    ]
