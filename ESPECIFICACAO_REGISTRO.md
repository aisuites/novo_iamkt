# ESPECIFICAÇÃO COMPLETA - PÁGINA DE REGISTRO
**Data:** 22/01/2026  
**Versão:** 1.0  
**Status:** Especificação para Aprovação

---

## 📋 CONTEXTO E DECISÕES

### **DOIS FLUXOS DISTINTOS**

#### **FLUXO A: Cadastro de Nova Empresa (Implementar AGORA)** ✅
- Usuário novo + Empresa nova
- Página pública `/register/`
- Aprovação manual pela equipe IAMKT
- **Este documento especifica este fluxo**

#### **FLUXO B: Adicionar Usuários em Empresa Existente (Implementar DEPOIS)** 🔄
- Gestor da empresa adiciona novos usuários
- Interface dentro do dashboard (autenticada)
- Usuários já nascem ativos (sem aprovação)
- **Será implementado via front posteriormente**

---

## 🎯 OBJETIVO DO FLUXO A

Permitir que **novos clientes** se cadastrem na plataforma IAMKT, criando:
1. Uma nova **Organização** (empresa)
2. O primeiro **Usuário** (admin da organização)

**Após cadastro:**
- Organização fica pendente de aprovação
- Usuário não pode fazer login
- Equipe IAMKT é notificada
- Após aprovação manual, usuário recebe email e pode acessar

---

## 📄 PÁGINA DE REGISTRO

### **URL**
```
/register/
```

### **Design**
- ✅ **Estilo idêntico à página de login**
- ✅ Layout em 2 colunas:
  - **Esquerda:** Imagem/ilustração (mesma do login)
  - **Direita:** Formulário de cadastro

### **Estrutura Visual**
```
┌─────────────────────────────────────────────────┐
│                                                 │
│  [IMAGEM/LOGO]        │   CRIAR CONTA          │
│  Ilustração           │                        │
│  Marketing            │   [Formulário]         │
│  (mesma do login)     │                        │
│                       │   [Botão Cadastrar]    │
│                       │                        │
│                       │   Já tem conta? Login  │
└─────────────────────────────────────────────────┘
```

---

## 📝 FORMULÁRIO DE CADASTRO

### **Campos Obrigatórios**

1. **Nome Completo**
   - Input: text
   - Placeholder: "João Silva"
   - Validação: Mínimo 3 caracteres
   - Será dividido em `first_name` e `last_name`

2. **Email**
   - Input: email
   - Placeholder: "seu@email.com"
   - Validação: 
     - ✅ Formato de email válido
     - ✅ **Email único** (não pode existir na base)
     - ✅ Mensagem de erro: "Este email já está cadastrado"

3. **Nome da Empresa**
   - Input: text
   - Placeholder: "Minha Empresa Ltda"
   - Validação: Mínimo 3 caracteres
   - Será usado para criar `Organization.name` e `Organization.slug`

4. **Senha**
   - Input: password
   - Placeholder: "••••••••"
   - Validação:
     - ✅ Mínimo 8 caracteres
     - ✅ Pelo menos 1 letra
     - ✅ Pelo menos 1 número
   - Mostrar/ocultar senha (ícone de olho)

5. **Confirmar Senha**
   - Input: password
   - Placeholder: "••••••••"
   - Validação: Deve ser igual à senha
   - Mensagem de erro: "As senhas não coincidem"

### **Campos Opcionais**

6. **Telefone** (opcional)
   - Input: tel
   - Placeholder: "(11) 98765-4321"
   - Máscara: `(XX) XXXXX-XXXX`
   - Validação: Se preenchido, deve ser válido

### **Aceite de Termos**

7. **Checkbox: Aceite dos Termos de Uso**
   - Obrigatório marcar para prosseguir
   - Texto: "Li e aceito os [Termos de Uso](#) e [Política de Privacidade](#)"
   - Links para termos (podem ser # por enquanto)

---

## 🔄 FLUXO DE CADASTRO

### **1. Usuário Preenche Formulário**
- Preenche todos os campos
- Marca aceite de termos
- Clica em "Criar Conta"

### **2. Validações (Frontend)**
- ✅ Todos campos obrigatórios preenchidos
- ✅ Email válido
- ✅ Senhas coincidem
- ✅ Senha forte (mínimo 8 caracteres)
- ✅ Termos aceitos

### **3. Validações (Backend)**
- ✅ **Email único** (não existe na base)
- ✅ Todos campos válidos
- ✅ CSRF token válido

### **4. Criação de Dados**

```python
# 1. Criar Organization (pendente)
organization = Organization.objects.create(
    name="Nome da Empresa",
    slug=slugify("Nome da Empresa"),
    is_active=False,  # Aguardando aprovação
    plan_type='pending',
    suspension_reason='pending',
    quota_pautas_dia=0,
    quota_posts_dia=0,
    quota_posts_mes=0
)

# 2. Criar User (inativo, vinculado à org)
user = User.objects.create(
    username=email,  # Email é o username
    email=email,
    first_name=nome.split()[0],
    last_name=' '.join(nome.split()[1:]),
    organization=organization,
    profile='admin',  # Primeiro usuário é admin da org
    is_active=False  # Aguardando aprovação
)
user.set_password(senha)
user.save()
```

### **5. Envio de Emails**

#### **Email 1: Confirmação para o Usuário**
```
Para: usuario@email.com
Assunto: Cadastro realizado com sucesso - IAMKT

Olá João,

Seu cadastro foi realizado com sucesso! 🎉

Empresa: Minha Empresa Ltda
Email: usuario@email.com

Sua conta está aguardando aprovação pela nossa equipe.
Você receberá um email assim que sua conta for liberada.

Qualquer dúvida, entre em contato: suporte@iamkt.com.br

Atenciosamente,
Equipe IAMKT
```

#### **Email 2: Notificação para Equipe IAMKT**
```
Para: [EMAILS_EQUIPE_IAMKT]  ← Configurável
Assunto: [IAMKT] Novo cadastro aguardando aprovação

Nova solicitação de cadastro:

👤 Nome: João Silva
📧 Email: usuario@email.com
🏢 Empresa: Minha Empresa Ltda
📅 Data: 22/01/2026 17:30

Acesse o admin para aprovar:
https://iamkt.aisuites.com.br/admin/core/organization/

---
Este é um email automático.
```

### **6. Página de Confirmação**

Após cadastro bem-sucedido, redirecionar para página:

```
/register/success/
```

**Conteúdo:**
```
✅ Cadastro realizado com sucesso!

Olá João,

Sua conta foi criada e está aguardando aprovação.

📧 Enviamos um email de confirmação para: usuario@email.com

⏳ Nossa equipe irá revisar seu cadastro em breve.
   Você receberá um email quando sua conta for aprovada.

🔗 Enquanto isso, conheça mais sobre o IAMKT:
   [Link para site institucional]

[Voltar para Login]
```

---

## 📧 SISTEMA DE EMAILS

### **Configuração de Destinatários**

**Problema identificado:**
> "precisamos ter um jeito fácil de alterar esses emails pois a equipe pode sofrer alteração"

**Solução:**

#### **Opção 1: Variável de Ambiente** (RECOMENDADO)
```python
# .env.development
NOTIFICATION_EMAILS=admin@iamkt.com,operacional@iamkt.com,suporte@iamkt.com
```

**Vantagens:**
- ✅ Fácil de alterar (sem deploy)
- ✅ Diferente por ambiente (dev/prod)
- ✅ Não precisa código

#### **Opção 2: Model de Configuração**
```python
class SystemConfig(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    
# No admin:
SystemConfig.objects.create(
    key='notification_emails',
    value='admin@iamkt.com,operacional@iamkt.com'
)
```

**Vantagens:**
- ✅ Editável via admin
- ✅ Histórico de mudanças
- ❌ Mais complexo

**Decisão:** Usar **Opção 1** (variável de ambiente) por simplicidade.

---

## 🔐 VALIDAÇÕES E SEGURANÇA

### **Validação de Email Duplicado**

```python
# views.py
if User.objects.filter(email=email).exists():
    messages.error(request, 'Este email já está cadastrado.')
    return render(request, 'auth/register.html', context)
```

**Mensagem de erro:**
```
❌ Este email já está cadastrado.
   Se você já tem uma conta, faça login.
   [Ir para Login]
```

### **Validação de Senha Forte**

```python
from django.contrib.auth.password_validation import validate_password

try:
    validate_password(password, user=None)
except ValidationError as e:
    messages.error(request, e.messages[0])
```

**Requisitos:**
- Mínimo 8 caracteres
- Não pode ser muito comum (ex: "12345678")
- Não pode ser muito similar ao email/nome

### **CSRF Protection**

```html
<form method="POST">
    {% csrf_token %}
    <!-- campos -->
</form>
```

### **Rate Limiting** (Futuro)

Prevenir spam de cadastros:
- Máximo 3 tentativas por IP por hora
- Implementar posteriormente com django-ratelimit

---

## 🎨 DESIGN E UX

### **Componentes Visuais**

1. **Header**
   - Logo IAMKT
   - Link "Já tem conta? Faça login"

2. **Formulário**
   - Labels claras
   - Placeholders informativos
   - Ícones nos inputs (email, senha, etc)
   - Validação em tempo real (opcional)

3. **Botão de Cadastro**
   - Texto: "Criar Conta"
   - Cor: Primary (roxo)
   - Loading state ao submeter

4. **Links Úteis**
   - "Já tem conta? Faça login"
   - "Termos de Uso"
   - "Política de Privacidade"

### **Estados do Formulário**

1. **Inicial:** Campos vazios
2. **Preenchendo:** Validação em tempo real (opcional)
3. **Erro:** Mensagens de erro em vermelho
4. **Submetendo:** Botão com loading
5. **Sucesso:** Redirect para `/register/success/`

---

## 🚫 O QUE NÃO SERÁ IMPLEMENTADO AGORA

### **Fluxo de Aprovação Automático**
- ❌ Painel de aprovação no admin
- ❌ Botão "Aprovar/Rejeitar"
- ❌ Email de aprovação
- ⏸️ Será implementado apenas com liberação do usuário

**Por enquanto:**
- Admin acessa `/admin/core/organization/`
- Edita manualmente:
  - `is_active = True`
  - `plan_type = 'free'` (ou outro)
  - `quota_pautas_dia = 3`
  - `quota_posts_dia = 3`
  - `quota_posts_mes = 15`
- Edita o usuário:
  - `is_active = True`
- Envia email manualmente (ou não envia)

### **Página de Pagamento**
- ❌ Escolha de plano
- ❌ Integração com gateway de pagamento
- ❌ Aprovação automática após pagamento
- 🔮 Será implementado no futuro

### **Gestão de Usuários (FLUXO B)**
- ❌ Adicionar usuários em empresa existente
- ❌ Interface para gestor
- ❌ Convites por email
- 🔮 Será implementado posteriormente via front

---

## 📊 ESTRUTURA DE ARQUIVOS

### **Templates**
```
app/templates/auth/
  ├── register.html          # Formulário de cadastro
  └── register_success.html  # Página de confirmação
```

### **Views**
```python
# apps/core/views_auth.py
def register_view(request):
    """View de registro de nova empresa + usuário"""
    if request.method == 'POST':
        # Validações
        # Criar organization + user
        # Enviar emails
        # Redirect para success
    return render(request, 'auth/register.html')

def register_success_view(request):
    """Página de confirmação após cadastro"""
    return render(request, 'auth/register_success.html')
```

### **URLs**
```python
# sistema/urls.py
urlpatterns = [
    path('register/', register_view, name='register'),
    path('register/success/', register_success_view, name='register_success'),
]
```

### **Emails**
```python
# apps/core/emails.py
def send_registration_confirmation(user, organization):
    """Envia email de confirmação para o usuário"""
    
def send_registration_notification(user, organization):
    """Envia email de notificação para equipe IAMKT"""
```

### **Forms** (Opcional)
```python
# apps/core/forms.py
class RegistrationForm(forms.Form):
    full_name = forms.CharField(max_length=200)
    email = forms.EmailField()
    company_name = forms.CharField(max_length=200)
    password = forms.CharField(widget=forms.PasswordInput)
    password_confirm = forms.CharField(widget=forms.PasswordInput)
    phone = forms.CharField(required=False)
    accept_terms = forms.BooleanField()
```

---

## ✅ CHECKLIST DE IMPLEMENTAÇÃO

### **Backend**
- [ ] View `register_view` com validações
- [ ] View `register_success_view`
- [ ] Função `send_registration_confirmation`
- [ ] Função `send_registration_notification`
- [ ] Validação de email duplicado
- [ ] Validação de senha forte
- [ ] Criação de Organization (pendente)
- [ ] Criação de User (inativo)
- [ ] Configuração de `NOTIFICATION_EMAILS` no .env

### **Frontend**
- [ ] Template `register.html` (estilo igual ao login)
- [ ] Template `register_success.html`
- [ ] Formulário com todos os campos
- [ ] Validação frontend (JavaScript)
- [ ] Mostrar/ocultar senha
- [ ] Máscara de telefone
- [ ] Loading state no botão
- [ ] Mensagens de erro

### **Emails**
- [ ] Template de email para usuário
- [ ] Template de email para equipe IAMKT
- [ ] Configuração SMTP (se não estiver)
- [ ] Teste de envio de emails

### **Testes**
- [ ] Teste de cadastro bem-sucedido
- [ ] Teste de email duplicado
- [ ] Teste de senha fraca
- [ ] Teste de senhas não coincidem
- [ ] Teste de envio de emails
- [ ] Teste de criação de org + user

---

## 🎯 CRITÉRIOS DE ACEITE

### **Funcional**
- ✅ Usuário consegue acessar `/register/`
- ✅ Formulário valida todos os campos
- ✅ Email duplicado é bloqueado
- ✅ Organization é criada com `is_active=False`
- ✅ User é criado com `is_active=False`
- ✅ Email de confirmação é enviado ao usuário
- ✅ Email de notificação é enviado à equipe IAMKT
- ✅ Página de sucesso é exibida
- ✅ Usuário não consegue fazer login (conta pendente)

### **Visual**
- ✅ Design idêntico à página de login
- ✅ Layout em 2 colunas
- ✅ Responsivo (mobile-friendly)
- ✅ Mensagens de erro claras
- ✅ Loading state no botão

### **Segurança**
- ✅ CSRF protection
- ✅ Senha hasheada
- ✅ Validação de email único
- ✅ Validação de senha forte

---

## 📝 OBSERVAÇÕES IMPORTANTES

### **Brecha Identificada: Sistema de Pagamento**
> "aqui temos uma brecha pois ainda não fizemos o site de 'venda' de assinatura"

**Solução Temporária:**
- Cliente faz cadastro gratuito
- Equipe IAMKT aprova manualmente
- Define plano manualmente (free, basic, premium)
- No futuro: integrar com gateway de pagamento

### **Diferença entre FLUXO A e FLUXO B**

| Aspecto | FLUXO A (Nova Empresa) | FLUXO B (Usuário em Empresa Existente) |
|---------|------------------------|----------------------------------------|
| Quem cria | Próprio usuário | Gestor da empresa |
| Onde | Página pública `/register/` | Dashboard (autenticado) |
| Aprovação | Manual (equipe IAMKT) | Automática (gestor decide) |
| Organization | Cria nova | Usa existente |
| Status inicial | Inativo | Ativo |
| Implementação | **AGORA** | **DEPOIS** |

---

## 🚀 PRÓXIMOS PASSOS

1. **Revisar esta especificação** ✅
2. **Aprovar para implementação** ⏳ (aguardando usuário)
3. **Implementar backend** (4h)
4. **Implementar frontend** (3h)
5. **Implementar emails** (2h)
6. **Testar fluxo completo** (1h)

**Tempo total estimado: ~10 horas**

---

## ❓ PERGUNTAS PARA O USUÁRIO

Antes de implementar, confirme:

1. **Emails da equipe IAMKT:**
   - Quais emails devem receber notificação de novos cadastros?
   - Exemplo: `admin@iamkt.com, operacional@iamkt.com`

2. **Configuração SMTP:**
   - Já tem servidor SMTP configurado?
   - Ou usar serviço externo (SendGrid, Mailgun, etc)?

3. **Termos de Uso:**
   - Já tem documento de Termos de Uso?
   - Ou deixar link como `#` por enquanto?

4. **Design:**
   - Alguma alteração no design do login que deva ser replicada?
   - Cores, logo, ilustração estão OK?

---

**Documento criado em:** 22/01/2026 17:30  
**Versão:** 1.0  
**Status:** Aguardando Aprovação para Implementação  
**Próxima ação:** Usuário revisar e aprovar
