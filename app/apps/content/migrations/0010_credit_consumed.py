# Migration ESCRITA À MÃO (padrão do pacote videos-avatar).
# Marca se o registro consumiu crédito — refund só devolve o que consumiu.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0009_heygenavatar_criacao_twin'),
    ]

    operations = [
        migrations.AddField(
            model_name='videoavatar',
            name='credit_consumed',
            field=models.BooleanField(
                default=False,
                help_text='Consumiu 1 crédito do pacote na criação (falha '
                          'definitiva devolve apenas se True)',
                verbose_name='Crédito Consumido'),
        ),
        migrations.AddField(
            model_name='heygenavatar',
            name='credit_consumed',
            field=models.BooleanField(
                default=False,
                help_text='Consumiu 1 crédito de setup na criação',
                verbose_name='Crédito Consumido'),
        ),
    ]
