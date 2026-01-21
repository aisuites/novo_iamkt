"""
Script para criar pautas de teste para IAMKT e ACME Corp

Uso:
    docker compose exec -u root iamkt_web python scripts/create_test_pautas.py
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings.development')
django.setup()

from django.contrib.auth import get_user_model
from apps.core.models import Organization, Area
from apps.content.models import Pauta
from django.utils import timezone

User = get_user_model()


def create_test_pautas():
    """Criar pautas de teste para ambas organizations"""
    
    print("=" * 60)
    print("CRIANDO PAUTAS DE TESTE")
    print("=" * 60)
    
    # ========================================
    # PAUTA 1: IAMKT
    # ========================================
    print("\n1. Criando Pauta para IAMKT...")
    
    try:
        org_iamkt = Organization.objects.get(slug='iamkt')
        user_iamkt = User.objects.get(username='user_iamkt')
        area_iamkt = Area.objects.filter(organization=org_iamkt).first()
        
        pauta_iamkt = Pauta.objects.create(
            organization=org_iamkt,
            user=user_iamkt,
            area=area_iamkt,
            theme='Marketing Digital para B2B',
            target_audience='Empresas de tecnologia',
            objective='engajamento',
            additional_context='Foco em estratégias de inbound marketing',
            title='5 Estratégias de Marketing Digital para Empresas B2B',
            description='Explore as principais estratégias de marketing digital que empresas B2B podem usar para aumentar seu alcance e gerar leads qualificados.',
            status='completed',
            completed_at=timezone.now()
        )
        
        print(f"   ✅ Pauta criada: {pauta_iamkt.title}")
        print(f"      Organization: {org_iamkt.name}")
        print(f"      User: {user_iamkt.username}")
        print(f"      ID: {pauta_iamkt.id}")
        
    except Exception as e:
        print(f"   ❌ Erro ao criar pauta IAMKT: {e}")
    
    # ========================================
    # PAUTA 2: ACME Corp
    # ========================================
    print("\n2. Criando Pauta para ACME Corp...")
    
    try:
        org_acme = Organization.objects.get(slug='acme-corp')
        user_acme = User.objects.get(username='user_acme')
        area_acme = Area.objects.filter(organization=org_acme).first()
        
        pauta_acme = Pauta.objects.create(
            organization=org_acme,
            user=user_acme,
            area=area_acme,
            theme='Técnicas de Vendas B2C',
            target_audience='Consumidores finais',
            objective='conversao',
            additional_context='Foco em vendas online e e-commerce',
            title='Como Aumentar Conversões no E-commerce',
            description='Descubra técnicas comprovadas para aumentar as taxas de conversão em lojas virtuais e melhorar a experiência do cliente.',
            status='completed',
            completed_at=timezone.now()
        )
        
        print(f"   ✅ Pauta criada: {pauta_acme.title}")
        print(f"      Organization: {org_acme.name}")
        print(f"      User: {user_acme.username}")
        print(f"      ID: {pauta_acme.id}")
        
    except Exception as e:
        print(f"   ❌ Erro ao criar pauta ACME: {e}")
    
    # ========================================
    # RESUMO
    # ========================================
    print("\n" + "=" * 60)
    print("PAUTAS DE TESTE CRIADAS COM SUCESSO!")
    print("=" * 60)
    
    print("\n📊 RESUMO:")
    
    pautas_iamkt = Pauta.objects.filter(organization=org_iamkt).count()
    pautas_acme = Pauta.objects.filter(organization=org_acme).count()
    
    print(f"\nIAMKT: {pautas_iamkt} pauta(s)")
    print(f"ACME Corp: {pautas_acme} pauta(s)")
    
    print("\n✅ VALIDAR ISOLAMENTO:")
    print("   1. Login como user_iamkt")
    print("   2. Ir em /admin/content/pauta/")
    print("   3. Deve ver APENAS a pauta de IAMKT")
    print()
    print("   4. Logout e login como user_acme")
    print("   5. Ir em /admin/content/pauta/")
    print("   6. Deve ver APENAS a pauta de ACME Corp")
    print("=" * 60)


if __name__ == '__main__':
    create_test_pautas()
