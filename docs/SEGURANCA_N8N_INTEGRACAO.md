# 🔐 SEGURANÇA E INTEGRAÇÃO N8N - ARQUITETURA COMPLETA

**Data de Criação:** 28 de Janeiro de 2026  
**Última Atualização:** 28 de Janeiro de 2026 - 17:59  
**Status:** Planejamento Aprovado

---

## 🎯 OBJETIVO

Implementar integração segura e escalável entre Django (IAMKT) e N8N, preparada para:
- ✅ Múltiplos ambientes (dev/staging/prod)
- ✅ Alta exposição e tráfego
- ✅ Proteção contra ataques (DDoS, replay, injection, MITM)
- ✅ Auditoria e monitoramento
- ✅ Fácil manutenção e configuração

---

## 🏗️ ARQUITETURA DE SEGURANÇA

### **Camadas de Proteção:**

```
┌─────────────────────────────────────────────────────────┐
│ CAMADA 1: Validação de IP (Whitelist)                  │
│ - IP fixo do servidor N8N                              │
│ - Configurável por ambiente (dev/prod)                 │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ CAMADA 2: Autenticação HMAC + Timestamp                │
│ - Assinatura SHA-256 do payload                        │
│ - Timestamp para prevenir replay attacks               │
│ - Janela de 5 minutos                                  │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ CAMADA 3: Validação de Dados                           │
│ - revision_id único e válido                           │
│ - kb_id existe e pertence à organização                │
│ - Estrutura do payload validada                        │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ CAMADA 4: Rate Limiting                                │
│ - Limite de requisições por IP                         │
│ - Limite de requisições por organização                │
│ - Proteção contra DDoS                                 │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ CAMADA 5: Auditoria e Logging                          │
│ - Log de todas as requisições                          │
│ - Alertas de tentativas suspeitas                      │
│ - Métricas de uso                                      │
└─────────────────────────────────────────────────────────┘
```

---

## 📋 CONFIGURAÇÕES DE AMBIENTE

### **Variáveis `.env` (Desenvolvimento)**

```bash
# ============================================
# N8N INTEGRATION - DEVELOPMENT
# ============================================

# Webhooks N8N (Envio: Django → N8N)
N8N_WEBHOOK_FUNDAMENTOS=https://n8n.srv812718.hstgr.cloud/webhook/2f87eab4-40da-4975-a219-74f15dbb2576
N8N_WEBHOOK_COMPILA_SEM_SUGEST=https://n8n.srv812718.hstgr.cloud/webhook/compila-sem-sugestao
N8N_WEBHOOK_COMPILA_COM_SUGEST=https://n8n.srv812718.hstgr.cloud/webhook/compila-com-sugestao

# Timeout (segundos)
N8N_WEBHOOK_TIMEOUT=30

# Secret Token (compartilhado Django ↔ N8N)
# IMPORTANTE: Gerar token seguro com: openssl rand -hex 32
N8N_WEBHOOK_SECRET=GERAR_TOKEN_ALEATORIO_SEGURO_64_CARACTERES

# IP Whitelist (servidor N8N dev)
N8N_ALLOWED_IPS=IP_SERVIDOR_N8N_DEV,127.0.0.1

# Rate Limiting
N8N_RATE_LIMIT_PER_IP=10/minute
N8N_RATE_LIMIT_PER_ORG=5/minute

# Retry Policy
N8N_MAX_RETRIES=3
N8N_RETRY_DELAY=5
```

### **Variáveis `.env` (Produção)**

```bash
# ============================================
# N8N INTEGRATION - PRODUCTION
# ============================================

# Webhooks N8N (Envio: Django → N8N)
N8N_WEBHOOK_FUNDAMENTOS=https://n8n-prod.srv812718.hstgr.cloud/webhook/fundamentos-prod
N8N_WEBHOOK_COMPILA_SEM_SUGEST=https://n8n-prod.srv812718.hstgr.cloud/webhook/compila-sem-sugestao-prod
N8N_WEBHOOK_COMPILA_COM_SUGEST=https://n8n-prod.srv812718.hstgr.cloud/webhook/compila-com-sugestao-prod

# Timeout (segundos)
N8N_WEBHOOK_TIMEOUT=60

# Secret Token (DIFERENTE de dev)
N8N_WEBHOOK_SECRET=TOKEN_PRODUCAO_DIFERENTE_E_MAIS_SEGURO

# IP Whitelist (servidor N8N prod)
N8N_ALLOWED_IPS=IP_SERVIDOR_N8N_PROD

# Rate Limiting (mais restritivo)
N8N_RATE_LIMIT_PER_IP=5/minute
N8N_RATE_LIMIT_PER_ORG=3/minute

# Retry Policy
N8N_MAX_RETRIES=5
N8N_RETRY_DELAY=10
```

---

## 🔐 IMPLEMENTAÇÃO DE SEGURANÇA

### **1. Django → N8N (Envio)**

**Service Layer: `apps/knowledge/services/n8n_service.py`**

```python
import hmac
import hashlib
import time
import json
import requests
from django.conf import settings
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

class N8NService:
    """
    Service para integração segura com N8N
    """
    
    @staticmethod
    def _generate_signature(payload: dict, timestamp: int) -> str:
        """
        Gera assinatura HMAC SHA-256 do payload
        
        Args:
            payload: Dados a serem enviados
            timestamp: Unix timestamp
            
        Returns:
            Assinatura hexadecimal
        """
        # Serializar payload de forma determinística
        payload_string = json.dumps(payload, sort_keys=True)
        
        # Concatenar payload + timestamp
        message = f"{payload_string}{timestamp}"
        
        # Gerar HMAC SHA-256
        signature = hmac.new(
            settings.N8N_WEBHOOK_SECRET.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    @staticmethod
    def _check_rate_limit(organization_id: int) -> bool:
        """
        Verifica rate limit por organização
        
        Args:
            organization_id: ID da organização
            
        Returns:
            True se dentro do limite, False se excedido
        """
        cache_key = f"n8n_rate_limit_org_{organization_id}"
        
        # Pegar contador atual
        current_count = cache.get(cache_key, 0)
        
        # Extrair limite do settings (ex: "5/minute")
        limit_str = settings.N8N_RATE_LIMIT_PER_ORG
        max_requests = int(limit_str.split('/')[0])
        
        if current_count >= max_requests:
            logger.warning(
                f"Rate limit exceeded for organization {organization_id}. "
                f"Current: {current_count}, Max: {max_requests}"
            )
            return False
        
        # Incrementar contador (expira em 60 segundos)
        cache.set(cache_key, current_count + 1, 60)
        return True
    
    @staticmethod
    def send_fundamentos(kb_instance) -> dict:
        """
        Envia dados da KB para análise N8N (Fundamentos)
        
        Args:
            kb_instance: Instância de KnowledgeBase
            
        Returns:
            dict com success, revision_id ou error
        """
        try:
            # 1. Verificar rate limit
            if not N8NService._check_rate_limit(kb_instance.organization_id):
                return {
                    'success': False,
                    'error': 'Rate limit exceeded. Try again later.'
                }
            
            # 2. Montar payload
            payload = {
                'kb_id': kb_instance.id,
                'organization_id': kb_instance.organization_id,
                'organization_name': kb_instance.organization.name,
                'mission': kb_instance.missao or '',
                'vision': kb_instance.visao or '',
                'value_proposition': kb_instance.proposta_valor or '',
                'differentials': kb_instance.diferenciais or '',
                'phrase_10_words': '',  # TODO: adicionar campo
                'target_audience': kb_instance.publico_externo or '',
                'tone_of_voice': kb_instance.tom_voz_externo or '',
                'description': kb_instance.descricao_produto or '',
                'palette_colors': kb_instance.get_colors_list(),
                'logo_files': kb_instance.get_logos_list(),
                'fonts': kb_instance.get_fonts_list(),
                'website_url': kb_instance.site_institucional or '',
                'social_networks': kb_instance.get_social_networks_list(),
                'competitors': kb_instance.concorrentes or [],
                'reference_images': kb_instance.get_reference_images_list(),
            }
            
            # 3. Gerar timestamp e assinatura
            timestamp = int(time.time())
            signature = N8NService._generate_signature(payload, timestamp)
            
            # 4. Preparar headers
            headers = {
                'Content-Type': 'application/json',
                'X-API-Key': settings.N8N_WEBHOOK_SECRET,
                'X-Signature': signature,
                'X-Timestamp': str(timestamp),
                'X-Organization-ID': str(kb_instance.organization_id),
                'X-KB-ID': str(kb_instance.id),
            }
            
            # 5. Enviar requisição com retry
            max_retries = settings.N8N_MAX_RETRIES
            retry_delay = settings.N8N_RETRY_DELAY
            
            for attempt in range(max_retries):
                try:
                    response = requests.post(
                        settings.N8N_WEBHOOK_FUNDAMENTOS,
                        json=payload,
                        headers=headers,
                        timeout=settings.N8N_WEBHOOK_TIMEOUT
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Log sucesso
                        logger.info(
                            f"N8N fundamentos sent successfully. "
                            f"KB: {kb_instance.id}, "
                            f"Org: {kb_instance.organization_id}, "
                            f"Revision: {data.get('revision_id')}"
                        )
                        
                        return {
                            'success': True,
                            'revision_id': data.get('revision_id'),
                            'message': 'Análise solicitada com sucesso'
                        }
                    
                    # Se não for 200, tentar novamente
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    
                    # Última tentativa falhou
                    logger.error(
                        f"N8N fundamentos failed after {max_retries} attempts. "
                        f"Status: {response.status_code}, "
                        f"Response: {response.text}"
                    )
                    
                    return {
                        'success': False,
                        'error': f'N8N returned status {response.status_code}'
                    }
                    
                except requests.Timeout:
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    
                    logger.error(f"N8N fundamentos timeout after {max_retries} attempts")
                    return {
                        'success': False,
                        'error': 'Request timeout. Try again later.'
                    }
                    
        except Exception as e:
            logger.exception(f"Error sending to N8N: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
```

---

### **2. N8N → Django (Retorno)**

**View Webhook: `apps/knowledge/views.py`**

```python
import hmac
import hashlib
import time
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.core.cache import cache
from apps.knowledge.models import KnowledgeBase
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["POST"])
def n8n_webhook_fundamentos(request):
    """
    Webhook para receber análise de fundamentos do N8N
    
    Segurança:
    - Validação de IP
    - Validação de assinatura HMAC
    - Validação de timestamp (anti-replay)
    - Validação de revision_id
    - Rate limiting
    """
    
    # CAMADA 1: Validação de IP
    client_ip = request.META.get('REMOTE_ADDR')
    allowed_ips = settings.N8N_ALLOWED_IPS.split(',')
    
    if client_ip not in allowed_ips:
        logger.warning(
            f"Unauthorized IP attempting to access webhook: {client_ip}"
        )
        return JsonResponse({
            'success': False,
            'error': 'Unauthorized IP'
        }, status=401)
    
    # CAMADA 2: Rate Limiting por IP
    cache_key = f"n8n_webhook_rate_limit_{client_ip}"
    current_count = cache.get(cache_key, 0)
    
    limit_str = settings.N8N_RATE_LIMIT_PER_IP
    max_requests = int(limit_str.split('/')[0])
    
    if current_count >= max_requests:
        logger.warning(
            f"Rate limit exceeded for IP {client_ip}. "
            f"Current: {current_count}, Max: {max_requests}"
        )
        return JsonResponse({
            'success': False,
            'error': 'Rate limit exceeded'
        }, status=429)
    
    cache.set(cache_key, current_count + 1, 60)
    
    # CAMADA 3: Validação de Timestamp (anti-replay)
    timestamp_header = request.headers.get('X-Timestamp')
    
    if not timestamp_header:
        logger.warning("Missing X-Timestamp header")
        return JsonResponse({
            'success': False,
            'error': 'Missing timestamp'
        }, status=400)
    
    try:
        timestamp = int(timestamp_header)
    except ValueError:
        logger.warning(f"Invalid timestamp format: {timestamp_header}")
        return JsonResponse({
            'success': False,
            'error': 'Invalid timestamp'
        }, status=400)
    
    # Verificar se timestamp está dentro da janela de 5 minutos
    current_time = int(time.time())
    time_diff = abs(current_time - timestamp)
    
    if time_diff > 300:  # 5 minutos
        logger.warning(
            f"Request expired. Time diff: {time_diff}s, "
            f"Timestamp: {timestamp}, Current: {current_time}"
        )
        return JsonResponse({
            'success': False,
            'error': 'Request expired'
        }, status=401)
    
    # CAMADA 4: Validação de Assinatura HMAC
    signature_header = request.headers.get('X-Signature')
    
    if not signature_header:
        logger.warning("Missing X-Signature header")
        return JsonResponse({
            'success': False,
            'error': 'Missing signature'
        }, status=400)
    
    # Reconstruir assinatura esperada
    payload_bytes = request.body
    payload_string = payload_bytes.decode('utf-8')
    message = f"{payload_string}{timestamp}"
    
    expected_signature = hmac.new(
        settings.N8N_WEBHOOK_SECRET.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Comparação segura (previne timing attacks)
    if not hmac.compare_digest(signature_header, expected_signature):
        logger.warning(
            f"Invalid signature from IP {client_ip}. "
            f"Expected: {expected_signature[:10]}..., "
            f"Received: {signature_header[:10]}..."
        )
        return JsonResponse({
            'success': False,
            'error': 'Invalid signature'
        }, status=401)
    
    # CAMADA 5: Validação de Dados
    try:
        data = json.loads(payload_string)
    except json.JSONDecodeError:
        logger.warning("Invalid JSON payload")
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    
    # Validar campos obrigatórios
    required_fields = ['kb_id', 'revision_id', 'payload']
    for field in required_fields:
        if field not in data:
            logger.warning(f"Missing required field: {field}")
            return JsonResponse({
                'success': False,
                'error': f'Missing field: {field}'
            }, status=400)
    
    kb_id = data['kb_id']
    revision_id = data['revision_id']
    analysis_payload = data['payload']
    
    # Buscar KB e validar revision_id
    try:
        kb = KnowledgeBase.objects.get(
            id=kb_id,
            analysis_revision_id=revision_id,
            analysis_status='processing'
        )
    except KnowledgeBase.DoesNotExist:
        logger.warning(
            f"Invalid KB or revision_id. "
            f"KB: {kb_id}, Revision: {revision_id}"
        )
        return JsonResponse({
            'success': False,
            'error': 'Invalid KB or revision_id'
        }, status=404)
    
    # CAMADA 6: Processar Análise
    try:
        # Armazenar análise
        kb.set_n8n_response({
            'revision_id': revision_id,
            'payload': analysis_payload,
            'reference_images_analysis': data.get('reference_images_analysis', [])
        })
        
        # Log sucesso
        logger.info(
            f"N8N analysis received and stored. "
            f"KB: {kb_id}, Org: {kb.organization_id}, "
            f"Revision: {revision_id}"
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Analysis received and stored'
        }, status=200)
        
    except Exception as e:
        logger.exception(f"Error processing N8N analysis: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Internal server error'
        }, status=500)
```

---

## 📝 CONFIGURAÇÃO N8N - PASSO A PASSO

### **PARTE 1: Configuração do Webhook de Recebimento (N8N recebe de Django)**

#### **Passo 1: Criar Workflow "Fundamentos - Análise"**

1. Acessar N8N: `https://n8n.srv812718.hstgr.cloud`
2. Clicar em "New Workflow"
3. Nomear: "IAMKT - Fundamentos - Análise"

#### **Passo 2: Adicionar Nó Webhook**

1. Clicar em "+" para adicionar nó
2. Buscar "Webhook"
3. Configurar:
   - **HTTP Method:** POST
   - **Path:** `2f87eab4-40da-4975-a219-74f15dbb2576`
   - **Authentication:** Header Auth
   - **Header Name:** `X-API-Key`
   - **Header Value:** `{{$env.N8N_WEBHOOK_SECRET}}` (variável de ambiente)
   - **Response Mode:** When Last Node Finishes
   - **Response Code:** 200

#### **Passo 3: Adicionar Validação de Assinatura**

1. Adicionar nó "Function"
2. Nomear: "Validar Assinatura"
3. Código:

```javascript
const crypto = require('crypto');

// Pegar dados do webhook
const payload = $input.item.json.body;
const signature = $input.item.json.headers['x-signature'];
const timestamp = $input.item.json.headers['x-timestamp'];

// Validar timestamp (5 minutos)
const currentTime = Math.floor(Date.now() / 1000);
const timeDiff = Math.abs(currentTime - parseInt(timestamp));

if (timeDiff > 300) {
  throw new Error('Request expired');
}

// Reconstruir assinatura
const payloadString = JSON.stringify(payload);
const message = `${payloadString}${timestamp}`;

const expectedSignature = crypto
  .createHmac('sha256', process.env.N8N_WEBHOOK_SECRET)
  .update(message)
  .digest('hex');

// Validar assinatura
if (signature !== expectedSignature) {
  throw new Error('Invalid signature');
}

// Retornar dados validados
return {
  json: {
    ...payload,
    validated: true,
    timestamp: timestamp
  }
};
```

#### **Passo 4: Adicionar Lógica de Análise**

1. Adicionar nó "HTTP Request" ou "OpenAI" (conforme sua IA)
2. Processar cada campo do payload
3. Gerar avaliações e sugestões

#### **Passo 5: Adicionar Nó de Resposta**

1. Adicionar nó "Respond to Webhook"
2. Configurar:
   - **Response Code:** 200
   - **Response Body:**

```json
{
  "success": true,
  "revision_id": "{{ $('Webhook').item.json.body.kb_id }}_{{ $now.toUnixInteger() }}",
  "message": "Analysis started"
}
```

---

### **PARTE 2: Configuração do Webhook de Envio (N8N envia para Django)**

#### **Passo 6: Adicionar Nó HTTP Request (Enviar Análise)**

1. Adicionar nó "HTTP Request"
2. Nomear: "Enviar Análise para Django"
3. Configurar:
   - **Method:** POST
   - **URL:** `{{ $env.DJANGO_WEBHOOK_URL }}/api/webhooks/fundamentos/`
   - **Authentication:** None (usaremos headers customizados)
   - **Send Headers:** Sim

#### **Passo 7: Configurar Headers de Segurança**

1. Em "Headers", adicionar:

```json
{
  "Content-Type": "application/json",
  "X-API-Key": "{{ $env.N8N_WEBHOOK_SECRET }}",
  "X-Signature": "{{ $('Gerar Assinatura').item.json.signature }}",
  "X-Timestamp": "{{ $('Gerar Assinatura').item.json.timestamp }}"
}
```

#### **Passo 8: Adicionar Nó de Geração de Assinatura**

1. Adicionar nó "Function" ANTES do HTTP Request
2. Nomear: "Gerar Assinatura"
3. Código:

```javascript
const crypto = require('crypto');

// Montar payload
const payload = {
  kb_id: $('Webhook').item.json.body.kb_id,
  revision_id: $('Responder Webhook').item.json.revision_id,
  payload: $('Processar Análise').item.json.analysis,
  reference_images_analysis: $('Processar Imagens').item.json.images || []
};

// Gerar timestamp
const timestamp = Math.floor(Date.now() / 1000);

// Serializar payload
const payloadString = JSON.stringify(payload);
const message = `${payloadString}${timestamp}`;

// Gerar assinatura HMAC SHA-256
const signature = crypto
  .createHmac('sha256', process.env.N8N_WEBHOOK_SECRET)
  .update(message)
  .digest('hex');

// Retornar payload + assinatura
return {
  json: {
    payload: payload,
    signature: signature,
    timestamp: timestamp
  }
};
```

#### **Passo 9: Configurar Body do HTTP Request**

1. No nó "HTTP Request", em "Body":
   - **Body Content Type:** JSON
   - **Specify Body:** Using JSON
   - **JSON:**

```json
{{ $('Gerar Assinatura').item.json.payload }}
```

---

### **PARTE 3: Variáveis de Ambiente N8N**

#### **Passo 10: Configurar Variáveis de Ambiente**

1. Acessar Settings → Environment Variables
2. Adicionar:

```bash
# Secret compartilhado com Django
N8N_WEBHOOK_SECRET=MESMO_TOKEN_DO_DJANGO_ENV

# URL do webhook Django
DJANGO_WEBHOOK_URL=https://iamkt-femmeintegra.aisuites.com.br
```

---

### **PARTE 4: Testes**

#### **Passo 11: Testar Webhook**

1. Ativar workflow
2. Copiar URL do webhook
3. Usar Postman ou curl para testar:

```bash
# Gerar timestamp
TIMESTAMP=$(date +%s)

# Gerar assinatura (exemplo com Python)
python3 << EOF
import hmac
import hashlib
import json

payload = {
    "kb_id": 1,
    "organization_id": 1,
    "mission": "Teste"
}

timestamp = $TIMESTAMP
payload_string = json.dumps(payload, sort_keys=True)
message = f"{payload_string}{timestamp}"

signature = hmac.new(
    b'SEU_SECRET_AQUI',
    message.encode('utf-8'),
    hashlib.sha256
).hexdigest()

print(f"Signature: {signature}")
EOF

# Fazer requisição
curl -X POST \
  https://n8n.srv812718.hstgr.cloud/webhook/2f87eab4-40da-4975-a219-74f15dbb2576 \
  -H "Content-Type: application/json" \
  -H "X-API-Key: SEU_SECRET_AQUI" \
  -H "X-Signature: ASSINATURA_GERADA" \
  -H "X-Timestamp: $TIMESTAMP" \
  -d '{"kb_id": 1, "organization_id": 1, "mission": "Teste"}'
```

---

## 🔒 MELHORES PRÁTICAS DE SEGURANÇA

### **1. Gestão de Secrets**

✅ **FAZER:**
- Usar variáveis de ambiente para secrets
- Secrets diferentes por ambiente (dev/prod)
- Rotacionar secrets periodicamente (a cada 90 dias)
- Usar secrets longos (mínimo 32 caracteres)
- Gerar com: `openssl rand -hex 32`

❌ **NÃO FAZER:**
- Hardcode de secrets no código
- Commit de secrets no git
- Compartilhar secrets por email/slack
- Reutilizar secrets entre projetos

### **2. Rate Limiting**

✅ **Configuração Recomendada:**
- **Dev:** 10 req/min por IP, 5 req/min por org
- **Prod:** 5 req/min por IP, 3 req/min por org
- **Burst:** Permitir 2x o limite por 10 segundos

### **3. Logging e Monitoramento**

✅ **Logs Essenciais:**
- Todas as requisições (sucesso e falha)
- Tentativas de autenticação falhadas
- Rate limit exceeded
- Erros de validação
- Tempo de resposta

✅ **Alertas:**
- Mais de 10 falhas de autenticação em 5 minutos
- Rate limit exceeded por mais de 3 IPs diferentes
- Tempo de resposta > 30 segundos
- Erros 500 em mais de 5% das requisições

### **4. Retry Policy**

✅ **Configuração Recomendada:**
- **Max Retries:** 3 (dev), 5 (prod)
- **Delay:** 5s (dev), 10s (prod)
- **Backoff:** Exponencial (5s, 10s, 20s, 40s, 80s)
- **Timeout:** 30s (dev), 60s (prod)

### **5. Validação de Dados**

✅ **Sempre Validar:**
- Tipo de dados (string, int, array)
- Tamanho máximo (prevenir DoS)
- Caracteres permitidos (prevenir injection)
- Estrutura do JSON (schema validation)

---

## 📊 MONITORAMENTO E MÉTRICAS

### **Métricas Essenciais:**

1. **Disponibilidade:**
   - Uptime do webhook
   - Taxa de sucesso (%)
   - Tempo médio de resposta

2. **Segurança:**
   - Tentativas de autenticação falhadas
   - IPs bloqueados
   - Rate limit violations

3. **Performance:**
   - Requisições por minuto
   - Tempo de processamento
   - Tamanho do payload

4. **Negócio:**
   - Análises solicitadas por dia
   - Taxa de conversão (análise → compilação)
   - Organizações ativas

---

## 🚨 PLANO DE RESPOSTA A INCIDENTES

### **Cenário 1: Ataque DDoS**

1. Identificar IPs atacantes (logs)
2. Adicionar IPs à blacklist temporária
3. Reduzir rate limit globalmente
4. Ativar CloudFlare/WAF se disponível
5. Notificar equipe de segurança

### **Cenário 2: Tentativa de Replay Attack**

1. Verificar logs de timestamps duplicados
2. Reduzir janela de tempo (5min → 2min)
3. Bloquear IP temporariamente
4. Investigar origem

### **Cenário 3: Vazamento de Secret**

1. **IMEDIATO:** Rotacionar secret em todos os ambientes
2. Invalidar todas as requisições em andamento
3. Notificar N8N para atualizar secret
4. Investigar como vazou
5. Implementar controles adicionais

---

## ✅ CHECKLIST DE IMPLEMENTAÇÃO

### **Django:**
- [ ] Adicionar variáveis ao `.env`
- [ ] Adicionar configurações ao `settings/base.py`
- [ ] Criar `N8NService` em `services/n8n_service.py`
- [ ] Criar view webhook em `views.py`
- [ ] Adicionar rota em `urls.py`
- [ ] Implementar rate limiting
- [ ] Implementar logging
- [ ] Testes unitários
- [ ] Testes de integração

### **N8N:**
- [ ] Criar workflow "Fundamentos - Análise"
- [ ] Configurar webhook de recebimento
- [ ] Implementar validação de assinatura
- [ ] Configurar lógica de análise
- [ ] Configurar webhook de envio
- [ ] Adicionar variáveis de ambiente
- [ ] Testar fluxo completo
- [ ] Configurar alertas

### **Segurança:**
- [ ] Gerar secrets seguros
- [ ] Configurar IP whitelist
- [ ] Implementar HMAC + timestamp
- [ ] Configurar rate limiting
- [ ] Implementar logging completo
- [ ] Configurar alertas
- [ ] Documentar procedimentos

---

**Documento completo e pronto para implementação.**
