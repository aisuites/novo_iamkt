# Migration ESCRITA À MÃO (evita re-detectar o drift antigo do content
# no makemigrations — ver notas nas migrations 0006/0007).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0007_heygenlook_remove_post_area_remove_post_organization_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='videoavatar',
            name='voice_speed',
            field=models.FloatField(
                default=1.0,
                help_text='Velocidade da fala (0.5–2.0); vai em voice_settings.speed',
                verbose_name='Velocidade da Fala',
            ),
        ),
        migrations.AddField(
            model_name='videoavatar',
            name='aspect_ratio',
            field=models.CharField(
                max_length=8,
                default='auto',
                choices=[('auto', 'Automático (segue o look)'),
                         ('9:16', 'Vertical 9:16'),
                         ('16:9', 'Horizontal 16:9'),
                         ('1:1', 'Quadrado 1:1')],
                help_text='Formato do vídeo enviado à HeyGen',
                verbose_name='Formato',
            ),
        ),
        migrations.AlterField(
            model_name='videoavatar',
            name='avatar_action',
            field=models.CharField(
                blank=True,
                help_text="Direção de atuação enviada como motion_prompt (Avatar IV): "
                          "'fale gesticulando', 'tom animado', 'sorria no final'...",
                max_length=200,
                verbose_name='Gestos / Atuação',
            ),
        ),
    ]
