# 📋 IAMKT - DOCUMENTAÇÃO TÉCNICA

**Versão:** 1.0  
**Data:** Janeiro 2026  
**Aplicação:** IAMKT (Marketing Intelligence Platform)  
**Servidor:** FEMME - Rede Isolada Docker  
**Domínio:** iamkt-femmeintegra.aisuites.com.br  
**IP:** 72.61.223.244  
**Status:** Em Desenvolvimento - Fase 1

---

## 🎯 VISÃO GERAL

O **IAMKT** (Marketing Intelligence Platform) é uma aplicação Django desenvolvida para uso interno da FEMME, projetada para automatizar e potencializar a geração de conteúdo de marketing através de Inteligência Artificial.

A plataforma utiliza a **Base de Conhecimento FEMME** como "DNA" da marca, garantindo que todo conteúdo gerado esteja alinhado com a identidade institucional, tom de voz, valores e diretrizes visuais da empresa.

---

## 🎨 PROPÓSITO

- ✅ Centralizar a geração de conteúdo de marketing em uma única plataforma
- ✅ Garantir consistência de marca em todas as comunicações
- ✅ Agilizar processos criativos com IA mantendo qualidade e alinhamento
- ✅ Monitorar tendências e insights de mercado automaticamente
- ✅ Facilitar colaboração entre equipes com workflow de aprovação

---

## 👥 PÚBLICO-ALVO

A aplicação é destinada **exclusivamente para uso interno da FEMME**, atendendo os seguintes perfis:

| Perfil | Admin Django | Front-end | Permissões |
|--------|-------------|-----------|------------|
| **Admin/TI** | ✅ Acesso Total | ✅ | Acesso completo a tudo, incluindo configurações do servidor |
| **Gestores** | ❌ Sem acesso | ✅ | Vinculado a área(s). Aprovação, relatórios, visualização completa |
| **Operacionais** | ❌ Sem acesso | ✅ | Vinculado a área(s). Criação de conteúdo, limitado pelas permissões da área |

---

## 📚 ESTRUTURA DA DOCUMENTAÇÃO

Esta documentação está dividida nos seguintes arquivos:

1. **01_IAMKT_Visao_Geral.md** (este arquivo)
   - Visão geral do projeto
   - Objetivos e escopo
   - Público-alvo

2. **02_IAMKT_Arquitetura.md**
   - Arquitetura do sistema
   - Componentes técnicos
   - Integrações externas

3. **03_IAMKT_Apps_Django.md**
   - Estrutura das 4 Django Apps
   - Models de cada app
   - Relacionamentos

4. **04_IAMKT_Funcionalidades_Fase1.md**
   - Geração de Pautas
   - Geração de Posts (imagem + legenda)
   - Simulador de Feed
   - Monitoramento de Trends
   - Pesquisa Web e Insights

5. **05_IAMKT_Base_Conhecimento.md**
   - 7 blocos da Base FEMME
   - Estrutura detalhada
   - Funcionalidades de edição

6. **06_IAMKT_Usuarios_Permissoes.md**
   - Perfis de usuário
   - Áreas organizacionais
   - Sistema de permissões

7. **07_IAMKT_Integracoes_Tecnicas.md**
   - APIs de IA (OpenAI, Gemini, Grok)
   - AWS S3
   - Web Scraping
   - Cache Redis
   - Celery

8. **08_IAMKT_Workflow_Aprovacoes.md**
   - Fluxo de aprovação
   - Estados do conteúdo
   - Opções de aprovação

9. **09_IAMKT_Roadmap.md**
   - Fase 1 (MVP)
   - Fase 2 (Expansão)
   - Cronograma

10. **10_IAMKT_Especificacoes_Tecnicas.md**
    - Stack tecnológica
    - Configurações Docker
    - Variáveis de ambiente
    - Performance e segurança

---

## 🎯 OBJETIVOS ESTRATÉGICOS

### Metas Principais

1. **Reduzir tempo de criação** de conteúdo em 70% mantendo qualidade
2. **Garantir 100% de alinhamento** com diretrizes da marca FEMME
3. **Automatizar monitoramento** de tendências de mercado diariamente
4. **Centralizar aprovações** e facilitar colaboração entre áreas
5. **Gerar insights de dados** para campanhas mais assertivas

---

## 📦 ESCOPO - FASE 1 (MVP)

### Funcionalidades Prioritárias

#### ✅ Base de Conhecimento FEMME
- 7 blocos de informações da marca
- Interface sanfona para edição
- Upload de assets (fontes, logos, imagens)
- Histórico de alterações

#### ✅ Geração de Pautas
- Input: tema, público-alvo, objetivo
- IA gera 5-10 sugestões relevantes
- Alinhado com Base FEMME
- Opção de salvar favoritas

#### ✅ Geração de Posts (Imagem + Legenda)
- Geração de imagem via OpenAI (DALL-E 3) ou Gemini
- Imagem segue paleta de cores FEMME
- Legenda alinhada com tom de voz
- Templates por rede social (Instagram, LinkedIn, Facebook)

#### ✅ Simulador de Feed
- **DIFERENCIAL CRÍTICO**
- Preview de como post aparecerá na rede social
- Suporte: Instagram Feed, Stories, LinkedIn, Facebook
- Visualização de cortes e dimensões corretas

#### ✅ Monitoramento de Trends
- Execução automática: 1x por dia (6h)
- Execução manual: botão sob demanda
- Fontes: Google Trends, Think with Google, Reddit, Twitter/X
- IA analisa relevância para nicho FEMME
- Alertas para tendências críticas

#### ✅ Pesquisa Web e Insights
- Web scraping com Playwright
- Análise de sites concorrentes
- Extração de informações do mercado
- IA resume e gera insights
- Exportação em PDF

#### ✅ Sistema de Aprovação Básico
- Operacional cria → Gestor aprova
- Opções: Aprovar, Solicitar Ajustes, Reprovar
- Notificação por email + in-app
- Aprovação via sistema ou resposta de email

#### ✅ Gestão de Usuários por Áreas
- Áreas gerenciadas via Admin Django
- Permissões por área (quais ferramentas acessar)
- Limites de uso personalizados por área
- Usuário pode estar em múltiplas áreas

---

## 🚀 ESCOPO - FASE 2 (EXPANSÃO)

### Funcionalidades Futuras

#### 📝 Geração de Textos para Blog
- Artigos completos SEO-friendly
- Múltiplos templates (tutorial, case study, listicle)

#### 🎥 Roteiros de Vídeo + Avatar Fê
- Geração de roteiros com IA
- Integração com VEO3 para geração de vídeo
- Avatar "Fê" desenvolvido internamente

#### 📊 Apresentações (PPTX)
- Geração automática de slides
- Templates corporativos

#### 📅 Calendário Editorial
- View mensal/semanal/diária
- Drag-and-drop para agendamento
- Filtros por tipo, área, responsável

#### 🔗 Integração com Redes Sociais
- Postagem automática pós-aprovação
- Meta Business Suite (Instagram/Facebook)
- LinkedIn API
- Twitter API

#### 📚 Biblioteca Completa de Assets
- Upload em lote
- Tags e categorias
- Busca inteligente
- Vinculação com conteúdos gerados

#### 🔍 Insights AWS Bedrock + Athena
- Conexão com banco Athena
- Queries pré-definidas (ex: exames por período)
- IA analisa dados e sugere campanhas
- AWS Bedrock para insights não óbvios

#### 📈 Relatórios e Analytics Avançados
- Dashboard completo de métricas
- Análise de custos de IA
- Performance por usuário/área
- Exportação PDF + envio por email

---

## 🎨 INTERFACE DO USUÁRIO

### Layout Padrão

```
┌─────────────────────────────────────────────────┐
│ Header: Logo | Notificações | Perfil | Área    │
├──────────┬──────────────────────────────────────┤
│          │                                       │
│ Sidebar  │     Área de Conteúdo                 │
│ (Menu)   │                                       │
│          │                                       │
│ ☰        │                                       │
│          │                                       │
│ Dashboard│                                       │
│ Base     │                                       │
│ Ferramen.│                                       │
│ Projetos │                                       │
│ Relatórs │                                       │
│          │                                       │
│ [Admin]  │                                       │
└──────────┴──────────────────────────────────────┘
```

**Características:**
- Sidebar recolhível (ícone ☰)
- Responsivo (mobile: menu hambúrguer)
- Design consistente em todas as páginas
- Sem CSS inline (tudo estruturado em arquivos)

---

## 🎯 PRÓXIMOS PASSOS

Após aprovação desta documentação:

1. **Definir Models Django detalhados** (todas as 4 apps)
2. **Setup do ambiente de desenvolvimento**
3. **Iniciar Fase 1 - Etapa 1**: Models e Estrutura de Dados
4. **Seguir plano de 12 etapas** conforme PLANO_DESENVOLVIMENTO_GENERICO.md

---

## 📞 CONTATOS

| Área | Responsável | Contato |
|------|------------|---------|
| Desenvolvimento | Equipe TI FEMME | ti@femme.com.br |
| Produto/Marketing | Gestão Marketing | marketing@femme.com.br |
| Infraestrutura | DevOps/SysAdmin | infra@femme.com.br |

---

**Documento criado em:** Janeiro 2026  
**Próxima atualização:** Após definição final dos Models
