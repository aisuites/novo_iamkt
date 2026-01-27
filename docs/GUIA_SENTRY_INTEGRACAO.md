# 📘 GUIA: Integração com Sentry

**Data:** 27/01/2026  
**Objetivo:** Configurar Sentry para monitoramento de erros em produção

---

## 🎯 BENEFÍCIOS DO SENTRY

1. **Rastreamento de Erros:** Captura e agrupa erros automaticamente
2. **Stack Traces:** Informações detalhadas de cada erro
3. **Performance Monitoring:** APM integrado
4. **Alertas:** Notificações em tempo real
5. **Release Tracking:** Rastreia erros por versão

---

## 📋 PRÉ-REQUISITOS

- Conta Sentry (gratuita ou paga)
- Projeto Django configurado

---

## 🔧 PASSO 1: CRIAR PROJETO NO SENTRY

### **1.1. Acessar Sentry**

```
https://sentry.io/
```

### **1.2. Criar Novo Projeto**

1. Clicar em **Create Project**
2. Selecionar plataforma: **Django**
3. Nome do projeto: `iamkt-production`
4. Team: Selecionar ou criar
5. Clicar em **Create Project**

### **1.3. Copiar DSN**

Copiar o **DSN** (Data Source Name):
```
https://abc123@o123456.ingest.sentry.io/789012
```

---

## 🔧 PASSO 2: INSTALAR SENTRY SDK

### **2.1. Instalar Pacote**

```bash
pip install sentry-sdk
```

### **2.2. Adicionar ao requirements.txt**

```txt
sentry-sdk==1.40.0
```

---

## 🔧 PASSO 3: CONFIGURAR DJANGO

### **3.1. Configurar settings.py**

```python
# settings/base.py

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from decouple import config

# Sentry Configuration
SENTRY_DSN = config('SENTRY_DSN', default='')
SENTRY_ENVIRONMENT = config('SENTRY_ENVIRONMENT', default='production')
SENTRY_RELEASE = config('SENTRY_RELEASE', default='1.0.0')

if SENTRY_DSN and not DEBUG:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=SENTRY_ENVIRONMENT,
        release=SENTRY_RELEASE,
        
        # Integrações
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            RedisIntegration(),
        ],
        
        # Performance Monitoring
        traces_sample_rate=0.1,  # 10% das transações
        
        # Profiling
        profiles_sample_rate=0.1,  # 10% dos profiles
        
        # Filtros
        before_send=before_send_filter,
        
        # Configurações
        send_default_pii=False,  # Não enviar PII
        attach_stacktrace=True,
        max_breadcrumbs=50,
    )


def before_send_filter(event, hint):
    """
    Filtro para eventos antes de enviar ao Sentry
    Remove informações sensíveis
    """
    # Remover informações sensíveis
    if 'request' in event:
        if 'headers' in event['request']:
            # Remover headers sensíveis
            sensitive_headers = ['Authorization', 'Cookie', 'X-CSRFToken']
            for header in sensitive_headers:
                if header in event['request']['headers']:
                    event['request']['headers'][header] = '[Filtered]'
        
        if 'data' in event['request']:
            # Remover campos sensíveis
            sensitive_fields = ['password', 'token', 'secret']
            for field in sensitive_fields:
                if field in event['request']['data']:
                    event['request']['data'][field] = '[Filtered]'
    
    return event
```

### **3.2. Atualizar .env**

```bash
# .env.production
SENTRY_DSN=https://abc123@o123456.ingest.sentry.io/789012
SENTRY_ENVIRONMENT=production
SENTRY_RELEASE=1.0.0
```

---

## 🔧 PASSO 4: CONFIGURAR FRONTEND (JavaScript)

### **4.1. Adicionar Sentry SDK**

```html
<!-- templates/base.html -->
<script
  src="https://browser.sentry-cdn.com/7.99.0/bundle.min.js"
  integrity="sha384-..."
  crossorigin="anonymous"
></script>

<script>
  Sentry.init({
    dsn: "{{ SENTRY_DSN_FRONTEND }}",
    environment: "{{ SENTRY_ENVIRONMENT }}",
    release: "{{ SENTRY_RELEASE }}",
    
    // Performance Monitoring
    tracesSampleRate: 0.1,
    
    // Session Replay
    replaysSessionSampleRate: 0.1,
    replaysOnErrorSampleRate: 1.0,
    
    integrations: [
      new Sentry.BrowserTracing(),
      new Sentry.Replay(),
    ],
  });
</script>
```

### **4.2. Integrar com logger.js**

```javascript
// logger.js

const Logger = {
    error: function(...args) {
        console.error(...args);
        
        // Enviar para Sentry em produção
        if (!this.isDevelopment && window.Sentry) {
            const error = args[0] instanceof Error ? args[0] : new Error(args.join(' '));
            Sentry.captureException(error);
        }
    },
};
```

---

## 🔧 PASSO 5: TESTAR INTEGRAÇÃO

### **5.1. Testar Backend**

```python
# views.py

def test_sentry(request):
    """View de teste para Sentry"""
    division_by_zero = 1 / 0  # Gera erro
```

Acessar: `https://iamkt.com.br/test-sentry/`

### **5.2. Testar Frontend**

```javascript
// Console do navegador
Sentry.captureException(new Error("Teste de erro frontend"));
```

### **5.3. Verificar no Sentry**

Acessar Sentry Dashboard → Issues

Deve aparecer o erro capturado

---

## 🔧 PASSO 6: CONFIGURAR RELEASES

### **6.1. Criar Release no Deploy**

```bash
# scripts/deploy.sh

# Criar release no Sentry
sentry-cli releases new "$VERSION"
sentry-cli releases set-commits "$VERSION" --auto
sentry-cli releases finalize "$VERSION"

# Deploy da aplicação
git pull
python manage.py migrate
python manage.py collectstatic --noinput

# Marcar deploy no Sentry
sentry-cli releases deploys "$VERSION" new -e production
```

### **6.2. Upload de Source Maps (Frontend)**

```bash
# Após build do frontend
sentry-cli releases files "$VERSION" upload-sourcemaps ./static/js/dist
```

---

## 📊 MONITORAMENTO

### **Dashboard Sentry**

**Métricas importantes:**
- **Error Rate:** Taxa de erros
- **Affected Users:** Usuários impactados
- **Crash-Free Sessions:** % de sessões sem crash
- **APDEX Score:** Satisfação do usuário

**Alertas:**
- Configurar alertas por email/Slack
- Threshold: > 10 erros/minuto

---

## 🔒 SEGURANÇA E PRIVACIDADE

### **Configurações Recomendadas**

1. **send_default_pii=False:** Não enviar PII
2. **before_send filter:** Filtrar dados sensíveis
3. **Data Scrubbing:** Ativar no Sentry Dashboard
4. **IP Anonymization:** Anonimizar IPs

### **LGPD/GDPR Compliance**

- Não enviar dados pessoais identificáveis
- Configurar retenção de dados (30-90 dias)
- Permitir exclusão de dados sob solicitação

---

## 💰 CUSTOS

### **Planos Sentry**

| Plano | Eventos/mês | Custo |
|-------|-------------|-------|
| **Developer** | 5.000 | Grátis |
| **Team** | 50.000 | $26/mês |
| **Business** | 100.000 | $80/mês |
| **Enterprise** | Custom | Custom |

**Recomendação:** Começar com Developer, escalar conforme necessário

---

## ✅ CHECKLIST DE IMPLEMENTAÇÃO

- [ ] Criar projeto no Sentry
- [ ] Instalar sentry-sdk
- [ ] Configurar settings.py
- [ ] Adicionar DSN ao .env
- [ ] Configurar before_send filter
- [ ] Integrar frontend (opcional)
- [ ] Testar captura de erros
- [ ] Configurar releases
- [ ] Configurar alertas
- [ ] Revisar configurações de privacidade

---

## 🎯 PRÓXIMOS PASSOS

1. **Performance Monitoring:** Ativar APM
2. **Session Replay:** Gravar sessões de usuários
3. **Custom Tags:** Adicionar tags customizadas
4. **Integração Slack:** Notificações em tempo real

---

**Documentação oficial:**
- [Sentry Django](https://docs.sentry.io/platforms/python/guides/django/)
- [Sentry JavaScript](https://docs.sentry.io/platforms/javascript/)
