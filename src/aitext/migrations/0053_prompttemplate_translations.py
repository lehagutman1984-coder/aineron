# Hand-authored to match modeltranslation's convention, see
# 0052_category_name_en_category_name_ru_faq_answer_en_and_more.py

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('aitext', '0052_category_name_en_category_name_ru_faq_answer_en_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='prompttemplate',
            name='content_en',
            field=models.TextField(null=True, verbose_name='Текст промта'),
        ),
        migrations.AddField(
            model_name='prompttemplate',
            name='content_ru',
            field=models.TextField(null=True, verbose_name='Текст промта'),
        ),
        migrations.AddField(
            model_name='prompttemplate',
            name='title_en',
            field=models.CharField(max_length=100, null=True, verbose_name='Название'),
        ),
        migrations.AddField(
            model_name='prompttemplate',
            name='title_ru',
            field=models.CharField(max_length=100, null=True, verbose_name='Название'),
        ),
    ]
