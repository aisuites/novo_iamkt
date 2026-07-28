# Migration ESCRITA À MÃO (evita re-detectar o drift antigo do content —
# ver notas nas migrations 0006/0007). Campos da criação de digital twin
# via iamkt (footage → HeyGen → treino async).

import apps.core.storage
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('content', '0008_videoavatar_voice_speed_aspect_ratio'),
    ]

    operations = [
        migrations.AlterField(
            model_name='heygenavatar',
            name='voice_id',
            field=models.CharField(
                blank=True, max_length=64,
                help_text='Voz pt-BR da HeyGen — no twin criado via iamkt vem '
                          'sozinha do treino (default_voice_id do look)',
                verbose_name='Voice ID (HeyGen)'),
        ),
        migrations.AddField(
            model_name='heygenavatar',
            name='status',
            field=models.CharField(
                max_length=12, default='ready',
                choices=[('pending', 'Enviando'), ('training', 'Treinando'),
                         ('ready', 'Pronto'), ('failed', 'Falhou')],
                help_text='ready = cadastro manual ou treino concluído; '
                          'pending/training = criação via iamkt em andamento',
                verbose_name='Status'),
        ),
        migrations.AddField(
            model_name='heygenavatar',
            name='source_video',
            field=models.FileField(
                blank=True, null=True, upload_to='footage/%Y/%m/',
                storage=apps.core.storage.VideoAvatarStorage(),
                help_text='Footage enviado pelo cliente (gravação ou upload) — '
                          'vira o twin',
                verbose_name='Vídeo de Origem'),
        ),
        migrations.AddField(
            model_name='heygenavatar',
            name='heygen_asset_id',
            field=models.CharField(blank=True, max_length=64,
                                   verbose_name='Asset ID (HeyGen)'),
        ),
        migrations.AddField(
            model_name='heygenavatar',
            name='error_message',
            field=models.TextField(blank=True, verbose_name='Erro'),
        ),
        migrations.AddField(
            model_name='heygenavatar',
            name='created_by',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='heygen_avatars_created',
                to=settings.AUTH_USER_MODEL, verbose_name='Criado por'),
        ),
        migrations.AddField(
            model_name='heygenavatar',
            name='trained_at',
            field=models.DateTimeField(blank=True, null=True,
                                       verbose_name='Treino concluído em'),
        ),
    ]
