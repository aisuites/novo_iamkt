# BACKLOG ITEM: Usuário Pertencer a Múltiplas Organizações

**Data de Criação:** 21/01/2026  
**Prioridade:** Média  
**Complexidade:** Alta  
**Status:** Planejamento

---

## 📋 DESCRIÇÃO

Permitir que um usuário possa pertencer a múltiplas organizações simultaneamente, com seleção da organização ativa no momento do login.

**Cenário de uso:**
- Consultor que atende múltiplas empresas
- Funcionário que trabalha em mais de uma empresa do grupo
- Agência que gerencia contas de múltiplos clientes

---

## 🎯 OBJETIVO

Transformar o relacionamento `User → Organization` de **1:1** para **N:N** (muitos-para-muitos), permitindo que:
1. Usuário faça login e escolha qual organização acessar
2. Sessão mantenha organização ativa
3. Usuário possa trocar de organização sem fazer logout
4. Cada organização mantenha isolamento de dados

---

## 📊 ANÁLISE DE COMPLEXIDADE

### **Complexidade Geral: ALTA** ⚠️

| Componente | Complexidade | Impacto | Esforço |
|------------|--------------|---------|---------|
| Model User | Média | Alto | 2h |
| Login Flow | Alta | Alto | 4h |
| Session Management | Alta | Crítico | 3h |
| Middleware | Média | Crítico | 2h |
| UI/UX | Média | Médio | 3h |
| Testes | Alta | Alto | 4h |
| **TOTAL** | **Alta** | **Crítico** | **~18h** |

---

## 🔧 MUDANÇAS NECESSÁRIAS

### **1. MODEL: User → Organizations (N:N)**

**Atual (1:1):**
```python
class User(AbstractUser):
    organization = models.ForeignKey(
        'Organization',
        on_delete=models.CASCADE,
        related_name='users',
        null=True,
        blank=True
    )
```

**Proposto (N:N):**
```python
class User(AbstractUser):
    organizations = models.ManyToManyField(
        'Organization',
        through='UserOrganization',
        related_name='users',
        blank=True
    )
    
    # Organização padrão (primeira que aparece no seletor)
    default_organization = models.ForeignKey(
        'Organization',
        on_delete=models.SET_NULL,
        related_name='default_users',
        null=True,
        blank=True
    )

class UserOrganization(models.Model):
    """
    Tabela intermediária para relacionamento User-Organization
    Permite adicionar metadados (role, data de entrada, etc)
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    role = models.CharField(max_length=50, default='member')  # member, admin, owner
    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['user', 'organization']
```

**Migration:**
- Criar `UserOrganization` model
- Migrar dados existentes: `user.organization` → `user.organizations.add()`
- Remover campo `organization` (ou manter deprecated)
- Adicionar `default_organization`

**Impacto:** 🔴 ALTO - Quebra compatibilidade com código existente

---

### **2. LOGIN FLOW: Seleção de Organização**

**Fluxo Atual:**
```
Login (email + senha) → Validar credenciais → Validar org → Dashboard
```

**Fluxo Proposto:**
```
Login (email + senha) → Validar credenciais → 
    ↓
Tem múltiplas orgs?
    ├─ Sim → Tela de seleção de organização → Setar org na sessão → Dashboard
    └─ Não → Setar única org na sessão → Dashboard
```

**Tela de Seleção de Organização:**
```html
<div class="org-selector">
  <h2>Selecione a Organização</h2>
  <p>Você tem acesso a múltiplas organizações. Escolha qual deseja acessar:</p>
  
  <div class="org-list">
    {% for user_org in user.userorganization_set.all %}
      <div class="org-card" onclick="selectOrg({{ user_org.organization.id }})">
        <h3>{{ user_org.organization.name }}</h3>
        <p>{{ user_org.get_role_display }}</p>
        <span class="badge">{{ user_org.organization.plan_type }}</span>
      </div>
    {% endfor %}
  </div>
</div>
```

**Nova View:**
```python
@login_required
def select_organization(request):
    """
    View para seleção de organização após login
    """
    if request.method == 'POST':
        org_id = request.POST.get('organization_id')
        
        # Validar que usuário tem acesso a essa org
        if request.user.organizations.filter(id=org_id).exists():
            request.session['active_organization_id'] = org_id
            return redirect('core:dashboard')
        else:
            messages.error(request, 'Organização inválida')
    
    user_orgs = request.user.userorganization_set.select_related('organization')
    return render(request, 'auth/select_organization.html', {
        'user_orgs': user_orgs
    })
```

**Impacto:** 🟡 MÉDIO - Adiciona nova tela no fluxo de login

---

### **3. SESSION MANAGEMENT: Organização Ativa**

**Atual:**
```python
# Middleware seta organization do user
request.organization = request.user.organization
```

**Proposto:**
```python
# Middleware busca organization ativa da sessão
active_org_id = request.session.get('active_organization_id')
if active_org_id:
    request.organization = Organization.objects.get(id=active_org_id)
else:
    # Fallback: usar default_organization
    request.organization = request.user.default_organization
```

**Trocar de Organização (sem logout):**
```python
@login_required
def switch_organization(request, org_id):
    """
    Permite trocar de organização sem fazer logout
    """
    # Validar acesso
    if request.user.organizations.filter(id=org_id).exists():
        request.session['active_organization_id'] = org_id
        messages.success(request, f'Organização alterada para {org.name}')
        return redirect('core:dashboard')
    else:
        messages.error(request, 'Você não tem acesso a essa organização')
        return redirect('core:dashboard')
```

**Widget no Header:**
```html
<div class="org-switcher">
  <button class="current-org">
    {{ request.organization.name }} ▼
  </button>
  <div class="org-dropdown">
    {% for user_org in request.user.userorganization_set.all %}
      <a href="{% url 'switch_organization' user_org.organization.id %}">
        {{ user_org.organization.name }}
        {% if user_org.organization.id == request.organization.id %}✓{% endif %}
      </a>
    {% endfor %}
  </div>
</div>
```

**Impacto:** 🔴 ALTO - Mudança crítica no middleware

---

### **4. MIDDLEWARE: TenantMiddleware Atualizado**

**Atual:**
```python
class TenantMiddleware:
    def __call__(self, request):
        if request.user.is_authenticated:
            request.organization = request.user.organization
```

**Proposto:**
```python
class TenantMiddleware:
    def __call__(self, request):
        if request.user.is_authenticated:
            # Buscar org ativa da sessão
            active_org_id = request.session.get('active_organization_id')
            
            if active_org_id:
                try:
                    # Validar que user tem acesso a essa org
                    request.organization = request.user.organizations.get(id=active_org_id)
                except Organization.DoesNotExist:
                    # Org inválida, limpar sessão e usar default
                    del request.session['active_organization_id']
                    request.organization = request.user.default_organization
            else:
                # Sem org na sessão, usar default
                request.organization = request.user.default_organization
            
            # Se não tem default, redirecionar para seleção
            if not request.organization:
                # Redirecionar para select_organization
                pass
```

**Impacto:** 🔴 ALTO - Componente crítico do sistema

---

### **5. UI/UX: Seletor de Organização**

**Componentes necessários:**

1. **Tela de Seleção (após login)**
   - Lista de organizações com cards
   - Informações: Nome, Plano, Role do usuário
   - Botão de seleção

2. **Dropdown no Header (trocar org)**
   - Organização atual
   - Lista de outras organizações
   - Indicador visual da org ativa

3. **Página de Gerenciamento**
   - Listar todas as organizações do usuário
   - Definir organização padrão
   - Sair de uma organização (se permitido)

**Impacto:** 🟡 MÉDIO - Novas telas e componentes

---

### **6. VALIDAÇÕES E REGRAS DE NEGÓCIO**

**Regras a implementar:**

1. **Usuário deve ter pelo menos 1 organização**
   - Não pode remover última organização
   - Validação no admin e nas views

2. **Organização padrão deve ser uma das organizações do usuário**
   - Validação no model
   - Auto-ajuste se organização for removida

3. **Isolamento de dados mantido**
   - OrganizationScopedManager continua funcionando
   - Queries filtram pela `request.organization` (sessão)

4. **Permissões por organização**
   - Usuário pode ter roles diferentes em cada org
   - Admin em uma, member em outra

5. **Quotas por organização**
   - Cada org tem suas próprias quotas
   - Uso de quotas isolado por org

**Impacto:** 🟡 MÉDIO - Lógica de negócio adicional

---

### **7. TESTES**

**Testes necessários:**

```python
class MultiOrgUserTestCase(TestCase):
    def test_user_can_belong_to_multiple_orgs(self):
        """Usuário pode pertencer a múltiplas organizações"""
        
    def test_user_can_switch_organizations(self):
        """Usuário pode trocar de organização sem logout"""
        
    def test_data_isolation_maintained(self):
        """Dados continuam isolados por organização"""
        
    def test_user_cannot_access_org_without_permission(self):
        """Usuário não acessa org que não pertence"""
        
    def test_default_organization_fallback(self):
        """Sistema usa default_organization se sessão vazia"""
        
    def test_login_with_single_org_skips_selection(self):
        """Login com 1 org pula tela de seleção"""
        
    def test_login_with_multiple_orgs_shows_selection(self):
        """Login com múltiplas orgs mostra seleção"""
```

**Impacto:** 🔴 ALTO - Cobertura de testes crítica

---

## 🚧 RISCOS E DESAFIOS

### **Riscos Técnicos:**

1. **Quebra de Compatibilidade** 🔴
   - Código existente usa `user.organization` (singular)
   - Precisa refatorar TODAS as referências
   - Estimativa: ~50 arquivos afetados

2. **Complexidade de Sessão** 🔴
   - Sessão pode ficar inconsistente
   - Usuário pode tentar acessar org que foi removida
   - Precisa validação robusta

3. **Performance** 🟡
   - Queries adicionais para buscar organizações do usuário
   - Middleware mais pesado
   - Solução: Cache de organizações do usuário

4. **Isolamento de Dados** 🔴
   - Risco de vazamento de dados entre orgs
   - Middleware DEVE setar org correta
   - Testes extensivos necessários

### **Riscos de Negócio:**

1. **UX Complexa** 🟡
   - Usuários podem se confundir com múltiplas orgs
   - Precisa indicadores visuais claros
   - Documentação e onboarding

2. **Suporte** 🟡
   - Mais casos de uso para suportar
   - Usuários podem não saber em qual org estão
   - Logs detalhados necessários

---

## 📈 ESTIMATIVA DE ESFORÇO

| Tarefa | Tempo | Complexidade |
|--------|-------|--------------|
| 1. Refatorar Model User (N:N) | 2h | Média |
| 2. Criar UserOrganization model | 1h | Baixa |
| 3. Migration de dados | 1h | Média |
| 4. Atualizar Middleware | 2h | Alta |
| 5. Criar tela de seleção de org | 2h | Média |
| 6. Criar dropdown de troca de org | 1h | Baixa |
| 7. Implementar switch_organization view | 1h | Média |
| 8. Refatorar código existente (user.organization) | 4h | Alta |
| 9. Atualizar Admin | 1h | Baixa |
| 10. Criar testes | 4h | Alta |
| 11. Testes manuais e ajustes | 2h | Média |
| 12. Documentação | 1h | Baixa |
| **TOTAL** | **~22h** | **Alta** |

**Estimativa conservadora: 3-4 dias de desenvolvimento**

---

## 🎯 ALTERNATIVAS MAIS SIMPLES

### **Alternativa 1: Múltiplos Logins (Atual)**
- Usuário faz logout e login com outra conta
- **Prós:** Simples, já funciona
- **Contras:** Inconveniente, múltiplas contas

### **Alternativa 2: Convite de Usuário**
- Criar usuário separado para cada org
- Mesmo email, usernames diferentes
- **Prós:** Isolamento total, sem mudanças no código
- **Contras:** Múltiplas senhas, confuso

### **Alternativa 3: Subcontas**
- Usuário principal + subcontas vinculadas
- **Prós:** Mantém simplicidade do modelo atual
- **Contras:** Limitado, não resolve todos os casos

---

## 📋 CHECKLIST DE IMPLEMENTAÇÃO

Quando for implementar, seguir esta ordem:

- [ ] 1. Criar branch `feature/multi-org-user`
- [ ] 2. Criar model `UserOrganization`
- [ ] 3. Adicionar campo `organizations` (M2M) em User
- [ ] 4. Adicionar campo `default_organization` em User
- [ ] 5. Criar migration de dados (user.organization → user.organizations)
- [ ] 6. Atualizar TenantMiddleware
- [ ] 7. Criar view `select_organization`
- [ ] 8. Criar template `auth/select_organization.html`
- [ ] 9. Criar view `switch_organization`
- [ ] 10. Adicionar dropdown no header
- [ ] 11. Atualizar login_view para redirecionar para seleção
- [ ] 12. Refatorar código que usa `user.organization` (buscar e substituir)
- [ ] 13. Atualizar Admin (UserAdmin, OrganizationAdmin)
- [ ] 14. Criar testes unitários
- [ ] 15. Criar testes de integração
- [ ] 16. Testes manuais completos
- [ ] 17. Documentar no README
- [ ] 18. Code review
- [ ] 19. Deploy em staging
- [ ] 20. Validação com usuários
- [ ] 21. Deploy em produção

---

## 💡 RECOMENDAÇÕES

1. **Implementar em Fases:**
   - Fase 1: Model + Migration (sem quebrar código existente)
   - Fase 2: UI de seleção (opcional, pode pular se 1 org)
   - Fase 3: Dropdown de troca (feature completa)
   - Fase 4: Refatorar código antigo

2. **Manter Compatibilidade Temporária:**
   - Criar property `user.organization` que retorna `user.default_organization`
   - Deprecar gradualmente
   - Remover em versão futura

3. **Logs Detalhados:**
   - Logar todas as trocas de organização
   - Incluir org ativa em todos os logs
   - Facilitar debug e auditoria

4. **Feature Flag:**
   - Implementar atrás de feature flag
   - Ativar apenas para usuários específicos inicialmente
   - Rollout gradual

---

## 📚 REFERÊNCIAS

- Django ManyToManyField: https://docs.djangoproject.com/en/4.2/topics/db/examples/many_to_many/
- Django Through Models: https://docs.djangoproject.com/en/4.2/ref/models/fields/#django.db.models.ManyToManyField.through
- Session Management: https://docs.djangoproject.com/en/4.2/topics/http/sessions/

---

**Documento criado em:** 21/01/2026 19:30  
**Autor:** Cascade AI  
**Status:** Planejamento - Aguardando aprovação para implementação
