from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('posts', '0020_add_simple_pipeline_choice'),
    ]

    operations = [
        migrations.AlterField(
            model_name='post',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pendente de Aprovação'),
                    ('generating', 'Agente Gerando Conteúdo'),
                    ('image_generating', 'Agente Gerando Imagem'),
                    ('image_ready', 'Imagem Disponível'),
                    ('approved', 'Aprovado'),
                    ('agent', 'Agente Alterando — Aguarde'),
                    ('rejected', 'Rejeitado'),
                    ('failed', 'Falhou'),
                ],
                default='pending',
                max_length=20,
                verbose_name='Status',
            ),
        ),
    ]
