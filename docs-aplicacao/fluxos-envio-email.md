# Fluxos de Envio de Email - IAMKT

**Data:** 01/03/2026  
**Versão:** 1.0  
**Objetivo:** Documentar todos os fluxos de envio de email da aplicação IAMKT

---

## 📊 Resumo Geral

**Total de fluxos:** 8 fluxos principais  
**Uso de variáveis de ambiente:** ✅ Todos os destinatários usam variáveis de ambiente  
**Emails hardcoded:** ⚠️ 3 ocorrências de email de suporte hardcoded

---

## 🔍 Fluxos Detalhados

### 1. Email de Confirmação de Cadastro

**Arquivo:** `apps/core/emails.py` (linhas 36-69)  
**Função:** `send_registration_confirmation(user, organization)`

| Item | Valor |
|------|-------|
| **Destinatário** | `user.email` (email do usuário que se cadastrou) |
| **Remetente** | `settings.DEFAULT_FROM_EMAIL` |
| **Hardcoded?** | ❌ Não - dinâmico |
| **Variável ENV** | `DEFAULT_FROM_EMAIL` |
| **Quando envia** | Após cadastro de novo usuário |
| **Template** | `templates/emails/registration_confirmation.html` |
| **Assunto** | "Cadastro realizado com sucesso - IAMKT" |

**Contexto do template:**
- `user_name`: Nome do usuário ou email
- `user_email`: Email do usuário
- `organization_name`: Nome da organização

**Observações:**
- Email transacional enviado imediatamente após cadastro
- Confirma que o cadastro foi recebido e está aguardando aprovação

---

### 2. Notificação de Novo Cadastro (Equipe IAMKT)

**Arquivo:** `apps/core/emails.py` (linhas 72-117)  
**Função:** `send_registration_notification(user, organization)`

| Item | Valor |
|------|-------|
| **Destinatário** | `get_notification_emails('operacao')` + `get_notification_emails('newuser')` |
| **Remetente** | `settings.DEFAULT_FROM_EMAIL` |
| **Hardcoded?** | ❌ Não |
| **Variável ENV** | `NOTIFICATION_EMAILS_OPERACAO` e `NEWUSER_NOTIFICATION_EMAILS` |
| **Quando envia** | Após cadastro de novo usuário (notifica equipe interna) |
| **Template** | `templates/emails/registration_notification.html` |
| **Assunto** | "[IAMKT] Novo cadastro aguardando aprovação" |

**Contexto do template:**
- `user_name`: Nome completo do usuário
- `user_email`: Email do usuário
- `organization_name`: Nome da organização
- `created_at`: Data/hora do cadastro
- `admin_url`: Link direto para admin da organização

**Configuração no `.env.development`:**
```env
NOTIFICATION_EMAILS_OPERACAO=email1@domain.com,email2@domain.com
NEWUSER_NOTIFICATION_EMAILS=email3@domain.com
```

**Observações:**
- Notifica equipe de operação sobre novos cadastros
- Inclui link direto para aprovação no admin
- Suporta múltiplos destinatários (separados por vírgula)

---

### 3. Email de Organização Aprovada

**Arquivo:** `apps/core/emails.py` (linhas 120-162)  
**Função:** `send_organization_approved_email(organization)`

| Item | Valor |
|------|-------|
| **Destinatário** | `organization.owner.email` |
| **Remetente** | `settings.DEFAULT_FROM_EMAIL` |
| **Hardcoded?** | ❌ Não - dinâmico |
| **Variável ENV** | `DEFAULT_FROM_EMAIL`, `SITE_URL` |
| **Quando envia** | Quando organização é aprovada (via signal) |
| **Template** | `templates/emails/organization_approved.html` |
| **Assunto** | "Sua conta IAMKT foi aprovada! 🎉" |

**Contexto do template:**
- `user_name`: Nome do owner
- `organization_name`: Nome da organização
- `plan_type`: Tipo de plano (display)
- `login_url`: URL de login (`{SITE_URL}/login/`)
- `quota_pautas`: Quota diária de pautas
- `quota_posts_dia`: Quota diária de posts
- `quota_posts_mes`: Quota mensal de posts

**Observações:**
- Enviado automaticamente via Django signal
- Informa quotas e plano configurado
- Inclui link para login

---

### 4. Email de Organização Suspensa

**Arquivo:** `apps/core/emails.py` (linhas 165-213)  
**Função:** `send_organization_suspended_email(organization)`

| Item | Valor |
|------|-------|
| **Destinatário** | `organization.owner.email` |
| **Remetente** | `settings.DEFAULT_FROM_EMAIL` |
| **Hardcoded?** | ⚠️ **SIM** - `support_email: 'suporte@aisuites.com.br'` (linha 193) |
| **Variável ENV** | `DEFAULT_FROM_EMAIL` |
| **Quando envia** | Quando organização é suspensa (via signal) |
| **Template** | `templates/emails/organization_suspended.html` |
| **Assunto** | "Sua conta IAMKT foi suspensa" |

**Contexto do template:**
- `user_name`: Nome do owner
- `organization_name`: Nome da organização
- `suspension_reason`: Motivo da suspensão (display)
- `reason_message`: Mensagem personalizada por motivo
- `support_email`: Email de suporte (**HARDCODED**)

**Motivos de suspensão:**
- `payment`: Problema com pagamento
- `terms`: Violação de termos
- `canceled`: Cancelamento solicitado
- `other`: Outros motivos

**⚠️ Problema identificado:**
- Email de suporte hardcoded: `'suporte@aisuites.com.br'`
- **Recomendação:** Migrar para variável `SUPPORT_EMAIL`

---

### 5. Email de Organização Reativada

**Arquivo:** `apps/core/emails.py` (linhas 216-254)  
**Função:** `send_organization_reactivated_email(organization)`

| Item | Valor |
|------|-------|
| **Destinatário** | `organization.owner.email` |
| **Remetente** | `settings.DEFAULT_FROM_EMAIL` |
| **Hardcoded?** | ❌ Não - dinâmico |
| **Variável ENV** | `DEFAULT_FROM_EMAIL`, `SITE_URL` |
| **Quando envia** | Quando organização é reativada (via signal) |
| **Template** | `templates/emails/organization_reactivated.html` |
| **Assunto** | "Sua conta IAMKT foi reativada! ✅" |

**Contexto do template:**
- `user_name`: Nome do owner
- `organization_name`: Nome da organização
- `login_url`: URL de login (`{SITE_URL}/login/`)

**Observações:**
- Enviado automaticamente via Django signal
- Notifica reativação da conta

---

### 6. Alerta de Quota (80% ou 100%)

**Arquivo:** `apps/core/tasks.py` (linhas 240-269)  
**Função:** `send_quota_alert()` (Celery task)

| Item | Valor |
|------|-------|
| **Destinatário** | `organization.alert_email` ou `settings.DEFAULT_FROM_EMAIL` (fallback) |
| **Remetente** | `settings.DEFAULT_FROM_EMAIL` |
| **Hardcoded?** | ❌ Não - dinâmico |
| **Variável ENV** | `DEFAULT_FROM_EMAIL` |
| **Quando envia** | Quando quota atinge 80% ou 100% |
| **Template** | Email em texto puro (sem template HTML) |
| **Assunto** | "⚠️ Alerta de Quota - {tipo}" |

**Tipos de alerta:**
- `pauta_dia`: Quota diária de pautas
- `post_dia`: Quota diária de posts
- `post_mes`: Quota mensal de posts

**Conteúdo do email:**
- Nome da organização
- Tipo de quota
- Uso atual vs limite
- Percentual utilizado
- Mensagem de alerta

**Observações:**
- Task Celery executada periodicamente
- Registra alerta em `QuotaAlert` model
- Usa campo `alert_email` da organização ou fallback para `DEFAULT_FROM_EMAIL`

---

### 7. Solicitação de Imagem (Nova)

**Arquivo:** `apps/posts/utils.py` (linhas 64-118)  
**Função:** `_notify_image_request_email(post, request=None)`

| Item | Valor |
|------|-------|
| **Destinatário** | `get_notification_emails('gestao')` |
| **Remetente** | `settings.DEFAULT_FROM_EMAIL` |
| **Hardcoded?** | ❌ Não |
| **Variável ENV** | `NOTIFICATION_EMAILS_GESTAO` |
| **Quando envia** | Quando post solicita imagem pela primeira vez |
| **Template** | `templates/emails/post_image_request.html` |
| **Assunto** | "🎨 Nova solicitação de imagem - Post #{post.id}" |

**Contexto do template:**
- `post`: Objeto Post completo
- `organization`: Organização do post
- `post_url`: Link direto para admin do post
- `requested_at`: Data/hora da solicitação
- `deadline`: Prazo de entrega (6 horas úteis)

**Configuração no `.env.development`:**
```env
NOTIFICATION_EMAILS_GESTAO=designer1@domain.com,designer2@domain.com
```

**Observações:**
- Notifica equipe de design sobre nova solicitação
- Calcula prazo de 6 horas úteis
- Inclui link direto para admin do post

---

### 8. Solicitação de Alteração de Imagem

**Arquivo:** `apps/posts/utils.py` (linhas 121-177)  
**Função:** `_notify_revision_request(post, message, payload=None, user=None, request=None)`

| Item | Valor |
|------|-------|
| **Destinatário** | `get_notification_emails('gestao')` |
| **Remetente** | `settings.DEFAULT_FROM_EMAIL` |
| **Hardcoded?** | ❌ Não |
| **Variável ENV** | `NOTIFICATION_EMAILS_GESTAO` |
| **Quando envia** | Quando usuário solicita alteração de imagem |
| **Template** | `templates/emails/post_change_request.html` |
| **Assunto** | "🔄 Solicitação de alteração de imagem - Post #{post.id}" |

**Contexto do template:**
- `post`: Objeto Post completo
- `message`: Mensagem de solicitação de alteração
- `organization`: Organização do post
- `requester_name`: Nome do usuário solicitante
- `post_url`: Link direto para admin do post
- `requested_at`: Data/hora da solicitação
- `deadline`: Prazo de entrega (6 horas úteis)

**Configuração no `.env.development`:**
```env
NOTIFICATION_EMAILS_GESTAO=designer1@domain.com,designer2@domain.com
```

**Observações:**
- Notifica equipe de design sobre solicitação de alteração
- Inclui mensagem do usuário explicando a alteração
- Calcula prazo de 6 horas úteis
- Inclui link direto para admin do post

---

## 📋 Variáveis de Ambiente

### Configuração SMTP

```env
# Servidor SMTP
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=seu_email@gmail.com
EMAIL_HOST_PASSWORD=sua_senha_app

# Remetente padrão
DEFAULT_FROM_EMAIL=noreply@iamkt.com.br
```

### Grupos de Notificação

```env
# Equipe de gestão (design, imagens)
NOTIFICATION_EMAILS_GESTAO=designer1@domain.com,designer2@domain.com

# Equipe de operação (novos cadastros)
NOTIFICATION_EMAILS_OPERACAO=operacao1@domain.com,operacao2@domain.com

# Notificações de posts (não utilizado atualmente)
NOTIFICATION_EMAILS_POSTS=

# Compatibilidade com app antiga (novos usuários)
NEWUSER_NOTIFICATION_EMAILS=admin@domain.com
```

### URLs e Suporte

```env
# URL base da aplicação (para links em emails)
SITE_URL=https://app.iamkt.com.br

# Email de suporte (RECOMENDADO - atualmente hardcoded)
SUPPORT_EMAIL=suporte@aisuites.com.br
```

---

## ⚠️ Emails Hardcoded Identificados

### 1. Email de Suporte

**Ocorrências:** 3 locais

#### a) `apps/core/emails.py` (linha 193)
```python
'support_email': 'suporte@aisuites.com.br',  # ← HARDCODED
```

#### b) `apps/core/views_auth.py` (linha 49)
```python
messages.error(request, 'Sua organização está suspensa. Para mais detalhes, entre em contato com o suporte: suporte@aisuites.com.br')  # ← HARDCODED
```

#### c) `apps/core/models.py` (linhas 724, 741)
```python
return False, 'suspended', 'Essa empresa está suspensa no momento. Para mais detalhes entre em contato com o nosso suporte suporte@aisuites.com.br'  # ← HARDCODED
```

### 2. Email de Suporte em Templates HTML

**Arquivo:** `templates/emails/registration_confirmation.html` (linha 117)
```html
<a href="mailto:suporte@iamkt.com.br">suporte@iamkt.com.br</a>
```

**⚠️ Observação:** Emails diferentes!
- Código Python: `suporte@aisuites.com.br`
- Template HTML: `suporte@iamkt.com.br`

---

## 💡 Recomendações

### 1. Migrar Email de Suporte para Variável de Ambiente

**Adicionar ao `sistema/settings/base.py`:**
```python
SUPPORT_EMAIL = config('SUPPORT_EMAIL', default='suporte@aisuites.com.br')
```

**Adicionar ao `.env.development`:**
```env
SUPPORT_EMAIL=suporte@aisuites.com.br
```

**Substituir nos arquivos:**
- `apps/core/emails.py` → `settings.SUPPORT_EMAIL`
- `apps/core/views_auth.py` → `settings.SUPPORT_EMAIL`
- `apps/core/models.py` → `settings.SUPPORT_EMAIL`
- Templates HTML → `{{ support_email }}` (passar via context)

### 2. Padronizar Email de Suporte

Definir qual email usar:
- `suporte@aisuites.com.br` (usado no código)
- `suporte@iamkt.com.br` (usado em templates)

### 3. Criar Variável para URL do Site em Templates

Alguns templates usam URL hardcoded:
```html
<a href="https://iamkt.aisuites.com.br">iamkt.aisuites.com.br</a>
```

**Recomendação:** Usar `{{ site_url }}` passado via context

---

## 📊 Resumo de Conformidade

| Item | Status | Quantidade |
|------|--------|------------|
| **Destinatários via ENV** | ✅ | 8/8 (100%) |
| **Remetente via ENV** | ✅ | 8/8 (100%) |
| **URLs via ENV** | ✅ | 5/5 (100%) |
| **Email de suporte hardcoded** | ⚠️ | 3 ocorrências |
| **Email de suporte em templates** | ⚠️ | 1 ocorrência |

**Conformidade Geral:** 🟡 **Boa** (apenas email de suporte precisa ser migrado)

---

## 🔧 Função Auxiliar: `get_notification_emails()`

**Arquivo:** `apps/core/emails.py` (linhas 14-33)

```python
def get_notification_emails(group='operacao'):
    """
    Retorna lista de emails para notificação baseado no grupo
    
    Grupos disponíveis:
    - gestao: Notificações estratégicas e aprovações
    - operacao: Notificações operacionais e novos cadastros
    - posts: Notificações sobre posts criados
    - newuser: Compatibilidade com app antiga (novos usuários)
    """
    env_key = f'NOTIFICATION_EMAILS_{group.upper()}'
    emails_str = getattr(settings, env_key, '')
    
    if not emails_str:
        logger.warning(f'Nenhum email configurado para o grupo: {group}')
        return []
    
    # Separar por vírgula e remover espaços
    emails = [email.strip() for email in emails_str.split(',') if email.strip()]
    return emails
```

**Uso:**
```python
# Retorna lista de emails do grupo 'gestao'
recipients = get_notification_emails('gestao')

# Retorna lista de emails dos grupos 'operacao' e 'newuser'
recipients = list(set(
    get_notification_emails('operacao') + 
    get_notification_emails('newuser')
))
```

---

## 📝 Notas de Implementação

### Envio de Emails via Django

Todos os emails usam a função `send_mail()` do Django:

```python
from django.core.mail import send_mail

send_mail(
    subject=subject,
    message=plain_message,        # Versão texto puro
    from_email=settings.DEFAULT_FROM_EMAIL,
    recipient_list=[user.email],  # Lista de destinatários
    html_message=html_message,    # Versão HTML (opcional)
    fail_silently=False,          # Lança exceção em caso de erro
)
```

### Templates HTML

Todos os templates HTML estão em `app/templates/emails/`:
- `registration_confirmation.html`
- `registration_notification.html`
- `organization_approved.html`
- `organization_suspended.html`
- `organization_reactivated.html`
- `post_image_request.html`
- `post_change_request.html`

### Renderização de Templates

```python
from django.template.loader import render_to_string
from django.utils.html import strip_tags

# Renderizar HTML
html_message = render_to_string('emails/template.html', context)

# Gerar versão texto puro (fallback)
plain_message = strip_tags(html_message)
```

---

## 🔍 Troubleshooting

### Email não está sendo enviado

1. Verificar configuração SMTP no `.env.development`
2. Verificar logs: `docker compose logs iamkt_web | grep -i email`
3. Verificar se grupo de notificação está configurado:
   ```python
   from apps.core.emails import get_notification_emails
   print(get_notification_emails('gestao'))
   ```

### Email vai para spam

1. Configurar SPF, DKIM e DMARC no domínio
2. Usar servidor SMTP confiável (ex: SendGrid, AWS SES)
3. Evitar palavras que acionam filtros de spam

### Destinatários não recebem

1. Verificar se emails estão corretos no `.env.development`
2. Verificar se há espaços ou vírgulas extras
3. Testar com `get_notification_emails()` no shell Django

---

**Documento criado em:** 01/03/2026  
**Última atualização:** 01/03/2026  
**Responsável:** Equipe de Desenvolvimento IAMKT
