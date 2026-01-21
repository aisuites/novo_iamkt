# FLUXO DE CADASTRO E APROVAÇÃO DE USUÁRIOS - IAMKT

## 📋 VISÃO GERAL

Sistema de cadastro com aprovação manual pelo admin antes de liberar acesso à plataforma.

---

## 🔄 FLUXO COMPLETO

### **1. CADASTRO (Página Pública)**

**Usuário acessa:** `/register/`

**Formulário de Cadastro:**
- ✅ Nome completo
- ✅ Email (será o username)
- ✅ Senha + Confirmação de senha
- ✅ Nome da Empresa
- ✅ Telefone (opcional)
- ✅ Aceite dos Termos de Uso

**Ação ao submeter:**
```python
# Criar Organização (status: pendente)
organization = Organization.objects.create(
    name="Nome da Empresa",
    slug=slugify("Nome da Empresa"),
    is_active=False,  # Aguardando aprovação
    plan_type='pending',
    suspension_reason='pending'
)

# Criar Usuário (vinculado à organização)
user = User.objects.create(
    username=email,
    email=email,
    first_name=nome,
    last_name=sobrenome,
    organization=organization,
    profile='admin',  # Primeiro usuário é admin da org
    is_active=False  # Aguardando aprovação
)
user.set_password(senha)
user.save()
```

**Mensagem ao usuário:**
> ✅ Cadastro realizado com sucesso!  
> ⏳ Sua conta está aguardando aprovação.  
> 📧 Você receberá um email quando for aprovada.

---

### **2. AGUARDANDO APROVAÇÃO**

**Status:**
- `User.is_active = False`
- `Organization.is_active = False`
- `Organization.plan_type = 'pending'`
- `Organization.suspension_reason = 'pending'`

**Tentativa de Login:**
```
❌ Sua organização está aguardando aprovação.
   Você será notificado por e-mail quando for aprovada.
```

---

### **3. APROVAÇÃO PELO ADMIN**

**Admin acessa:** `/admin/core/organization/`

**Ações do Admin:**

1. **Revisar dados da organização**
   - Nome da empresa
   - Usuário solicitante
   - Data de cadastro

2. **Definir Plano e Quotas**
   - Plano: Free, Basic, Premium, Custom
   - Quotas diárias: pautas, posts
   - Quotas mensais: posts

3. **Aprovar Organização**
   ```python
   organization.is_active = True
   organization.plan_type = 'free'  # ou outro plano
   organization.suspension_reason = ''
   organization.approved_at = timezone.now()
   organization.approved_by = admin_user
   organization.save()
   ```

4. **Ativar Usuário**
   ```python
   user.is_active = True
   user.save()
   ```

5. **Enviar Email de Aprovação** (TODO)
   ```
   Assunto: Sua conta IAMKT foi aprovada! 🎉
   
   Olá {nome},
   
   Sua conta e a organização "{empresa}" foram aprovadas!
   
   Você já pode acessar a plataforma:
   https://iamkt.aisuites.com.br/login/
   
   Email: {email}
   Plano: {plano}
   
   Bem-vindo ao IAMKT!
   ```

---

### **4. PRIMEIRO LOGIN (Após Aprovação)**

**Usuário acessa:** `/login/`

**Validações:**
1. ✅ Credenciais corretas
2. ✅ Usuário tem organização
3. ✅ Organização está ativa (`is_active=True`)
4. ✅ Login permitido

**Fluxo:**
1. Login bem-sucedido
2. **Modal de Boas-vindas** aparece (primeira visita)
3. Sugestão: Preencher Base de Conhecimento
4. Redirecionamento para Dashboard

---

### **5. PRÓXIMOS PASSOS (Usuário Aprovado)**

1. **Preencher Base de Conhecimento**
   - Informações da empresa
   - Público-alvo
   - Paleta de cores
   - Identidade visual

2. **Explorar Ferramentas**
   - Criar pautas
   - Gerar posts
   - Acompanhar tendências

3. **Gerenciar Quotas**
   - Acompanhar uso diário/mensal
   - Solicitar upgrade de plano (futuro)

---

## 🗂️ ESTRUTURA DE DADOS

### **Organization (Pendente)**
```python
{
    'name': 'Empresa XYZ',
    'slug': 'empresa-xyz',
    'is_active': False,
    'plan_type': 'pending',
    'suspension_reason': 'pending',
    'quota_pautas_dia': 0,
    'quota_posts_dia': 0,
    'quota_posts_mes': 0,
    'approved_at': None,
    'approved_by': None
}
```

### **Organization (Aprovada)**
```python
{
    'name': 'Empresa XYZ',
    'slug': 'empresa-xyz',
    'is_active': True,
    'plan_type': 'free',
    'suspension_reason': '',
    'quota_pautas_dia': 3,
    'quota_posts_dia': 3,
    'quota_posts_mes': 15,
    'approved_at': '2026-01-21 19:00:00',
    'approved_by': <User: admin>
}
```

### **User**
```python
{
    'username': 'usuario@empresa.com',
    'email': 'usuario@empresa.com',
    'first_name': 'João',
    'last_name': 'Silva',
    'organization': <Organization: Empresa XYZ>,
    'profile': 'admin',
    'is_active': True,  # False até aprovação
    'is_staff': False,
    'is_superuser': False
}
```

---

## 📝 TAREFAS PENDENTES (Para Implementação Futura)

### **Página de Registro**
- [ ] Criar formulário de cadastro (`/register/`)
- [ ] Validação de email único
- [ ] Validação de senha forte
- [ ] Aceite de termos de uso
- [ ] Criar organização + usuário automaticamente
- [ ] Página de confirmação "Aguardando aprovação"

### **Painel de Aprovação (Admin)**
- [ ] Listagem de organizações pendentes
- [ ] Botão "Aprovar" com modal para definir plano
- [ ] Botão "Rejeitar" com campo de motivo
- [ ] Envio de email de aprovação/rejeição
- [ ] Log de auditoria (quem aprovou, quando)

### **Notificações**
- [ ] Email de confirmação de cadastro
- [ ] Email de aprovação
- [ ] Email de rejeição (se aplicável)
- [ ] Notificação para admin quando novo cadastro

### **Melhorias de UX**
- [ ] Página de status "Aguardando aprovação"
- [ ] Contador de tempo desde o cadastro
- [ ] Link para suporte/contato

---

## 🎯 REFERÊNCIAS DA APLICAÇÃO ANTIGA

**IMPORTANTE:** Antes de implementar, o usuário fornecerá:
- ✅ Telas da aplicação antiga
- ✅ Fluxo de cadastro existente
- ✅ Emails de notificação
- ✅ Validações e regras de negócio

**NÃO INVENTAR NADA!** Seguir exatamente o padrão da aplicação antiga.

---

## 🔐 SEGURANÇA

- ✅ Senha hasheada (Django default)
- ✅ CSRF protection em formulários
- ✅ Validação de email único
- ✅ Aprovação manual obrigatória
- ✅ Isolamento por organização
- ✅ Logs de auditoria (futuro)

---

## 📊 ESTADOS DO SISTEMA

| Estado | User.is_active | Org.is_active | Org.plan_type | Pode Logar? |
|--------|----------------|---------------|---------------|-------------|
| Cadastro Pendente | False | False | pending | ❌ Não |
| Aprovado | True | True | free/basic/premium | ✅ Sim |
| Rejeitado | False | False | pending | ❌ Não |
| Suspenso | True | False | (qualquer) | ❌ Não |

---

**Documento criado em:** 21/01/2026  
**Versão:** 1.0  
**Status:** Planejamento - Aguardando referências da aplicação antiga
