# Adiciona 'thermomix' aos choices de pipeline_used (METADATA apenas — nenhuma
# mudanca de schema no banco; espelha a 0024 que fez o mesmo p/ todxs/vb/samsung).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('posts', '0024_alter_post_pipeline_used'),
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
                    ('todxs', 'TODXS (arquetipos, render deterministico)'),
                    ('vb', 'VB Gastronomia (arquetipos, render deterministico)'),
                    ('samsung', 'Samsung Healthcare (arquetipos, render deterministico)'),
                    ('thermomix', 'Thermomix (arquetipos, engine v3)'),
                ],
                default='n8n',
                help_text='Qual pipeline foi acionado: N8N externo, Celery local ou pipeline de arte da org',
                max_length=10,
                verbose_name='Pipeline usada',
            ),
        ),
    ]
