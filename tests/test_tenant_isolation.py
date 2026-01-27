"""
Testes de isolamento de tenants
Garante que dados de uma organization não vazam para outra
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from apps.core.models import Organization
from apps.knowledge.models import KnowledgeBase, Logo, ReferenceImage, CustomFont

User = get_user_model()


class TenantIsolationTestCase(TestCase):
    """
    Testes de isolamento entre organizations
    """
    
    def setUp(self):
        """Configurar dados de teste"""
        # Organization 1
        self.org1 = Organization.objects.create(
            name='Organization 1',
            slug='org1',
            email='org1@test.com'
        )
        self.user1 = User.objects.create_user(
            email='user1@test.com',
            password='password123',
            organization=self.org1
        )
        self.kb1 = KnowledgeBase.objects.create(
            organization=self.org1,
            nome_empresa='Empresa 1'
        )
        
        # Organization 2
        self.org2 = Organization.objects.create(
            name='Organization 2',
            slug='org2',
            email='org2@test.com'
        )
        self.user2 = User.objects.create_user(
            email='user2@test.com',
            password='password123',
            organization=self.org2
        )
        self.kb2 = KnowledgeBase.objects.create(
            organization=self.org2,
            nome_empresa='Empresa 2'
        )
        
        # Criar logos para cada organization
        self.logo1 = Logo.objects.create(
            knowledge_base=self.kb1,
            name='Logo 1',
            s3_key='org-1/logos/logo1.png',
            uploaded_by=self.user1
        )
        self.logo2 = Logo.objects.create(
            knowledge_base=self.kb2,
            name='Logo 2',
            s3_key='org-2/logos/logo2.png',
            uploaded_by=self.user2
        )
        
        self.client = Client()
    
    def test_user_sees_only_own_organization_data(self):
        """Usuário vê apenas dados da própria organization"""
        # Login como user1
        self.client.login(email='user1@test.com', password='password123')
        
        # Acessar página de knowledge
        response = self.client.get('/knowledge/')
        
        # Deve ver dados da org1
        self.assertContains(response, 'Empresa 1')
        self.assertContains(response, 'Logo 1')
        
        # NÃO deve ver dados da org2
        self.assertNotContains(response, 'Empresa 2')
        self.assertNotContains(response, 'Logo 2')
    
    def test_cannot_access_other_organization_logo(self):
        """Não pode acessar logo de outra organization"""
        # Login como user1
        self.client.login(email='user1@test.com', password='password123')
        
        # Tentar deletar logo da org2
        response = self.client.delete(f'/knowledge/logo/{self.logo2.id}/delete/')
        
        # Deve retornar 404 (não encontrado) ou 403 (forbidden)
        self.assertIn(response.status_code, [403, 404])
    
    def test_queries_filter_by_organization(self):
        """Queries filtram corretamente por organization"""
        # Simular request com org1
        from unittest.mock import Mock
        request = Mock()
        request.organization = self.org1
        
        # Buscar logos
        logos = Logo.objects.filter(knowledge_base__organization=request.organization)
        
        # Deve retornar apenas logo1
        self.assertEqual(logos.count(), 1)
        self.assertEqual(logos.first().id, self.logo1.id)
    
    def test_knowledge_base_unique_per_organization(self):
        """Cada organization tem apenas 1 KnowledgeBase"""
        # Tentar criar outro KB para org1
        kb_count_before = KnowledgeBase.objects.filter(organization=self.org1).count()
        
        # get_or_create deve retornar o existente
        kb, created = KnowledgeBase.objects.get_or_create(
            organization=self.org1,
            defaults={'nome_empresa': 'Empresa 1 Novo'}
        )
        
        kb_count_after = KnowledgeBase.objects.filter(organization=self.org1).count()
        
        # Não deve criar novo
        self.assertFalse(created)
        self.assertEqual(kb_count_before, kb_count_after)
        self.assertEqual(kb.id, self.kb1.id)


class TenantIsolationAPITestCase(TestCase):
    """
    Testes de isolamento em endpoints de API
    """
    
    def setUp(self):
        """Configurar dados de teste"""
        # Organization 1
        self.org1 = Organization.objects.create(
            name='Organization 1',
            slug='org1',
            email='org1@test.com'
        )
        self.user1 = User.objects.create_user(
            email='user1@test.com',
            password='password123',
            organization=self.org1
        )
        
        # Organization 2
        self.org2 = Organization.objects.create(
            name='Organization 2',
            slug='org2',
            email='org2@test.com'
        )
        self.user2 = User.objects.create_user(
            email='user2@test.com',
            password='password123',
            organization=self.org2
        )
        
        self.client = Client()
    
    def test_upload_url_contains_organization_id(self):
        """URL de upload contém organization_id correto"""
        # Login como user1
        self.client.login(email='user1@test.com', password='password123')
        
        # Solicitar URL de upload
        response = self.client.post('/knowledge/logo/upload-url/', {
            'fileName': 'test.png',
            'fileType': 'image/png',
            'fileSize': 1024
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # s3_key deve conter org-1
        self.assertIn(f'org-{self.org1.id}', data['data']['s3_key'])
        # NÃO deve conter org-2
        self.assertNotIn(f'org-{self.org2.id}', data['data']['s3_key'])
