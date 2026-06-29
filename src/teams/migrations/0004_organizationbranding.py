from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('teams', '0003_org_seats'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrganizationBranding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('subdomain', models.SlugField(max_length=63, unique=True, verbose_name='Субдомен')),
                ('custom_domain', models.CharField(blank=True, max_length=253, verbose_name='Кастомный домен')),
                ('logo_url', models.URLField(blank=True, verbose_name='URL логотипа')),
                ('primary_color', models.CharField(default='#f0a38a', max_length=7, verbose_name='Основной цвет')),
                ('company_name', models.CharField(blank=True, max_length=100, verbose_name='Название компании')),
                ('support_email', models.EmailField(blank=True, verbose_name='Email поддержки')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активен')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('organization', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='branding', to='teams.organization')),
            ],
            options={
                'verbose_name': 'Брендинг организации',
                'verbose_name_plural': 'Брендинг организаций',
            },
        ),
    ]
