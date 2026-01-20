# 👥 IAMKT - USUÁRIOS E PERMISSÕES

**Documento:** 06 de 10  
**Versão:** 1.0  
**Data:** Janeiro 2026

---

## 🎯 VISÃO GERAL

O IAMKT implementa um sistema robusto de gestão de usuários e permissões baseado em **Áreas Organizacionais**, permitindo controle granular sobre quem pode acessar quais ferramentas e com quais limites.

### Princípios

1. **Baseado em Áreas**: Permissões vinculadas a áreas, não usuários individuais
2. **Múltiplas Áreas**: Usuário pode estar em várias áreas
3. **Permissões Aditivas**: União de permissões de todas as áreas
4. **Limites por Área**: Controle de uso mensal
5. **Auditoria Completa**: Todas ações críticas registradas

---

## 👤 PERFIS DE USUÁRIO

### Hierarquia de Perfis

```
┌─────────────────────────────────────────┐
│           ADMIN / TI                    │
│  (Acesso total sistema + Django Admin) │
└─────────────────┬───────────────────────┘
                  │
        ┌─────────┴─────────┐
        │                   │
┌───────▼────────┐  ┌──────▼──────────┐
│    GESTOR      │  │  OPERACIONAL    │
│ (Aprovação +   │  │  (Criação de    │
│  Relatórios)   │  │   Conteúdo)     │
└────────────────┘  └─────────────────┘
```

---

### PERFIL: Admin

**Descrição:** Controle total do sistema.

| Aspecto | Acesso |
|---------|--------|
| **Django Admin** | ✅ Acesso completo |
| **Front-end IAMKT** | ✅ Acesso total |
| **Áreas** | Pode estar em qualquer área |
| **Ferramentas** | Todas |
| **Limites** | Sem limites |

**Permissões Específicas:**
- Gerenciar usuários (criar, editar, deletar)
- Gerenciar áreas (criar, editar, deletar)
- Configurar Base de Conhecimento
- Acessar logs de auditoria completos
- Modificar configurações do sistema
- Ver métricas de todas as áreas
- Ignorar limites de uso

**Casos de Uso:**
- Configuração inicial do sistema
- Gestão de acessos
- Manutenção técnica
- Configurações avançadas

---

### PERFIL: TI

**Descrição:** Equivalente ao Admin, focado em suporte técnico.

| Aspecto | Acesso |
|---------|--------|
| **Django Admin** | ✅ Acesso completo |
| **Front-end IAMKT** | ✅ Acesso total |
| **Áreas** | Pode estar em qualquer área |
| **Ferramentas** | Todas |
| **Limites** | Sem limites |

**Diferença do Admin:**
- Mesmo nível de acesso técnico
- Foco em troubleshooting e suporte
- Pode ser múltiplos usuários (equipe TI)

---

### PERFIL: Gestor

**Descrição:** Gerencia equipe, aprova conteúdos, visualiza relatórios.

| Aspecto | Acesso |
|---------|--------|
| **Django Admin** | ❌ Sem acesso |
| **Front-end IAMKT** | ✅ Acesso conforme área(s) |
| **Áreas** | Vinculado a 1 ou mais áreas |
| **Ferramentas** | Conforme permissões da(s) área(s) |
| **Limites** | Ignora limites para visualização |

**Permissões Específicas:**
- ✅ Criar conteúdo (se área permitir)
- ✅ **Aprovar/reprovar** conteúdos da(s) sua(s) área(s)
- ✅ Ver histórico completo da área
- ✅ Ver relatórios e métricas da área
- ✅ Ver custos de IA da área
- ✅ Receber notificações de aprovação
- ❌ Não pode gerenciar usuários
- ❌ Não pode modificar Base de Conhecimento (apenas visualizar)

**Dashboard do Gestor:**
```
┌─────────────────────────────────────────┐
│  👤 João Silva - Gestor (Marketing)     │
├─────────────────────────────────────────┤
│                                          │
│  🔔 APROVAÇÕES PENDENTES: 5              │
│  ┌────────────────────────────────────┐ │
│  │ Post Instagram - "Saúde do Coração"│ │
│  │ Solicitado por: Maria Santos       │ │
│  │ [ Ver ] [ Aprovar ] [ Ajustar ]   │ │
│  └────────────────────────────────────┘ │
│                                          │
│  📊 MÉTRICAS MARKETING (Este Mês)       │
│  - Conteúdos gerados: 45                │
│  - Taxa aprovação: 87%                  │
│  - Custo IA: R$ 125,00                  │
│                                          │
│  📈 RELATÓRIOS                           │
│  [ Ver Relatório Mensal ]               │
│  [ Exportar Dados ]                     │
└─────────────────────────────────────────┘
```

---

### PERFIL: Operacional

**Descrição:** Criador de conteúdo, usuário final das ferramentas de IA.

| Aspecto | Acesso |
|---------|--------|
| **Django Admin** | ❌ Sem acesso |
| **Front-end IAMKT** | ✅ Acesso conforme área(s) |
| **Áreas** | Vinculado a 1 ou mais áreas |
| **Ferramentas** | Conforme permissões da(s) área(s) |
| **Limites** | Sujeito a limites de uso |

**Permissões Específicas:**
- ✅ Criar conteúdo com ferramentas permitidas
- ✅ Editar seus próprios conteúdos
- ✅ Enviar para aprovação
- ✅ Ver histórico dos seus conteúdos
- ✅ Marcar favoritos
- ❌ Não pode aprovar conteúdos
- ❌ Não pode ver relatórios completos (apenas seus próprios)
- ❌ Não pode ver custos detalhados

**Dashboard do Operacional:**
```
┌─────────────────────────────────────────┐
│  👤 Maria Santos - Operacional (Mkt)    │
├─────────────────────────────────────────┤
│                                          │
│  🎨 FERRAMENTAS DISPONÍVEIS              │
│  ┌──────┐ ┌──────┐ ┌──────┐           │
│  │Pautas│ │Posts │ │Trends│           │
│  └──────┘ └──────┘ └──────┘           │
│                                          │
│  📝 MEUS CONTEÚDOS RECENTES              │
│  - Post "Prevenção..." ⏳ Aguard. Apr.  │
│  - Pauta "Cardiologia" ✅ Aprovado     │
│  - Post "Check-up" ⚠️ Em Ajuste        │
│                                          │
│  ⭐ FAVORITOS (3)                        │
│  📊 USO: 45/100 gerações este mês       │
└─────────────────────────────────────────┘
```

---

## 🏢 ÁREAS ORGANIZACIONAIS

### Conceito

**Áreas** são divisões organizacionais que agrupam usuários e definem:
- Quais ferramentas podem usar
- Limites de uso mensal
- Métricas independentes

### Estrutura de Área

```python
class Area(models.Model):
    nome = "Marketing"
    descricao = "Equipe de marketing e comunicação"
    ativa = True
    
    # Ferramentas permitidas
    ferramentas_permitidas = [
        'pautas',
        'posts',
        'trends',
        'pesquisa_web'
    ]
    
    # Limites
    limite_mensal = 1000
    tipo_limite = 'geracoes'  # ou 'tokens'
```

### Exemplos de Áreas

#### Área: Marketing
```yaml
Nome: Marketing
Descrição: Equipe de marketing e comunicação institucional
Ferramentas:
  - pautas
  - posts
  - trends
  - pesquisa_web
  - simulador_feed
Limite: 1000 gerações/mês
Usuários:
  - João Silva (Gestor)
  - Maria Santos (Operacional)
  - Ana Costa (Operacional)
```

#### Área: Comunicação Interna
```yaml
Nome: Comunicação Interna
Descrição: Comunicação com colaboradores
Ferramentas:
  - pautas
  - posts
Limite: 500 gerações/mês
Usuários:
  - Carlos Oliveira (Gestor)
  - Fernanda Lima (Operacional)
```

#### Área: Recursos Humanos
```yaml
Nome: Recursos Humanos
Descrição: RH e gestão de pessoas
Ferramentas:
  - pautas
Limite: 200 gerações/mês
Usuários:
  - Paula Souza (Gestor)
  - Roberto Alves (Operacional)
```

#### Área: Diretoria
```yaml
Nome: Diretoria
Descrição: Diretoria executiva
Ferramentas:
  - todas
Limite: sem limite
Usuários:
  - Dr. Ricardo Mendes (Gestor)
```

---

## 🔐 SISTEMA DE PERMISSÕES

### Regras Fundamentais

#### 1. Permissões são ADITIVAS

Usuário em múltiplas áreas tem **UNIÃO** das permissões.

**Exemplo:**
```
Maria Santos está em:
  - Marketing (pautas, posts, trends)
  - Comunicação Interna (pautas, posts)

Permissões de Maria:
  ✅ pautas (Marketing + Com. Interna)
  ✅ posts (Marketing + Com. Interna)
  ✅ trends (Marketing)
```

#### 2. Limites são SOMADOS

Usuário em múltiplas áreas tem **SOMA** dos limites.

**Exemplo:**
```
Maria Santos está em:
  - Marketing: 1000 gerações/mês
  - Com. Interna: 500 gerações/mês

Limite total de Maria: 1500 gerações/mês
```

#### 3. Bloqueio por Limite

Quando área atinge 100% do limite:
- ✅ Visualização continua funcionando
- ❌ Nova geração bloqueada
- 📧 Email automático para gestor da área
- 🔓 Admin pode desbloquear manualmente

#### 4. Alerta aos 80%

Sistema envia alerta quando área atinge 80% do limite:
- Email para todos gestores da área
- Notificação in-app
- Badge visual no dashboard

---

## 📊 MATRIZ DE PERMISSÕES

### Por Funcionalidade

| Funcionalidade | Admin/TI | Gestor | Operacional |
|----------------|----------|--------|-------------|
| **Django Admin** | ✅ | ❌ | ❌ |
| **Criar Usuário** | ✅ | ❌ | ❌ |
| **Editar Base FEMME** | ✅ | ❌ | ❌ |
| **Ver Base FEMME** | ✅ | ✅ | ✅ |
| **Criar Conteúdo** | ✅ | ✅* | ✅* |
| **Editar Próprio Conteúdo** | ✅ | ✅ | ✅ |
| **Editar Conteúdo de Outros** | ✅ | ✅** | ❌ |
| **Aprovar Conteúdo** | ✅ | ✅** | ❌ |
| **Ver Relatórios Área** | ✅ | ✅** | ❌ |
| **Ver Relatórios Globais** | ✅ | ❌ | ❌ |
| **Ver Custos IA** | ✅ | ✅** | ❌ |
| **Gerenciar Áreas** | ✅ | ❌ | ❌ |
| **Ver Logs Auditoria** | ✅ | ✅*** | ❌ |

\* Se área permitir ferramenta  
\** Apenas da(s) sua(s) área(s)  
\*** Apenas logs da sua área

---

## 🔄 FLUXOS DE TRABALHO

### Criação de Novo Usuário

```
1. Admin acessa Django Admin
   │
2. Users → Add User
   │
3. Preenche dados
   ├─> Username (único)
   ├─> Email (único, obrigatório)
   ├─> Password
   ├─> Perfil (admin/ti/gestor/operacional)
   └─> Áreas (múltipla escolha)
   │
4. Save
   │
5. Email automático enviado
   ├─> Credenciais de acesso
   ├─> Link para primeiro login
   └─> Instruções básicas
```

### Mudança de Área

```
1. Admin acessa Django Admin → Users
   │
2. Seleciona usuário
   │
3. Edita campo "Áreas"
   ├─> Adiciona nova área
   └─> Remove área antiga (se necessário)
   │
4. Save
   │
5. Permissões recalculadas automaticamente
   │
6. Log de auditoria registrado
```

### Desativação de Usuário

```
1. Admin acessa Django Admin → Users
   │
2. Seleciona usuário
   │
3. Desmarca checkbox "Ativo"
   │
4. Save
   │
5. Usuário não consegue mais fazer login
   ├─> Conteúdos criados permanecem
   ├─> Histórico preservado
   └─> Pode ser reativado depois
```

---

## 📈 CONTROLE DE LIMITES

### Tracking de Uso

Cada geração incrementa contador:

```python
# Ao gerar conteúdo
def gerar_conteudo(usuario, area, ferramenta):
    # 1. Verifica limite
    usage = UsageLimit.objects.get(
        area=area,
        mes_referencia=mes_atual()
    )
    
    if usage.bloqueado:
        raise LimiteExcedidoError()
    
    # 2. Gera conteúdo
    conteudo = ia_gerar(...)
    
    # 3. Incrementa contador
    usage.consumido += 1
    
    # 4. Verifica alerta 80%
    if usage.consumido >= area.limite_mensal * 0.8:
        if not usage.alerta_enviado:
            enviar_alerta_80(area)
            usage.alerta_enviado = True
    
    # 5. Verifica bloqueio 100%
    if usage.consumido >= area.limite_mensal:
        usage.bloqueado = True
        enviar_alerta_100(area)
    
    usage.save()
```

### Dashboard de Limites (Admin)

```
┌─────────────────────────────────────────────────┐
│  📊 Controle de Limites - Janeiro 2026          │
├─────────────────────────────────────────────────┤
│                                                  │
│  Área: Marketing                                │
│  Limite: 1000 gerações/mês                      │
│  Consumido: 850 (85%)                           │
│  Status: ⚠️ Alerta enviado                      │
│  ████████████████████░░                         │
│                                                  │
│  [ Aumentar Limite ] [ Resetar Contador ]      │
│                                                  │
├─────────────────────────────────────────────────┤
│                                                  │
│  Área: Comunicação Interna                      │
│  Limite: 500 gerações/mês                       │
│  Consumido: 320 (64%)                           │
│  Status: ✅ Normal                              │
│  █████████████░░░░░░░░░                         │
│                                                  │
├─────────────────────────────────────────────────┤
│                                                  │
│  Área: RH                                        │
│  Limite: 200 gerações/mês                       │
│  Consumido: 200 (100%)                          │
│  Status: 🔒 BLOQUEADO                           │
│  █████████████████████                          │
│                                                  │
│  [ Desbloquear ] [ Aumentar Limite ]           │
│                                                  │
└─────────────────────────────────────────────────┘
```

---

## 📝 AUDITORIA

### Eventos Registrados

Todas as ações críticas são registradas no `AuditLog`:

| Evento | Dados Capturados |
|--------|------------------|
| **Login** | Usuário, IP, timestamp, sucesso/falha |
| **Criação Usuário** | Admin que criou, dados do novo usuário |
| **Edição Base FEMME** | Bloco, campo, valor anterior, valor novo |
| **Geração Conteúdo** | Ferramenta, modelo IA, tokens, custo |
| **Aprovação** | Conteúdo, aprovador, decisão |
| **Mudança Permissões** | Usuário afetado, áreas antes/depois |
| **Atingir Limite** | Área, timestamp, valor do limite |

### Consulta de Logs

**Filtros disponíveis:**
- Por usuário
- Por ação
- Por data
- Por área
- Por model/objeto

**Exemplo de Log:**
```json
{
  "timestamp": "2026-01-12 15:30:00",
  "usuario": "joao.silva",
  "perfil": "gestor",
  "acao": "approve",
  "model_name": "GeneratedContent",
  "object_id": 123,
  "dados_anteriores": {"status": "aguardando_aprovacao"},
  "dados_novos": {"status": "aprovado"},
  "ip_address": "192.168.1.100",
  "area": "Marketing"
}
```

---

## 🔧 CONFIGURAÇÕES ADICIONAIS

### Notificações

**Admin pode configurar:**
- Email de alertas de limite
- Frequência de relatórios automáticos
- Quem recebe notificações de aprovação

**Por Usuário:**
- Notificações in-app (ativar/desativar)
- Email de novos trends (ativar/desativar)
- Email de aprovações (ativar/desativar)

### Sessões

- **Timeout:** 8 horas de inatividade
- **Múltiplos logins:** Permitido (mesmo usuário em vários browsers)
- **Logout forçado:** Admin pode forçar logout de usuário

---

**Próximo documento:** [07_IAMKT_Integracoes_Tecnicas.md](07_IAMKT_Integracoes_Tecnicas.md)
