from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='StudioTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(unique=True)),
                ('name', models.CharField(max_length=120)),
                ('description', models.TextField()),
                ('stack', models.CharField(
                    choices=[('nextjs', 'Next.js'), ('react', 'React'), ('vue', 'Vue'), ('html', 'HTML')],
                    default='nextjs',
                    max_length=10,
                )),
                ('preview_image', models.CharField(blank=True, max_length=300)),
                ('seed_prompt', models.TextField()),
                ('order', models.IntegerField(default=0)),
            ],
            options={
                'ordering': ['order'],
            },
        ),
    ]
