"""
Sincroniza os looks dos apresentadores HeyGen de uma org (ou de todas).

Uso:
  python manage.py heygen_sync --org iamkt            # uma org
  python manage.py heygen_sync --all                  # todas com apresentador
  python manage.py heygen_sync --org iamkt --activate # looks novos já ativos

Looks novos entram INATIVOS por padrão (curadoria no admin). Looks que
sumiram do grupo na HeyGen são desativados, nunca deletados.
Mesma lógica da ação "Sincronizar looks da HeyGen" no admin.
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Puxa os looks novos dos avatar groups da HeyGen para o catálogo'

    def add_arguments(self, parser):
        parser.add_argument('--org', help='Slug da organização')
        parser.add_argument('--all', action='store_true',
                            help='Todas as orgs com apresentador cadastrado')
        parser.add_argument('--activate', action='store_true',
                            help='Looks novos entram ativos (pula a curadoria)')

    def handle(self, *args, **opts):
        from apps.content.models import HeygenAvatar
        from apps.content.services import heygen

        if opts['org']:
            avatars = HeygenAvatar.objects.filter(organization__slug=opts['org'])
        elif opts['all']:
            avatars = HeygenAvatar.objects.all()
        else:
            raise CommandError('Use --org <slug> ou --all')

        avatars = avatars.exclude(group_id='').select_related('organization')
        if not avatars:
            raise CommandError('Nenhum apresentador com group_id encontrado')

        for avatar in avatars:
            try:
                r = heygen.sync_group_looks(avatar, activate_new=opts['activate'])
            except heygen.HeygenError as e:
                self.stderr.write(self.style.ERROR(
                    f'{avatar.organization.slug}/{avatar.name}: {e}'))
                continue
            self.stdout.write(self.style.SUCCESS(
                f'{avatar.organization.slug}/{avatar.name}: '
                f'{r["created"]} novos{"" if opts["activate"] else " (inativos)"}, '
                f'{r["deactivated"]} desativados, {r["remote_total"]} no grupo'))
