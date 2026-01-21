"""
Comando Django para resetar flag de primeira visita
Uso: python manage.py reset_welcome <username>
"""
from django.core.management.base import BaseCommand
from django.contrib.sessions.models import Session
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = 'Reseta a flag de primeira visita para um usuário (para testes do modal de boas-vindas)'

    def add_arguments(self, parser):
        parser.add_argument(
            'username',
            type=str,
            help='Username ou email do usuário'
        )

    def handle(self, *args, **options):
        User = get_user_model()
        username = options['username']
        
        try:
            # Buscar usuário
            user = User.objects.get(username=username)
            
            # Limpar todas as sessões do usuário
            deleted_count = 0
            for session in Session.objects.all():
                data = session.get_decoded()
                if data.get('_auth_user_id') == str(user.id):
                    session.delete()
                    deleted_count += 1
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Sessões limpas para {user.username} ({deleted_count} sessão(ões))'
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    'ℹ️  Faça login novamente para ver o modal de boas-vindas'
                )
            )
            
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'❌ Usuário "{username}" não encontrado')
            )
