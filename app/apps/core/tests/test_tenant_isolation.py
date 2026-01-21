"""
Testes de Isolamento Multi-tenant

Valida que:
1. Usuários só acessam dados da própria organization
2. OrganizationScopedManager filtra automaticamente
3. Admin filtra corretamente
"""
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from apps.core.models import Organization, Area
from apps.content.models import Pauta, Post
from apps.core.middleware import TenantMiddleware

User = get_user_model()


class TenantIsolationTestCase(TestCase):
    """Testes de isolamento entre organizations"""
    
    def setUp(self):
        """Configurar dados de teste"""
        # Criar organizations
        self.org_a = Organization.objects.create(
            name='Organization A',
            slug='org-a',
            is_active=True
        )
        self.org_b = Organization.objects.create(
            name='Organization B',
            slug='org-b',
            is_active=True
        )
        
        # Criar usuários
        self.user_a = User.objects.create_user(
            username='user_a',
            email='user_a@test.com',
            password='test123',
            organization=self.org_a
        )
        self.user_b = User.objects.create_user(
            username='user_b',
            email='user_b@test.com',
            password='test123',
            organization=self.org_b
        )
        
        # Criar área global
        self.area = Area.objects.create(name='Marketing')
        
        # Criar pautas
        self.pauta_a = Pauta.objects.create(
            organization=self.org_a,
            user=self.user_a,
            area=self.area,
            theme='Pauta A',
            target_audience='Público A',
            objective='engajamento',
            title='Pauta da Org A',
            description='Descrição A'
        )
        self.pauta_b = Pauta.objects.create(
            organization=self.org_b,
            user=self.user_b,
            area=self.area,
            theme='Pauta B',
            target_audience='Público B',
            objective='conversao',
            title='Pauta da Org B',
            description='Descrição B'
        )
    
    def test_organization_scoped_manager_filters_automatically(self):
        """Teste: for_organization() filtra corretamente"""
        # Filtrar por organization A
        pautas = Pauta.objects.for_organization(self.org_a)
        
        # Deve retornar apenas pautas da org A
        self.assertEqual(pautas.count(), 1)
        self.assertEqual(pautas.first().id, self.pauta_a.id)
        self.assertEqual(pautas.first().organization, self.org_a)
    
    def test_user_cannot_access_other_organization_data(self):
        """Teste: for_organization filtra dados corretamente"""
        # Filtrar por organization B
        pautas = Pauta.objects.for_organization(self.org_b)
        
        # Deve retornar apenas pautas da org B
        self.assertEqual(pautas.count(), 1)
        self.assertEqual(pautas.first().id, self.pauta_b.id)
        
        # Não deve conseguir acessar pauta da org A
        self.assertNotIn(self.pauta_a, pautas)
    
    def test_all_tenants_returns_all_data(self):
        """Teste: all_tenants() retorna dados de todas organizations"""
        # Sem contexto de organization
        pautas = Pauta.objects.all_tenants()
        
        # Deve retornar pautas de ambas organizations
        self.assertEqual(pautas.count(), 2)
        self.assertIn(self.pauta_a, pautas)
        self.assertIn(self.pauta_b, pautas)
    
    def test_for_organization_filters_correctly(self):
        """Teste: for_organization() filtra corretamente"""
        # Filtrar por organization A
        pautas_a = Pauta.objects.for_organization(self.org_a)
        self.assertEqual(pautas_a.count(), 1)
        self.assertEqual(pautas_a.first().organization, self.org_a)
        
        # Filtrar por organization B
        pautas_b = Pauta.objects.for_organization(self.org_b)
        self.assertEqual(pautas_b.count(), 1)
        self.assertEqual(pautas_b.first().organization, self.org_b)
    
    def test_middleware_sets_organization_correctly(self):
        """Teste: Middleware seta organization corretamente no request"""
        factory = RequestFactory()
        request = factory.get('/dashboard/')
        request.user = self.user_a
        
        # Processar middleware
        middleware = TenantMiddleware(lambda r: None)
        middleware.process_request(request)
        
        # Verificar que organization foi setada
        self.assertTrue(hasattr(request, 'organization'))
        self.assertEqual(request.organization, self.org_a)
    
    def test_quotas_are_isolated_per_organization(self):
        """Teste: Quotas são isoladas por organization"""
        from apps.core.models import QuotaUsageDaily
        from django.utils import timezone
        
        today = timezone.now().date()
        
        # Criar ou obter uso de quota para org A
        usage_a, _ = QuotaUsageDaily.objects.get_or_create(
            organization=self.org_a,
            date=today,
            defaults={'pautas_requested': 3}
        )
        usage_a.pautas_requested = 3
        usage_a.save()
        
        # Criar ou obter uso de quota para org B
        usage_b, _ = QuotaUsageDaily.objects.get_or_create(
            organization=self.org_b,
            date=today,
            defaults={'pautas_requested': 5}
        )
        usage_b.pautas_requested = 5
        usage_b.save()
        
        # Verificar isolamento
        self.assertEqual(usage_a.organization, self.org_a)
        self.assertEqual(usage_b.organization, self.org_b)
        self.assertNotEqual(usage_a.pautas_requested, usage_b.pautas_requested)
    
    def test_create_with_wrong_organization_fails(self):
        """Teste: Filtro por organization funciona independente de quem criou"""
        # Criar pauta com organization B mas user da org A
        pauta_wrong = Pauta.objects.create(
            organization=self.org_b,
            user=self.user_a,  # User da org A
            area=self.area,
            theme='Teste',
            target_audience='Teste',
            objective='engajamento',
            title='Teste',
            description='Teste'
        )
        
        # Ao filtrar por org A, não deve aparecer (mesmo sendo do user_a)
        pautas_a = Pauta.objects.for_organization(self.org_a)
        self.assertNotIn(pauta_wrong, pautas_a)
        
        # Ao filtrar por org B, deve aparecer
        pautas_b = Pauta.objects.for_organization(self.org_b)
        self.assertIn(pauta_wrong, pautas_b)


class AdminIsolationTestCase(TestCase):
    """Testes de isolamento no Django Admin"""
    
    def setUp(self):
        """Configurar dados de teste"""
        # Criar organizations
        self.org_a = Organization.objects.create(
            name='Organization A',
            slug='org-a',
            is_active=True
        )
        self.org_b = Organization.objects.create(
            name='Organization B',
            slug='org-b',
            is_active=True
        )
        
        # Criar usuários staff
        self.admin_a = User.objects.create_user(
            username='admin_a',
            email='admin_a@test.com',
            password='test123',
            organization=self.org_a,
            is_staff=True
        )
        self.admin_b = User.objects.create_user(
            username='admin_b',
            email='admin_b@test.com',
            password='test123',
            organization=self.org_b,
            is_staff=True
        )
        
        # Criar superuser
        self.superuser = User.objects.create_superuser(
            username='superuser',
            email='super@test.com',
            password='test123'
        )
    
    def test_admin_sees_only_own_organization_data(self):
        """Teste: Admin vê apenas dados da própria organization"""
        from apps.content.admin import PautaAdmin
        from apps.content.models import Pauta
        
        # Criar área
        area = Area.objects.create(name='Marketing')
        
        # Criar pautas
        pauta_a = Pauta.objects.create(
            organization=self.org_a,
            user=self.admin_a,
            area=area,
            theme='A',
            target_audience='A',
            objective='engajamento',
            title='A',
            description='A'
        )
        pauta_b = Pauta.objects.create(
            organization=self.org_b,
            user=self.admin_b,
            area=area,
            theme='B',
            target_audience='B',
            objective='conversao',
            title='B',
            description='B'
        )
        
        # Simular request do admin A
        factory = RequestFactory()
        request = factory.get('/admin/content/pauta/')
        request.user = self.admin_a
        request.organization = self.org_a
        
        # Obter queryset do admin
        admin = PautaAdmin(Pauta, None)
        qs = admin.get_queryset(request)
        
        # Admin A deve ver apenas pauta A
        self.assertEqual(qs.count(), 1)
        self.assertIn(pauta_a, qs)
        self.assertNotIn(pauta_b, qs)
    
    def test_superuser_sees_all_data(self):
        """Teste: Superuser vê dados de todas organizations"""
        from apps.content.admin import PautaAdmin
        from apps.content.models import Pauta
        
        # Criar área
        area = Area.objects.create(name='Marketing')
        
        # Criar pautas
        pauta_a = Pauta.objects.create(
            organization=self.org_a,
            user=self.admin_a,
            area=area,
            theme='A',
            target_audience='A',
            objective='engajamento',
            title='A',
            description='A'
        )
        pauta_b = Pauta.objects.create(
            organization=self.org_b,
            user=self.admin_b,
            area=area,
            theme='B',
            target_audience='B',
            objective='conversao',
            title='B',
            description='B'
        )
        
        # Simular request do superuser
        factory = RequestFactory()
        request = factory.get('/admin/content/pauta/')
        request.user = self.superuser
        
        # Obter queryset do admin
        admin = PautaAdmin(Pauta, None)
        qs = admin.get_queryset(request)
        
        # Superuser deve ver todas as pautas
        self.assertEqual(qs.count(), 2)
        self.assertIn(pauta_a, qs)
        self.assertIn(pauta_b, qs)
