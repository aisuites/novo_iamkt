# Migration ESCRITA À MÃO (padrão adotado no pacote videos-avatar para não
# arrastar drift de makemigrations). Créditos do pacote Vídeos Avatar.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_organization_archetype_two_step'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='video_avatar_credits',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Vídeos avatar restantes do pacote (decrementa a cada '
                          'vídeo; 0 = bloqueado). Vídeo que falha devolve o crédito.',
                verbose_name='Créditos de Vídeo Avatar'),
        ),
        migrations.AddField(
            model_name='organization',
            name='avatar_creation_credits',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Criações de avatar (setup/digital twin) restantes. '
                          '0 = recurso oculto para o cliente.',
                verbose_name='Créditos de Criação de Avatar'),
        ),
    ]
