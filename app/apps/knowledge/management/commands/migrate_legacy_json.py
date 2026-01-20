"""
Comando Django para migrar dados JSON legados para models relacionados
Usage: python manage.py migrate_legacy_json
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.knowledge.models import KnowledgeBase, ColorPalette, CustomFont, SocialNetwork


class Command(BaseCommand):
    help = 'Migra dados JSON legados (paleta_cores, tipografia, redes_sociais) para models relacionados'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula a migração sem salvar no banco',
        )
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Remove dados existentes nos models relacionados antes de migrar',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        clear_existing = options['clear_existing']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 Modo DRY-RUN ativado - nenhuma alteração será salva'))
        
        try:
            kb = KnowledgeBase.get_instance()
        except KnowledgeBase.DoesNotExist:
            self.stdout.write(self.style.ERROR('❌ Base de Conhecimento não encontrada'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'✅ Base de Conhecimento encontrada: {kb.nome_empresa}'))
        self.stdout.write('')
        
        # Estatísticas
        stats = {
            'cores_migradas': 0,
            'fontes_migradas': 0,
            'redes_migradas': 0,
            'erros': []
        }
        
        if not dry_run:
            with transaction.atomic():
                # Migrar cores
                stats['cores_migradas'] = self._migrate_colors(kb, clear_existing)
                
                # Migrar fontes
                stats['fontes_migradas'] = self._migrate_fonts(kb, clear_existing)
                
                # Migrar redes sociais
                stats['redes_migradas'] = self._migrate_social_networks(kb, clear_existing)
        else:
            # Simular migração
            stats['cores_migradas'] = self._simulate_colors_migration(kb)
            stats['fontes_migradas'] = self._simulate_fonts_migration(kb)
            stats['redes_migradas'] = self._simulate_social_networks_migration(kb)
        
        # Mostrar resultados
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('📊 RESUMO DA MIGRAÇÃO:'))
        self.stdout.write(f'  🎨 Cores migradas: {stats["cores_migradas"]}')
        self.stdout.write(f'  🔤 Fontes migradas: {stats["fontes_migradas"]}')
        self.stdout.write(f'  📱 Redes sociais migradas: {stats["redes_migradas"]}')
        
        if stats['erros']:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('⚠️  ERROS ENCONTRADOS:'))
            for erro in stats['erros']:
                self.stdout.write(f'  - {erro}')
        
        if not dry_run:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('✅ Migração concluída com sucesso!'))
            self.stdout.write(self.style.WARNING('💡 Dica: Você pode agora remover os campos JSON legados em uma migration futura'))
        else:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('💡 Execute sem --dry-run para aplicar as mudanças'))

    def _migrate_colors(self, kb, clear_existing):
        """Migra paleta_cores JSON para ColorPalette model"""
        if clear_existing:
            deleted = kb.colors.all().delete()
            self.stdout.write(f'  🗑️  Removidos {deleted[0]} cores existentes')
        
        if not kb.paleta_cores or not isinstance(kb.paleta_cores, dict):
            self.stdout.write('  ℹ️  Nenhuma cor no JSON legado para migrar')
            return 0
        
        count = 0
        for index, (nome, hex_code) in enumerate(kb.paleta_cores.items()):
            if hex_code and hex_code.startswith('#'):
                ColorPalette.objects.create(
                    knowledge_base=kb,
                    name=nome.capitalize(),
                    hex_code=hex_code.upper(),
                    color_type='primary',
                    order=index
                )
                count += 1
                self.stdout.write(f'    ✓ Cor migrada: {nome} ({hex_code})')
        
        return count

    def _migrate_fonts(self, kb, clear_existing):
        """Migra tipografia JSON para CustomFont model"""
        if clear_existing:
            deleted = kb.custom_fonts.all().delete()
            self.stdout.write(f'  🗑️  Removidas {deleted[0]} fontes existentes')
        
        if not kb.tipografia or not isinstance(kb.tipografia, dict):
            self.stdout.write('  ℹ️  Nenhuma fonte no JSON legado para migrar')
            return 0
        
        font_type_map = {
            'titulo': 'titulo',
            'subtitulo': 'corpo',
            'corpo': 'corpo',
            'texto': 'corpo',
            'botao': 'destaque',
            'destaque': 'destaque'
        }
        
        count = 0
        for uso, nome_fonte in kb.tipografia.items():
            if nome_fonte:
                font_type = font_type_map.get(uso.lower(), 'corpo')
                CustomFont.objects.create(
                    knowledge_base=kb,
                    name=nome_fonte,
                    font_type=font_type,
                    s3_key=f'google-fonts/{nome_fonte.replace(" ", "-").lower()}',
                    s3_url=f'https://fonts.googleapis.com/css2?family={nome_fonte.replace(" ", "+")}',
                    file_format='woff2'
                )
                count += 1
                self.stdout.write(f'    ✓ Fonte migrada: {nome_fonte} ({uso})')
        
        return count

    def _migrate_social_networks(self, kb, clear_existing):
        """Migra redes_sociais JSON para SocialNetwork model"""
        if clear_existing:
            deleted = kb.social_networks.all().delete()
            self.stdout.write(f'  🗑️  Removidas {deleted[0]} redes sociais existentes')
        
        if not kb.redes_sociais or not isinstance(kb.redes_sociais, dict):
            self.stdout.write('  ℹ️  Nenhuma rede social no JSON legado para migrar')
            return 0
        
        count = 0
        for network_type, url in kb.redes_sociais.items():
            if url:
                SocialNetwork.objects.update_or_create(
                    knowledge_base=kb,
                    network_type=network_type.lower(),
                    defaults={
                        'name': network_type.capitalize(),
                        'url': url,
                        'is_active': True
                    }
                )
                count += 1
                self.stdout.write(f'    ✓ Rede social migrada: {network_type} ({url})')
        
        return count

    def _simulate_colors_migration(self, kb):
        """Simula migração de cores"""
        self.stdout.write('🎨 SIMULANDO MIGRAÇÃO DE CORES:')
        
        if not kb.paleta_cores or not isinstance(kb.paleta_cores, dict):
            self.stdout.write('  ℹ️  Nenhuma cor no JSON legado')
            return 0
        
        count = 0
        for nome, hex_code in kb.paleta_cores.items():
            if hex_code and hex_code.startswith('#'):
                self.stdout.write(f'  → Seria criada: {nome} ({hex_code})')
                count += 1
        
        return count

    def _simulate_fonts_migration(self, kb):
        """Simula migração de fontes"""
        self.stdout.write('')
        self.stdout.write('🔤 SIMULANDO MIGRAÇÃO DE FONTES:')
        
        if not kb.tipografia or not isinstance(kb.tipografia, dict):
            self.stdout.write('  ℹ️  Nenhuma fonte no JSON legado')
            return 0
        
        count = 0
        for uso, nome_fonte in kb.tipografia.items():
            if nome_fonte:
                self.stdout.write(f'  → Seria criada: {nome_fonte} ({uso})')
                count += 1
        
        return count

    def _simulate_social_networks_migration(self, kb):
        """Simula migração de redes sociais"""
        self.stdout.write('')
        self.stdout.write('📱 SIMULANDO MIGRAÇÃO DE REDES SOCIAIS:')
        
        if not kb.redes_sociais or not isinstance(kb.redes_sociais, dict):
            self.stdout.write('  ℹ️  Nenhuma rede social no JSON legado')
            return 0
        
        count = 0
        for network_type, url in kb.redes_sociais.items():
            if url:
                self.stdout.write(f'  → Seria criada: {network_type} ({url})')
                count += 1
        
        return count
