#!/usr/bin/env python3
"""
Script de teste para integração N8N
Testa envio de dados para N8N e recebimento de resposta
"""
import os
import sys
import django
import hmac
import hashlib
import time
import json
import requests

# Setup Django
sys.path.insert(0, '/opt/iamkt/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings.development')
django.setup()

from django.conf import settings
from apps.knowledge.models import KnowledgeBase
from apps.knowledge.services.n8n_service import N8NService


def test_send_to_n8n():
    """Testa envio de dados para N8N"""
    print("=" * 80)
    print("🧪 TESTE: Envio de dados para N8N")
    print("=" * 80)
    
    # Buscar primeira KB
    kb = KnowledgeBase.objects.first()
    
    if not kb:
        print("❌ Nenhuma Knowledge Base encontrada!")
        print("💡 Crie uma KB primeiro através da interface web")
        return False
    
    print(f"\n📊 Knowledge Base encontrada:")
    print(f"   ID: {kb.id}")
    print(f"   Organização: {kb.organization.name} (ID: {kb.organization_id})")
    print(f"   Nome: {kb.nome_empresa}")
    print(f"   Descrição: {kb.descricao_produto[:50]}..." if kb.descricao_produto else "   Descrição: (vazio)")
    
    # Verificar configurações
    print(f"\n🔧 Configurações N8N:")
    print(f"   URL: {settings.N8N_WEBHOOK_FUNDAMENTOS}")
    print(f"   Secret: {settings.N8N_WEBHOOK_SECRET[:10]}..." if settings.N8N_WEBHOOK_SECRET else "   Secret: (NÃO CONFIGURADO)")
    print(f"   Timeout: {settings.N8N_WEBHOOK_TIMEOUT}s")
    print(f"   Max Retries: {settings.N8N_MAX_RETRIES}")
    
    if not settings.N8N_WEBHOOK_SECRET:
        print("\n❌ N8N_WEBHOOK_SECRET não configurado!")
        print("💡 Configure no .env.development")
        return False
    
    if not settings.N8N_WEBHOOK_FUNDAMENTOS:
        print("\n❌ N8N_WEBHOOK_FUNDAMENTOS não configurado!")
        print("💡 Configure no .env.development")
        return False
    
    # Enviar para N8N
    print(f"\n🚀 Enviando dados para N8N...")
    result = N8NService.send_fundamentos(kb)
    
    if result['success']:
        print(f"\n✅ SUCESSO!")
        print(f"   Revision ID: {result['revision_id']}")
        print(f"   Mensagem: {result['message']}")
        
        # Recarregar KB para ver mudanças
        kb.refresh_from_db()
        print(f"\n📊 Status da KB atualizado:")
        print(f"   analysis_status: {kb.analysis_status}")
        print(f"   analysis_revision_id: {kb.analysis_revision_id}")
        print(f"   analysis_requested_at: {kb.analysis_requested_at}")
        
        return True
    else:
        print(f"\n❌ ERRO!")
        print(f"   Erro: {result['error']}")
        return False


def test_webhook_signature():
    """Testa geração e validação de assinatura HMAC"""
    print("\n" + "=" * 80)
    print("🧪 TESTE: Geração e Validação de Assinatura HMAC")
    print("=" * 80)
    
    # Payload de teste
    payload = {
        'kb_id': 1,
        'organization_id': 1,
        'test': 'data'
    }
    
    timestamp = int(time.time())
    
    # Gerar assinatura
    payload_string = json.dumps(payload, sort_keys=True)
    message = f"{payload_string}{timestamp}"
    
    signature = hmac.new(
        settings.N8N_WEBHOOK_SECRET.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    print(f"\n📝 Payload: {payload}")
    print(f"⏰ Timestamp: {timestamp}")
    print(f"🔐 Assinatura: {signature}")
    
    # Validar assinatura (simular N8N)
    expected_signature = hmac.new(
        settings.N8N_WEBHOOK_SECRET.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    if hmac.compare_digest(signature, expected_signature):
        print(f"\n✅ Assinatura válida!")
        return True
    else:
        print(f"\n❌ Assinatura inválida!")
        return False


def test_webhook_endpoint():
    """Testa endpoint webhook Django (simulando N8N)"""
    print("\n" + "=" * 80)
    print("🧪 TESTE: Endpoint Webhook Django")
    print("=" * 80)
    
    # Buscar KB com análise em andamento
    kb = KnowledgeBase.objects.filter(analysis_status='processing').first()
    
    if not kb:
        print("⚠️  Nenhuma KB com análise em andamento")
        print("💡 Execute test_send_to_n8n() primeiro")
        return False
    
    print(f"\n📊 KB encontrada:")
    print(f"   ID: {kb.id}")
    print(f"   Revision ID: {kb.analysis_revision_id}")
    print(f"   Status: {kb.analysis_status}")
    
    # Montar payload de resposta (simulando N8N)
    response_payload = {
        'kb_id': kb.id,
        'organization_id': kb.organization_id,
        'revision_id': kb.analysis_revision_id,
        'payload': [
            {
                'missao': {
                    'informado_pelo_usuario': kb.missao or '',
                    'avaliacao': 'Teste de avaliação',
                    'status': 'médio',
                    'sugestao_do_agente_iamkt': 'Teste de sugestão'
                }
            }
        ],
        'reference_images_analysis': []
    }
    
    # Gerar timestamp e assinatura
    timestamp = int(time.time())
    payload_string = json.dumps(response_payload, sort_keys=True)
    message = f"{payload_string}{timestamp}"
    
    signature = hmac.new(
        settings.N8N_WEBHOOK_SECRET.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Headers
    headers = {
        'Content-Type': 'application/json',
        'X-INTERNAL-TOKEN': settings.N8N_WEBHOOK_SECRET,
        'X-Signature': signature,
        'X-Timestamp': str(timestamp)
    }
    
    # URL do webhook
    webhook_url = f"https://iamkt-femmeintegra.aisuites.com.br/knowledge/webhook/fundamentos/"
    
    print(f"\n🚀 Enviando resposta simulada para webhook...")
    print(f"   URL: {webhook_url}")
    print(f"   KB ID: {kb.id}")
    print(f"   Revision ID: {kb.analysis_revision_id}")
    
    try:
        response = requests.post(
            webhook_url,
            json=response_payload,
            headers=headers,
            timeout=10
        )
        
        print(f"\n📡 Resposta do servidor:")
        print(f"   Status: {response.status_code}")
        print(f"   Body: {response.text}")
        
        if response.status_code == 200:
            # Recarregar KB
            kb.refresh_from_db()
            print(f"\n✅ SUCESSO!")
            print(f"   analysis_status: {kb.analysis_status}")
            print(f"   analysis_completed_at: {kb.analysis_completed_at}")
            print(f"   n8n_analysis: {json.dumps(kb.n8n_analysis, indent=2)[:200]}...")
            return True
        else:
            print(f"\n❌ ERRO: Status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n❌ ERRO: {str(e)}")
        return False


if __name__ == '__main__':
    print("\n🧪 INICIANDO TESTES DE INTEGRAÇÃO N8N\n")
    
    # Teste 1: Assinatura HMAC
    test1 = test_webhook_signature()
    
    # Teste 2: Envio para N8N
    test2 = test_send_to_n8n()
    
    # Teste 3: Webhook Django (apenas se teste 2 passou)
    test3 = False
    if test2:
        print("\n⏳ Aguarde o N8N processar (ou execute test_webhook_endpoint() manualmente)")
        print("💡 Para testar o webhook Django, execute:")
        print("   python test_n8n_integration.py webhook")
    
    # Resumo
    print("\n" + "=" * 80)
    print("📊 RESUMO DOS TESTES")
    print("=" * 80)
    print(f"   Assinatura HMAC: {'✅ PASSOU' if test1 else '❌ FALHOU'}")
    print(f"   Envio para N8N: {'✅ PASSOU' if test2 else '❌ FALHOU'}")
    print(f"   Webhook Django: ⏳ PENDENTE")
    print("=" * 80)
    
    # Se argumento "webhook" foi passado, testar webhook
    if len(sys.argv) > 1 and sys.argv[1] == 'webhook':
        test3 = test_webhook_endpoint()
        print(f"\n   Webhook Django: {'✅ PASSOU' if test3 else '❌ FALHOU'}")
