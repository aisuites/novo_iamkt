# 📘 GUIA: Configuração de CDN com CloudFront

**Data:** 27/01/2026  
**Objetivo:** Configurar CloudFront para servir static files com cache e performance otimizada

---

## 🎯 BENEFÍCIOS DO CDN

1. **Performance:** Arquivos servidos de edge locations próximas ao usuário
2. **Cache:** Reduz carga no servidor de origem
3. **Banda:** Reduz custos de transferência de dados
4. **Disponibilidade:** Alta disponibilidade global

---

## 📋 PRÉ-REQUISITOS

- Conta AWS ativa
- Bucket S3 configurado para static files
- Django configurado com `collectstatic`

---

## 🔧 PASSO 1: CRIAR DISTRIBUIÇÃO CLOUDFRONT

### **1.1. Acessar CloudFront Console**

```
https://console.aws.amazon.com/cloudfront/
```

### **1.2. Criar Nova Distribuição**

**Configurações básicas:**
- **Origin Domain:** `iamkt-assets.s3.amazonaws.com`
- **Origin Path:** `/static` (opcional)
- **Name:** `iamkt-static-files`

**Origin Settings:**
- **S3 bucket access:** Yes, use OAI (Origin Access Identity)
- **Create new OAI:** Sim
- **Bucket policy:** Yes, update automatically

**Default Cache Behavior:**
- **Viewer Protocol Policy:** Redirect HTTP to HTTPS
- **Allowed HTTP Methods:** GET, HEAD, OPTIONS
- **Cache Policy:** CachingOptimized
- **Compress Objects Automatically:** Yes

**Distribution Settings:**
- **Price Class:** Use Only North America and Europe (ou All Edge Locations)
- **Alternate Domain Names (CNAMEs):** `static.iamkt.com.br` (opcional)
- **SSL Certificate:** Default CloudFront Certificate (ou custom)

### **1.3. Criar Distribuição**

Clique em **Create Distribution**

Aguardar deploy (~15-20 minutos)

---

## 🔧 PASSO 2: CONFIGURAR DJANGO

### **2.1. Instalar django-storages**

```bash
pip install django-storages boto3
```

### **2.2. Configurar settings.py**

```python
# settings/production.py

# AWS S3 Configuration
AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME', default='iamkt-assets')
AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='us-east-1')

# CloudFront Configuration
AWS_S3_CUSTOM_DOMAIN = config(
    'AWS_CLOUDFRONT_DOMAIN',
    default='d1234567890abc.cloudfront.net'  # Seu domínio CloudFront
)

# Static files via CloudFront
STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/static/'
STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

# Cache headers
AWS_S3_OBJECT_PARAMETERS = {
    'CacheControl': 'max-age=86400',  # 1 dia
}

# Compressor com S3
COMPRESS_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
COMPRESS_URL = STATIC_URL
COMPRESS_OFFLINE = True
```

### **2.3. Atualizar .env**

```bash
# .env.production
AWS_CLOUDFRONT_DOMAIN=d1234567890abc.cloudfront.net
```

---

## 🔧 PASSO 3: DEPLOY DE STATIC FILES

### **3.1. Coletar Static Files**

```bash
python manage.py collectstatic --noinput
```

Arquivos serão enviados para S3 e servidos via CloudFront

### **3.2. Comprimir Assets (Opcional)**

```bash
python manage.py compress --force
```

---

## 🔧 PASSO 4: CONFIGURAR CACHE INVALIDATION

### **4.1. Criar Script de Invalidação**

```python
# scripts/invalidate_cloudfront.py

import boto3
import time
from decouple import config

def invalidate_cloudfront_cache(paths=['/*']):
    """
    Invalida cache do CloudFront
    
    Args:
        paths: Lista de paths a invalidar (default: todos)
    """
    cloudfront = boto3.client('cloudfront')
    distribution_id = config('AWS_CLOUDFRONT_DISTRIBUTION_ID')
    
    response = cloudfront.create_invalidation(
        DistributionId=distribution_id,
        InvalidationBatch={
            'Paths': {
                'Quantity': len(paths),
                'Items': paths
            },
            'CallerReference': str(time.time())
        }
    )
    
    print(f"Invalidação criada: {response['Invalidation']['Id']}")
    print(f"Status: {response['Invalidation']['Status']}")

if __name__ == '__main__':
    # Invalidar apenas CSS e JS
    invalidate_cloudfront_cache([
        '/static/css/*',
        '/static/js/*'
    ])
```

### **4.2. Usar no Deploy**

```bash
# Após collectstatic
python scripts/invalidate_cloudfront.py
```

---

## 🔧 PASSO 5: CONFIGURAR VERSIONAMENTO

### **5.1. Usar ManifestStaticFilesStorage**

```python
# settings/production.py

STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

# Ou com S3
STATICFILES_STORAGE = 'storages.backends.s3boto3.S3ManifestStaticStorage'
```

Gera arquivos com hash no nome: `style.abc123.css`

### **5.2. Vantagens**

- Cache infinito (arquivos nunca mudam)
- Sem necessidade de invalidação
- Melhor performance

---

## 📊 MONITORAMENTO

### **Métricas CloudFront**

Acessar CloudFront Console → Monitoring

**Métricas importantes:**
- **Requests:** Total de requisições
- **Bytes Downloaded:** Banda transferida
- **Error Rate:** Taxa de erros (4xx, 5xx)
- **Cache Hit Rate:** % de hits no cache

**Meta:** Cache Hit Rate > 80%

---

## 💰 CUSTOS ESTIMADOS

### **CloudFront Pricing (us-east-1)**

| Tráfego/mês | Custo/GB | Custo Total |
|-------------|----------|-------------|
| Primeiros 10 TB | $0.085 | $850 |
| 10-50 TB | $0.080 | - |
| 50-150 TB | $0.060 | - |

**Requests:**
- HTTP: $0.0075 por 10.000 requests
- HTTPS: $0.0100 por 10.000 requests

**Exemplo:**
- 1 TB/mês + 10M requests = ~$95/mês

---

## 🔒 SEGURANÇA

### **Configurações Recomendadas**

1. **HTTPS Only:** Redirecionar HTTP para HTTPS
2. **OAI (Origin Access Identity):** Acesso ao S3 apenas via CloudFront
3. **Geo Restriction:** Bloquear países se necessário
4. **WAF:** Adicionar AWS WAF para proteção DDoS

---

## ✅ CHECKLIST DE IMPLEMENTAÇÃO

- [ ] Criar distribuição CloudFront
- [ ] Configurar OAI para S3
- [ ] Atualizar settings.py com CloudFront domain
- [ ] Instalar django-storages
- [ ] Executar collectstatic
- [ ] Testar acesso aos static files
- [ ] Configurar versionamento (ManifestStaticFilesStorage)
- [ ] Criar script de invalidação
- [ ] Monitorar métricas
- [ ] Configurar alertas

---

## 🎯 PRÓXIMOS PASSOS

1. **Custom Domain:** Configurar `static.iamkt.com.br`
2. **SSL Certificate:** Adicionar certificado SSL custom
3. **Multiple Origins:** Separar static files e media files
4. **Lambda@Edge:** Otimizações avançadas

---

**Documentação oficial:**
- [CloudFront Getting Started](https://docs.aws.amazon.com/cloudfront/latest/DeveloperGuide/GettingStarted.html)
- [django-storages](https://django-storages.readthedocs.io/)
