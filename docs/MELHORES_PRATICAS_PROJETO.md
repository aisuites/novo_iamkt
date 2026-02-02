# 📚 MELHORES PRÁTICAS E PADRÕES DO PROJETO IAMKT

**Última atualização:** 28/01/2026 09:01  
**Objetivo:** Documento centralizado com todos os padrões e melhores práticas estabelecidos

---

## 🐳 1. PADRÃO DOCKER (CRÍTICO)

### **REGRA ABSOLUTA - INSTALAÇÃO DE PACOTES**

```bash
❌ NUNCA: pip install <pacote>  # Fora do container

✅ SEMPRE:
  1. Adicionar ao app/requirements.txt
  2. docker exec -u root iamkt_web pip install <pacote>
  3. Rebuild: docker-compose build iamkt_web && make recreate
```

**Histórico de erros corrigidos:**
- django-ratelimit instalado fora do container
- django-compressor instalado fora do container
- boto3 instalado fora do container

**Verificação:**
```bash
docker exec iamkt_web pip freeze  # Verificar instalações no container
```

---

### **COMANDOS DOCKER COM MAKEFILE**

O projeto usa **Makefile** para padronizar comandos Docker.

#### **Comandos Principais**

```bash
# Ver todos os comandos disponíveis
make help

# Iniciar containers (modo normal)
make up

# Iniciar containers (modo solo - mais recursos)
make solo

# Parar containers
make down

# Recriar containers (após mudanças em .env ou código)
make recreate

# Ver logs em tempo real
make logs

# Shell Django (Python)
make shell

# Shell PostgreSQL
make dbshell

# Executar migrations
make migrate

# Criar backup do banco
make backup

# Limpar containers órfãos
make clean

# Validar isolamento de portas
make validate
```

#### **Comandos Alternativos (Diretos)**

```bash
# Restart rápido (código já montado via volume)
docker-compose restart iamkt_web

# Logs específicos
docker logs -f iamkt_web

# Executar comando no container
docker exec iamkt_web python manage.py <comando>

# Shell interativo
docker exec -it iamkt_web bash
```

#### **Workflow de Desenvolvimento**

**Após mudanças em código Python:**
```bash
# Opção 1: Restart simples (código já montado via volume)
docker-compose restart iamkt_web

# Opção 2: Recreate (recarrega .env também)
make recreate
```

**Após mudanças em requirements.txt ou Dockerfile:**
```bash
# Rebuild completo
docker-compose build iamkt_web
make recreate
```

**Executar migrations:**
```bash
# Via make
make migrate

# Ou direto
docker exec iamkt_web python manage.py migrate
```

---

## 🏗️ 2. ARQUITETURA E PADRÕES DE CÓDIGO

### **Multi-tenancy (CRÍTICO)**

**REGRAS OBRIGATÓRIAS:**
- ✅ **SEMPRE** filtrar por `organization` em queries
- ❌ **NUNCA** usar `.first()` sem filtro de organization
- ✅ Testar com múltiplas organizations
- ✅ S3 keys devem conter `org-{id}/`

**Exemplo correto:**
```python
# ❌ ERRADO
knowledge_base = KnowledgeBase.objects.first()

# ✅ CORRETO
organization = getattr(request, 'organization', None)
knowledge_base = KnowledgeBase.objects.filter(organization=organization).first()
```

**Lição aprendida:**
- Bug do modal de onboarding: view pegava KB errada por não filtrar por organization
- Sempre verificar isolation em ambientes multi-tenant

---

### **Service Layer**

**Padrão estabelecido:**
- ✅ Lógica de negócio em Services (`S3Service`, `ColorService`, `FontService`, etc.)
- ✅ Views apenas orquestram e validam
- ✅ Services são reutilizáveis e testáveis

**Estrutura:**
```python
# apps/knowledge/services.py
class KnowledgeBaseService:
    @staticmethod
    def save_all_blocks(request, kb, forms):
        # Lógica de negócio aqui
        pass

# apps/knowledge/views.py
def knowledge_save_all(request):
    # View apenas orquestra
    success, errors = KnowledgeBaseService.save_all_blocks(request, kb, forms)
    if success:
        return redirect('core:dashboard')
```

---

### **Otimização de Queries**

**Padrões obrigatórios:**
- ✅ Usar `select_related()` para ForeignKey (1-to-1, Many-to-1)
- ✅ Usar `prefetch_related()` para ManyToMany e reverse ForeignKey
- ✅ Evitar N+1 queries
- ✅ Adicionar índices em campos frequentemente consultados

**Exemplo:**
```python
# ❌ ERRADO - N+1 queries
logos = Logo.objects.filter(knowledge_base=kb)
for logo in logos:
    print(logo.uploaded_by.email)  # Query adicional para cada logo

# ✅ CORRETO - 1 query
logos = Logo.objects.filter(knowledge_base=kb).select_related('uploaded_by')
for logo in logos:
    print(logo.uploaded_by.email)  # Sem query adicional
```

**Redução alcançada:** 95-97% menos queries

---

### **Paginação**

**Padrão:**
- ✅ 20 itens por página (padrão do projeto)
- ✅ Usar `Paginator` do Django

**Exemplo:**
```python
from django.core.paginator import Paginator

pautas = Pauta.objects.for_request(request).order_by('-created_at')
paginator = Paginator(pautas, 20)
page_obj = paginator.get_page(request.GET.get('page'))
```

---

## 🔒 3. SEGURANÇA

### **Validação de Upload**

**Classe implementada:** `apps/core/utils/upload_validators.py`

**Validações obrigatórias:**
- ✅ MIME type (whitelist)
- ✅ Tamanho de arquivo
- ✅ Extensão de arquivo

**Limites estabelecidos:**
- Imagens: 10MB
- Fontes: 5MB
- Vídeos: 100MB

**Uso:**
```python
from apps.core.utils.upload_validators import FileUploadValidator

is_valid, error_msg = FileUploadValidator.validate_image(
    file_name=file_name,
    file_type=file_type,
    file_size=int(file_size)
)
if not is_valid:
    return JsonResponse({'success': False, 'error': error_msg}, status=400)
```

---

### **Rate Limiting**

**Limites estabelecidos:**
- Logos: 10 uploads/minuto por usuário
- Referências: 20 uploads/minuto por usuário
- Fontes: 5 uploads/minuto por usuário

**Uso:**
```python
from django_ratelimit.decorators import ratelimit

@ratelimit(key='user', rate='10/m', method='POST', block=True)
def generate_logo_upload_url(request):
    pass
```

**Resposta:** HTTP 429 quando limite excedido

---

### **Secrets e Variáveis de Ambiente**

**Regras:**
- ✅ `.env` no `.gitignore`
- ✅ `python-decouple` para variáveis de ambiente
- ❌ **NUNCA** commitar secrets
- ✅ Usar `.env.development` e `.env.production`

**Exemplo:**
```python
from decouple import config

SECRET_KEY = config('SECRET_KEY')
AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID')
```

---

## 📝 4. LOGGING E DEBUG

### **Frontend (JavaScript)**

**Padrão estabelecido:**
- ✅ Usar `logger.debug()` ao invés de `console.log()`
- ✅ Usar `logger.error()` ao invés de `console.error()`
- ✅ Usar `logger.warn()` ao invés de `console.warn()`
- ✅ Logger silencioso em produção, verboso em desenvolvimento

**Arquivo:** `static/js/logger.js`

**Uso:**
```javascript
// ❌ ERRADO
console.log('Debug info:', data);
console.error('Erro:', error);

// ✅ CORRETO
logger.debug('Debug info:', data);
logger.error('Erro:', error);
```

**Comportamento:**
- **Desenvolvimento (localhost):** Logs verbosos no console
- **Produção:** Logs silenciosos (apenas erros críticos)

---

### **Backend (Python)**

**Para debug temporário:**
```python
# Durante desenvolvimento
print(f"🔍 DEBUG: {variavel}", flush=True)

# ❌ IMPORTANTE: Remover antes de commit final
```

**Logging estruturado:**
- ✅ Configuração em `sistema/settings/logging_config.py`
- ✅ Usar `logger.info()`, `logger.error()`, etc.

**Exemplo:**
```python
import logging
logger = logging.getLogger(__name__)

logger.info('Operação realizada com sucesso')
logger.error('Erro ao processar', exc_info=True)
```

---

## 🎨 5. CÓDIGO LIMPO E MELHORES PRÁTICAS (CRÍTICO)

### **NUNCA usar Hardcode**

**Regra absoluta:**
- ❌ **NUNCA** valores fixos no código
- ✅ **SEMPRE** usar variáveis de ambiente
- ✅ **SEMPRE** usar configurações
- ✅ **SEMPRE** usar constantes nomeadas

**Exemplos:**

```python
# ❌ ERRADO - Hardcode
url = "https://api.example.com/endpoint"
max_items = 100
api_key = "abc123xyz"
timeout = 30

# ✅ CORRETO - Configurável
from django.conf import settings

url = settings.API_ENDPOINT
max_items = settings.MAX_ITEMS_PER_PAGE
api_key = settings.API_KEY
timeout = settings.REQUEST_TIMEOUT
```

```javascript
// ❌ ERRADO - Hardcode
const apiUrl = 'https://api.example.com';
const maxRetries = 3;

// ✅ CORRETO - Configurável
const apiUrl = window.APP_CONFIG.apiUrl;
const maxRetries = window.APP_CONFIG.maxRetries;
```

---

### **NUNCA usar CSS Inline**

**Regra absoluta:**
- ❌ **NUNCA** usar atributo `style=""` em HTML
- ✅ **SEMPRE** criar classes CSS em arquivos .css
- ✅ **SEMPRE** usar componentes reutilizáveis
- ✅ **SEMPRE** separar apresentação de estrutura

**Exemplos:**

```html
<!-- ❌ ERRADO - CSS Inline -->
<div style="color: red; padding: 10px; margin-bottom: 20px;">
    Texto de erro
</div>

<button style="background: #6366f1; color: white; padding: 8px 16px;">
    Salvar
</button>

<!-- ✅ CORRETO - Classes CSS -->
<div class="alert alert-danger mb-4">
    Texto de erro
</div>

<button class="btn btn-primary">
    Salvar
</button>
```

**Arquivo CSS correspondente:**
```css
/* static/css/components.css */
.alert {
    padding: 10px;
    border-radius: 4px;
}

.alert-danger {
    color: #dc3545;
    background: #f8d7da;
    border: 1px solid #f5c6cb;
}

.btn {
    padding: 8px 16px;
    border-radius: 4px;
    border: none;
    cursor: pointer;
}

.btn-primary {
    background: #6366f1;
    color: white;
}
```

**Exceções permitidas:**
- ✅ Estilos dinâmicos calculados via JavaScript (ex: posição baseada em scroll)
- ✅ Estilos de debug temporários (remover antes de commit)

---

### **Melhores Práticas de Mercado**

**DRY (Don't Repeat Yourself):**
- ✅ Criar funções/componentes reutilizáveis
- ✅ Consolidar código duplicado
- ✅ Usar herança e composição

**Separação de Responsabilidades:**
- ✅ HTML: Estrutura
- ✅ CSS: Apresentação
- ✅ JavaScript: Comportamento
- ✅ Python: Lógica de negócio

**Componentização:**
- ✅ Criar componentes pequenos e focados
- ✅ Reutilizar componentes existentes
- ✅ Documentar componentes

**Código Limpo:**
- ✅ Nomes descritivos
- ✅ Funções pequenas (máx 50 linhas)
- ✅ Comentários apenas quando necessário
- ✅ Evitar complexidade desnecessária

---

## 📦 6. ORGANIZAÇÃO DE CÓDIGO

### **Estrutura de Arquivos**

```
app/
├── apps/
│   ├── core/           # Auth, Organization, User, Middleware
│   ├── knowledge/      # Knowledge Base (principal)
│   ├── content/        # Pautas, Posts, Trends
│   └── campaigns/      # Projetos
├── static/
│   ├── js/
│   │   ├── utils.js    # Funções utilitárias (DRY)
│   │   └── logger.js   # Logging condicional
│   └── css/
├── templates/
│   ├── base/
│   ├── components/     # Componentes reutilizáveis (sidebar, header)
│   └── [app]/
├── docs/               # Documentação (43 arquivos MD)
├── tests/              # Testes automatizados
└── scripts/            # Scripts utilitários
```

---

### **Remoção de Duplicação (DRY)**

**Funções utilitárias consolidadas em `static/js/utils.js`:**
- `getCookie()`
- `formatBytes()`
- `debounce()`, `throttle()`
- `isValidEmail()`, `isValidUrl()`
- `escapeHtml()`
- `generateUniqueId()`
- `copyToClipboard()`
- `scrollToElement()`
- `sleep()`

**Antes:** Função `getCookie()` duplicada em 4 arquivos  
**Depois:** 1 única implementação em `utils.js`

---

## 🧪 6. TESTES

### **Padrões de Teste**

**Estrutura:**
- ✅ Testes em pasta `tests/`
- ✅ Nomenclatura: `test_*.py`
- ✅ Usar `TestCase` do Django

**Áreas de teste obrigatórias:**
- ✅ Tenant isolation (multi-tenancy)
- ✅ Validações de upload
- ✅ Rate limiting
- ✅ Permissões e autenticação

**Execução:**
```bash
# Todos os testes
docker exec iamkt_web python manage.py test

# Teste específico
docker exec iamkt_web python manage.py test tests.test_tenant_isolation
```

**Arquivo exemplo:** `tests/test_tenant_isolation.py`

---

## 📄 7. DOCUMENTAÇÃO

### **Padrão de Documentação Diária**

**Regra:**
- ✅ **1 arquivo MD por dia** em `/opt/iamkt/docs/`
- ✅ Formato: `SESSAO_YYYY-MM-DD.md`
- ✅ Atualizar durante o dia conforme implementações
- ✅ Nunca deletar documentação anterior

**Estrutura do arquivo diário:**
```markdown
# SESSÃO DE DESENVOLVIMENTO - DD/MM/YYYY

## 📋 AÇÕES DO DIA
[Atualizar durante o dia]

## 🎯 CONTEXTO DA SESSÃO ANTERIOR
[Resumo da última sessão]

## 📝 IMPLEMENTAÇÕES
[Detalhar implementações]

## 🐛 PROBLEMAS E SOLUÇÕES
[Documentar bugs e fixes]

## 📊 COMMITS REALIZADOS
[Lista de commits]

## 🎓 LIÇÕES APRENDIDAS
[Aprendizados do dia]
```

---

### **Padrão de Commits**

**Formato:** `tipo: descrição curta`

**Tipos:**
- `feat`: Nova funcionalidade
- `fix`: Correção de bug
- `docs`: Documentação
- `refactor`: Refatoração de código
- `test`: Adição/modificação de testes
- `chore`: Tarefas de manutenção
- `debug`: Logs de debug (temporários)
- `cleanup`: Limpeza de código

**Exemplos:**
```bash
git commit -m "feat: adicionar página Perfil da Empresa"
git commit -m "fix: corrigir busca de KB por organization"
git commit -m "docs: atualizar documentação de onboarding"
git commit -m "cleanup: remover logs de debug"
```

---

## 🔄 8. WORKFLOW DE DESENVOLVIMENTO

### **Antes de Implementar**

1. ✅ Ler documentação existente em `/opt/iamkt/docs/`
2. ✅ Entender contexto e histórico
3. ✅ Planejar etapas (criar TODO list)
4. ✅ **NUNCA instalar pacotes sem autorização**
5. ✅ Criar branch se necessário

---

### **Durante Implementação**

1. ✅ Seguir padrões estabelecidos neste documento
2. ✅ Testar incrementalmente
3. ✅ Documentar no arquivo do dia (`SESSAO_YYYY-MM-DD.md`)
4. ✅ Commits frequentes e descritivos
5. ✅ Adicionar logs de debug temporários se necessário

---

### **Após Implementação**

1. ✅ Verificar com `docker exec iamkt_web python manage.py check`
2. ✅ Testar funcionalidade manualmente
3. ✅ Executar testes automatizados se aplicável
4. ✅ **Limpar logs de debug temporários**
5. ✅ Atualizar documentação do dia
6. ✅ Commit final com mensagem descritiva
7. ✅ Restart/recreate containers se necessário

---

### **Checklist de Qualidade**

Antes de considerar uma implementação completa:

- [ ] Código segue padrões do projeto
- [ ] Multi-tenancy respeitado (filtro por organization)
- [ ] Queries otimizadas (select_related/prefetch_related)
- [ ] Validações de segurança implementadas
- [ ] Logs de debug removidos
- [ ] Documentação atualizada
- [ ] Testes passando
- [ ] `python manage.py check` sem erros
- [ ] Commit com mensagem descritiva

---

## 🎓 9. LIÇÕES APRENDIDAS (HISTÓRICO)

### **Multi-tenancy**
- ⚠️ **Problema:** View pegando KB errada (`.first()` sem filtro)
- ✅ **Solução:** Sempre filtrar por `organization`
- 📝 **Lição:** Testar com múltiplas organizations

### **Docker**
- ⚠️ **Problema:** Pacotes instalados fora do container
- ✅ **Solução:** Sempre instalar dentro do container
- 📝 **Lição:** Verificar com `docker exec iamkt_web pip freeze`

### **Context Processors**
- ⚠️ **Problema:** Executam em TODAS as requisições
- ✅ **Solução:** Usar com cuidado, otimizar queries
- 📝 **Lição:** Evitar logs excessivos em context processors

### **Debugging**
- ⚠️ **Problema:** Código não atualizando após mudanças
- ✅ **Solução:** `make recreate` após mudanças em requirements.txt
- 📝 **Lição:** Restart simples para código, rebuild para dependências

---

## 📊 10. ESTADO ATUAL DO PROJETO

### **Última Implementação (27/01/2026)**
- ✅ Fluxo de onboarding completo
- ✅ Modal condicional baseado em `onboarding_completed`
- ✅ Middleware de restrição de acesso
- ✅ Menu sidebar dinâmico
- ✅ Placeholder N8N criado

### **Próximos Passos Planejados**
- 🎯 Página "Perfil da Empresa"
- 🎯 Integração N8N (definir payload e retorno)
- 🎯 Atualização dinâmica do sidebar após onboarding

---

## 🔗 REFERÊNCIAS

**Documentação importante:**
- `/opt/iamkt/docs/SESSAO_ONBOARDING_2026-01-27.md` - Última implementação
- `/opt/iamkt/docs/RESUMO_SESSAO_2026-01-27.md` - Auditoria completa
- `/opt/iamkt/docs/MELHORIAS_DESEJAVEIS_2026-01-27.md` - Melhorias P3
- `/opt/iamkt/docs/AUDITORIA_COMPLETA_2026-01-27.md` - Análise profunda
- `/opt/iamkt/Makefile` - Comandos Docker disponíveis

**Arquivos chave:**
- `app/requirements.txt` - Dependências Python
- `sistema/settings/base.py` - Configurações Django
- `apps/core/middleware_onboarding.py` - Middleware de onboarding
- `apps/core/context_processors.py` - Context processors globais
- `static/js/utils.js` - Funções utilitárias JS
- `static/js/logger.js` - Logger condicional JS

---

**Documento vivo - atualizar conforme novas práticas são estabelecidas**
