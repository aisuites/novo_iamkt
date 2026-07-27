"""
Ferramenta da EQUIPE INTERNA para montar o catálogo HeygenAvatar de uma org.

Uso:
  # 1. Descobrir o que existe na conta HeyGen (só leitura):
  python manage.py heygen_setup --list-avatars
  python manage.py heygen_setup --list-looks [--group <group_id>]
  python manage.py heygen_setup --list-voices

  # 2. Cadastrar um avatar para uma org (valida o look na API antes):
  python manage.py heygen_setup --org thermomix --name "Apresentadora" \
      --look-id lk_abc123 --voice-id v_123 [--engine avatar_v] [--default]

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
        parser.add_argument('--name', help='Nome de exibição do avatar')
        parser.add_argument('--look-id')
        parser.add_argument('--voice-id')
        parser.add_argument('--engine', default='avatar_iv',
                            choices=['avatar_iv', 'avatar_v'])
        parser.add_argument('--default', action='store_true',
                            help='Marca como avatar padrão da org')

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

        # cadastro
        required = ['org', 'name', 'look_id', 'voice_id']
        if not all(opts.get(k) for k in required):
            raise CommandError('Para cadastrar: --org --name --look-id --voice-id '
                               '(ou use --list-avatars / --list-looks / --list-voices)')

        from apps.core.models import Organization
        from apps.content.models import HeygenAvatar

        try:
            org = Organization.objects.get(slug=opts['org'])
        except Organization.DoesNotExist:
            raise CommandError(f"Organização '{opts['org']}' não encontrada")

        # valida o look na API (pega avatar_not_found e engine incompatível AGORA,
        # não no primeiro render do cliente)
        look = heygen.get_look(opts['look_id'])
        supported = look.get('supported_api_engines') or []
        if supported and opts['engine'] not in supported:
            raise CommandError(
                f"Look {opts['look_id']} não suporta engine {opts['engine']} "
                f"(suportados: {', '.join(supported)})")

        avatar, created = HeygenAvatar.objects.update_or_create(
            organization=org,
            look_id=opts['look_id'],
            defaults={
                'name': opts['name'],
                'voice_id': opts['voice_id'],
                'engine': opts['engine'],
                'is_default': opts['default'],
                'is_active': True,
            },
        )
        if opts['default']:
            HeygenAvatar.objects.filter(organization=org).exclude(
                pk=avatar.pk).update(is_default=False)

        verb = 'criado' if created else 'atualizado'
        self.stdout.write(self.style.SUCCESS(
            f'HeygenAvatar #{avatar.pk} {verb}: "{avatar.name}" para {org.name} '
            f'(look={avatar.look_id}, voice={avatar.voice_id}, engine={avatar.engine})'))
        self.stdout.write('Lembre de subir a preview_image pelo admin para o seletor.')
