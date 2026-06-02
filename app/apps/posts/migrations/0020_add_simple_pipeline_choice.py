from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('posts', '0019_post_copy_payload_post_designer_payload_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='post',
            name='pipeline_used',
            field=models.CharField(
                choices=[
                    ('n8n', 'N8N (workflow externo)'),
                    ('local', 'Local (Celery interno)'),
                    ('simple', 'Simples (Celery + OpenAI, 1 agente)'),
                ],
                default='n8n',
                help_text='Qual pipeline foi acionado: N8N externo (producao) ou Celery local (homol)',
                max_length=10,
                verbose_name='Pipeline usada',
            ),
        ),
    ]
