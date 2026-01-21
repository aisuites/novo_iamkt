"""
Script para criar dados de teste: 2 organizations e 2 usuários

Uso:
    docker compose exec -u root iamkt_web python scripts/create_test_data.py
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
from django.utils import timezone

User = get_user_model()


def create_test_data():
    """Criar 2 organizations e 2 usuários de teste"""
    
    print("=" * 60)
    print("CRIANDO DADOS DE TESTE")
    print("=" * 60)
    
    # ========================================
    # ORGANIZATION 1: IAMKT (já existe)
    # ========================================
    print("\n1. Verificando Organization IAMKT...")
    org1, created = Organization.objects.get_or_create(
        slug='iamkt',
        defaults={
            'name': 'IAMKT',
            'plan_type': 'premium',
            'is_active': True,
            'approved_at': timezone.now(),
            'quota_pautas_dia': 20,
            'quota_posts_dia': 20,
            'quota_posts_mes': 100,
            'quota_videos_dia': 5,
            'quota_videos_mes': 20,
            'alert_80_enabled': True,
            'alert_100_enabled': True,
            'alert_email': 'admin@iamkt.com',
        }
    )
    if created:
        print(f"   ✅ Organization criada: {org1.name}")
    else:
        print(f"   ℹ️  Organization já existe: {org1.name}")
    
    # Area para IAMKT
    area1, created = Area.objects.get_or_create(
        name='Marketing',
        organization=org1,
        defaults={
            'description': 'Área de Marketing da IAMKT',
            'is_active': True
        }
    )
    if created:
        print(f"   ✅ Area criada: {area1.name}")
    else:
        print(f"   ℹ️  Area já existe: {area1.name}")
    
    # ========================================
    # ORGANIZATION 2: ACME Corp (nova)
    # ========================================
    print("\n2. Criando Organization ACME Corp...")
    org2, created = Organization.objects.get_or_create(
        slug='acme-corp',
        defaults={
            'name': 'ACME Corp',
            'plan_type': 'basic',
            'is_active': True,
            'approved_at': timezone.now(),
            'quota_pautas_dia': 5,
            'quota_posts_dia': 5,
            'quota_posts_mes': 30,
            'quota_videos_dia': 2,
            'quota_videos_mes': 10,
            'alert_80_enabled': True,
            'alert_100_enabled': True,
            'alert_email': 'admin@acmecorp.com',
        }
    )
    if created:
        print(f"   ✅ Organization criada: {org2.name}")
    else:
        print(f"   ℹ️  Organization já existe: {org2.name}")
    
    # Area para ACME Corp
    area2, created = Area.objects.get_or_create(
        name='Vendas',
        organization=org2,
        defaults={
            'description': 'Área de Vendas da ACME Corp',
            'is_active': True
        }
    )
    if created:
        print(f"   ✅ Area criada: {area2.name}")
    else:
        print(f"   ℹ️  Area já existe: {area2.name}")
    
    # ========================================
    # USUÁRIO 1: user_iamkt (IAMKT)
    # ========================================
    print("\n3. Criando Usuário para IAMKT...")
    user1, created = User.objects.get_or_create(
        username='user_iamkt',
        defaults={
            'email': 'user@iamkt.com',
            'first_name': 'João',
            'last_name': 'Silva',
            'organization': org1,
            'profile': 'editor',
            'is_active': True,
            'is_staff': True,
        }
    )
    if created:
        user1.set_password('senha123')
        user1.save()
        user1.areas.add(area1)
        print(f"   ✅ Usuário criado: {user1.username}")
        print(f"      Email: {user1.email}")
        print(f"      Senha: senha123")
        print(f"      Organization: {org1.name}")
    else:
        print(f"   ℹ️  Usuário já existe: {user1.username}")
        # Garantir que está vinculado à organization
        if not user1.organization:
            user1.organization = org1
            user1.save()
            print(f"      ✅ Organization vinculada: {org1.name}")
        if not user1.areas.filter(id=area1.id).exists():
            user1.areas.add(area1)
            print(f"      ✅ Area vinculada: {area1.name}")
    
    # ========================================
    # USUÁRIO 2: user_acme (ACME Corp)
    # ========================================
    print("\n4. Criando Usuário para ACME Corp...")
    user2, created = User.objects.get_or_create(
        username='user_acme',
        defaults={
            'email': 'user@acmecorp.com',
            'first_name': 'Maria',
            'last_name': 'Santos',
            'organization': org2,
            'profile': 'editor',
            'is_active': True,
            'is_staff': True,
        }
    )
    if created:
        user2.set_password('senha123')
        user2.save()
        user2.areas.add(area2)
        print(f"   ✅ Usuário criado: {user2.username}")
        print(f"      Email: {user2.email}")
        print(f"      Senha: senha123")
        print(f"      Organization: {org2.name}")
    else:
        print(f"   ℹ️  Usuário já existe: {user2.username}")
        # Garantir que está vinculado à organization
        if not user2.organization:
            user2.organization = org2
            user2.save()
            print(f"      ✅ Organization vinculada: {org2.name}")
        if not user2.areas.filter(id=area2.id).exists():
            user2.areas.add(area2)
            print(f"      ✅ Area vinculada: {area2.name}")
    
    # ========================================
    # RESUMO
    # ========================================
    print("\n" + "=" * 60)
    print("DADOS DE TESTE CRIADOS COM SUCESSO!")
    print("=" * 60)
    
    print("\n📊 RESUMO:")
    print(f"\nOrganizations: {Organization.objects.count()}")
    print(f"  - {org1.name} ({org1.plan_type})")
    print(f"  - {org2.name} ({org2.plan_type})")
    
    print(f"\nUsuários: {User.objects.filter(is_superuser=False).count()}")
    print(f"  - {user1.username} → {org1.name}")
    print(f"  - {user2.username} → {org2.name}")
    
    print("\n🔐 CREDENCIAIS DE TESTE:")
    print("\nUsuário 1 (IAMKT):")
    print(f"  Username: user_iamkt")
    print(f"  Email: user@iamkt.com")
    print(f"  Senha: senha123")
    print(f"  Organization: IAMKT (Premium)")
    
    print("\nUsuário 2 (ACME Corp):")
    print(f"  Username: user_acme")
    print(f"  Email: user@acmecorp.com")
    print(f"  Senha: senha123")
    print(f"  Organization: ACME Corp (Basic)")
    
    print("\n✅ Agora você pode testar o isolamento de tenants!")
    print("   1. Faça login com user_iamkt")
    print("   2. Crie algumas Pautas/Posts")
    print("   3. Faça logout e login com user_acme")
    print("   4. Verifique que não vê os dados de IAMKT")
    print("=" * 60)


if __name__ == '__main__':
    create_test_data()
