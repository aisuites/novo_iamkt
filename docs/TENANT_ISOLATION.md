# 🔒 TENANT ISOLATION - Guia Completo

**Data:** 2025-01-20  
**Status:** ✅ Implementado e Funcional

---

## 🎯 O que é Tenant Isolation?

Sistema que garante que **cada organização (tenant) só acesse seus próprios dados**, prevenindo vazamento de informações entre diferentes empresas/clientes.

---

## 📦 Componentes Implementados

### 1. **Middleware** (`apps/core/middleware.py`)

#### **TenantMiddleware**
Detecta a organization do usuário logado e injeta no request.

```python
# Automático - não precisa fazer nada!
# Em qualquer view:
def my_view(request):
    org = request.organization  # ← Disponível automaticamente
    print(org.name)  # "IAMKT"
```

#### **TenantIsolationMiddleware**
Adiciona headers de segurança e validações.

**Headers adicionados:**
- `X-Tenant-ID`: ID da organization
- `X-Tenant-Slug`: Slug da organization

---

### 2. **Managers Customizados** (`apps/core/managers.py`)

#### **OrganizationScopedManager** (Recomendado)

Filtra **automaticamente** por organization. Ideal para models críticas.

```python
# Na model:
class Post(models.Model):
    organization = models.ForeignKey(Organization, ...)
    objects = OrganizationScopedManager()  # ← Manager customizado

# Uso em views:
posts = Post.objects.all()  # ← Filtra automaticamente!
# Equivalente a: Post.objects.filter(organization=request.organization)
```

**Métodos disponíveis:**

```python
# Filtrar por organization específica
Post.objects.for_organization(org)

# Filtrar pela organization do request
Post.objects.for_request(request)

# Acesso administrativo (sem filtro) - USE COM CUIDADO!
Post.objects.all_tenants()
```

#### **TenantManager** (Alternativo)

Manager mais flexível, mas requer configuração manual.

```python
class MyModel(models.Model):
    organization = models.ForeignKey(Organization, ...)
    objects = TenantManager()

# Uso:
MyModel.objects.for_organization(org).all()
```

---

### 3. **Context Processors** (`apps/core/context_processors.py`)

Adiciona `organization` a todos os templates automaticamente.

**Uso nos templates:**

```django
{# Verificar se tem organization #}
{% if organization %}
    <h1>Bem-vindo à {{ organization.name }}</h1>
    <p>Plano: {{ organization.plan_type }}</p>
{% endif %}

{# Alias 'tenant' também funciona #}
{% if tenant %}
    <p>Organização: {{ tenant.slug }}</p>
{% endif %}
```

---

### 4. **Decorators** (`apps/core/decorators.py`)

#### **@require_organization**

Bloqueia acesso se usuário não tem organization.

```python
from apps.core.decorators import require_organization

@require_organization
def my_view(request):
    # request.organization está garantido aqui
    posts = Post.objects.for_request(request)
    return render(request, 'posts.html', {'posts': posts})
```

#### **@organization_required**

Redireciona se usuário não tem organization.

```python
from apps.core.decorators import organization_required

@organization_required(redirect_url='/sem-acesso/')
def my_view(request):
    # ...
```

#### **@tenant_scoped_view**

Adiciona helpers ao request.

```python
from apps.core.decorators import tenant_scoped_view

@tenant_scoped_view
def my_view(request):
    org = request.organization  # Garantido
    tenant = request.tenant  # Alias
    # ...
```

#### **@superuser_or_organization**

Permite acesso a superusers ou usuários com organization.

```python
from apps.core.decorators import superuser_or_organization

@superuser_or_organization
def admin_view(request):
    # Superusers sempre têm acesso
    # Usuários normais precisam de organization
    # ...
```

---

## 🚀 Como Usar

### **Em Models**

```python
from django.db import models
from apps.core.managers import OrganizationScopedManager

class MeuModel(models.Model):
    organization = models.ForeignKey(
        'core.Organization',
        on_delete=models.CASCADE,
        related_name='meus_models'
    )
    nome = models.CharField(max_length=200)
    
    # Manager com filtro automático
    objects = OrganizationScopedManager()
    
    class Meta:
        verbose_name = 'Meu Model'
```

### **Em Views**

```python
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from apps.core.decorators import require_organization
from .models import MeuModel

@login_required
@require_organization
def minha_view(request):
    # Queries automáticas filtram por organization
    items = MeuModel.objects.all()  # ← Apenas da org do usuário!
    
    # Ou explicitamente:
    items = MeuModel.objects.for_request(request)
    
    # Ou por organization específica:
    org = request.organization
    items = MeuModel.objects.for_organization(org)
    
    return render(request, 'template.html', {
        'items': items,
        # 'organization' já está disponível no template!
    })
```

### **Em Templates**

```django
{% extends "base/base.html" %}

{% block content %}
    <h1>{{ organization.name }}</h1>
    
    {% if organization.plan_type == 'premium' %}
        <span class="badge">Premium</span>
    {% endif %}
    
    <ul>
    {% for item in items %}
        <li>{{ item.nome }}</li>
    {% endfor %}
    </ul>
{% endblock %}
```

---

## ⚠️ IMPORTANTE: Segurança

### **✅ FAZER (Seguro)**

```python
# Manager filtra automaticamente
posts = Post.objects.all()

# Filtro explícito por request
posts = Post.objects.for_request(request)

# Filtro por organization específica
posts = Post.objects.for_organization(org)
```

### **❌ NÃO FAZER (Inseguro)**

```python
# NUNCA use all_tenants() em views públicas!
posts = Post.objects.all_tenants()  # ← VAZAMENTO DE DADOS!

# NUNCA ignore o filtro de organization
posts = Post._default_manager.all()  # ← PERIGOSO!
```

### **⚠️ Quando usar all_tenants()**

Apenas em:
- Tasks administrativas (Celery)
- Migrations de dados
- Relatórios globais (apenas para superusers)
- Scripts de manutenção

```python
# Exemplo seguro em task administrativa
@shared_task
def cleanup_old_data():
    # OK aqui - é task administrativa
    old_posts = Post.objects.all_tenants().filter(
        created_at__lt=one_year_ago
    )
    old_posts.delete()
```

---

## 🧪 Testando Isolamento

### **Teste Manual**

1. Criar duas organizations:
```python
org1 = Organization.objects.create(name='Empresa A', slug='empresa-a')
org2 = Organization.objects.create(name='Empresa B', slug='empresa-b')
```

2. Criar usuários em cada organization:
```python
user1 = User.objects.create(username='user1', organization=org1)
user2 = User.objects.create(username='user2', organization=org2)
```

3. Criar posts:
```python
Post.objects.create(organization=org1, caption='Post da Empresa A')
Post.objects.create(organization=org2, caption='Post da Empresa B')
```

4. Verificar isolamento:
```python
# Login como user1
posts = Post.objects.for_organization(org1)
print(posts.count())  # Deve ser 1 (apenas posts da Empresa A)

# Login como user2
posts = Post.objects.for_organization(org2)
print(posts.count())  # Deve ser 1 (apenas posts da Empresa B)
```

---

## 📊 Models com Tenant Isolation

**✅ Já implementado:**
- `Pauta`
- `Post`
- `Asset`
- `VideoAvatar`

**⏳ Para implementar (se necessário):**
- `TrendMonitor`
- `WebInsight`
- `IAModelUsage`
- `ContentMetrics`
- `Project`

**Como adicionar em novas models:**

```python
from apps.core.managers import OrganizationScopedManager

class NovaModel(models.Model):
    organization = models.ForeignKey('core.Organization', ...)
    # ... outros campos ...
    
    # Adicionar manager
    objects = OrganizationScopedManager()
```

---

## 🔧 Troubleshooting

### **Erro: "Usuário não está vinculado a nenhuma organização"**

**Causa:** Usuário não tem `organization` definida.

**Solução:**
```python
user = User.objects.get(username='...')
user.organization = Organization.objects.get(slug='iamkt')
user.save()
```

### **Queries retornam vazio**

**Causa:** Manager está filtrando por organization, mas não há dados.

**Debug:**
```python
# Ver se há dados sem filtro
Post.objects.all_tenants().count()

# Ver organization do usuário
print(request.organization)

# Ver se posts têm organization
Post.objects.all_tenants().values('organization_id')
```

### **Headers X-Tenant-ID não aparecem**

**Causa:** Middleware não está configurado ou usuário não está autenticado.

**Verificar:**
1. Middleware está em `settings.py`?
2. Usuário está logado?
3. URL não é pública?

---

## 📝 Checklist de Implementação

Para adicionar tenant isolation em uma nova model:

- [ ] Adicionar campo `organization` (FK para Organization)
- [ ] Adicionar `objects = OrganizationScopedManager()`
- [ ] Criar migration
- [ ] Aplicar migration
- [ ] Vincular dados existentes à organization
- [ ] Testar queries
- [ ] Atualizar views para usar `for_request()`
- [ ] Adicionar decorator `@require_organization` nas views

---

## 🎯 Benefícios

✅ **Segurança:** Previne vazamento de dados entre tenants  
✅ **Automático:** Filtros aplicados por padrão  
✅ **Fácil de usar:** Queries normais funcionam  
✅ **Debugging:** Headers X-Tenant-ID para rastreamento  
✅ **Flexível:** Métodos para casos especiais  
✅ **Testável:** Fácil de testar isolamento  

---

**Última atualização:** 2025-01-20 21:45:00
