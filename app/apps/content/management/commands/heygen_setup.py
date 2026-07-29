"""
Ferramenta da EQUIPE INTERNA para montar o catálogo HeygenAvatar de uma org.

Uso:
  # 1. Descobrir o que existe na conta HeyGen (só leitura):
  python manage.py heygen_setup --list-avatars
  python manage.py heygen_setup --list-looks [--group <group_id>]
  python manage.py heygen_setup --list-voices

  # 2. Cadastrar um APRESENTADOR para uma org (por GROUP, não por look) —
  #    já sincroniza os looks do grupo (entram inativos, ative no admin):
  python manage.py heygen_setup --org thermomix --name "Apresentadora" \
      --group-id 6816bb70... --voice-id v_123 [--engine avatar_v]

  # 3. Re-sincronizar looks depois (ou use a ação no admin):
  python manage.py heygen_sync --org thermomix

Também serve de smoke test da HEYGEN_API_KEY.
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Lista avatares/looks/vozes da conta HeyGen e cadastra HeygenAvatar por org'

    def add_arguments(self, parser):
        parser.add_argument('--list-avatars', action='store_true')
        parser.add_argument('--list-looks', action='store_true')
        parser.add_argument('--group', help='Filtrar looks por avatar group')
        parser.add_argument('--list-voices', action='store_true')
        parser.add_argument('--language', default='Portuguese',
                            help='Idioma do filtro de vozes (default: Portuguese)')
        parser.add_argument('--org', help='Slug da organização')
        parser.add_argument('--name', help='Nome de exibição do apresentador')
        parser.add_argument('--group-id', help='ID do avatar GROUP na HeyGen')
        parser.add_argument('--voice-id')
        parser.add_argument('--engine', default='avatar_iv',
                            choices=['avatar_iv', 'avatar_v'])

    def handle(self, *args, **opts):
        from apps.content.services import heygen

        if opts['list_avatars']:
            for group in heygen.list_avatar_groups():
                self.stdout.write(f"  {group.get('id')}  {group.get('name', '?')}")
            return

        if opts['list_looks']:
            for look in heygen.list_looks(opts.get('group')):
                engines = ','.join(look.get('supported_api_engines', []) or [])
                self.stdout.write(
                    f"  {look.get('id')}  {look.get('name', '?')}  "
                    f"[{look.get('avatar_type', '?')}]  engines: {engines or '?'}")
            return

        if opts['list_voices']:
            for voice in heygen.list_voices(opts['language']):
                self.stdout.write(
                    f"  {voice.get('id') or voice.get('voice_id')}  "
                    f"{voice.get('name', '?')}  [{voice.get('gender', '?')}]  "
                    f"{voice.get('language', '')}")
            return

        # cadastro do apresentador (por GROUP) + sync dos looks
        required = ['org', 'name', 'group_id', 'voice_id']
        if not all(opts.get(k) for k in required):
            raise CommandError('Para cadastrar: --org --name --group-id --voice-id '
                               '(ou use --list-avatars / --list-looks / --list-voices)')

        from apps.core.models import Organization
        from apps.content.models import HeygenAvatar

        try:
            org = Organization.objects.get(slug=opts['org'])
        except Organization.DoesNotExist:
            raise CommandError(f"Organização '{opts['org']}' não encontrada")

        # valida o grupo AGORA (pega ID errado antes do primeiro render)
        remote_looks = heygen.list_looks(opts['group_id'])
        if not remote_looks:
            raise CommandError(
                f"Grupo {opts['group_id']} sem looks na HeyGen — confira o ID "
                "(é o GROUP, não o look) e se o treino terminou")

        avatar, created = HeygenAvatar.objects.update_or_create(
            organization=org,
            group_id=opts['group_id'],
            defaults={
                'name': opts['name'],
                'voice_id': opts['voice_id'],
                'engine': opts['engine'],
                'is_active': True,
            },
        )
        verb = 'criado' if created else 'atualizado'
        self.stdout.write(self.style.SUCCESS(
            f'Apresentador #{avatar.pk} {verb}: "{avatar.name}" para {org.name} '
            f'(group={avatar.group_id}, voice={avatar.voice_id})'))

        r = heygen.sync_group_looks(avatar)
        self.stdout.write(self.style.SUCCESS(
            f'Looks sincronizados: {r["created"]} novos (INATIVOS), '
            f'{r["remote_total"]} no grupo. Ative os liberados no admin.'))
