# Migration ESCRITA À MÃO (padrão do pacote videos-avatar).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_organization_creditos_videos_avatar'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='look_creation_enabled',
            field=models.BooleanField(
                default=False,
                help_text='Cliente pode criar novos looks (visuais) para os '
                          'avatares da org — por prompt ou imagem. Liberado '
                          'pela equipe.',
                verbose_name='Criação de Looks Habilitada'),
        ),
    ]
