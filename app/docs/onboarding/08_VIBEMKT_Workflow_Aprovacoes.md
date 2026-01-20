# ✅ IAMKT - WORKFLOW E APROVAÇÕES

**Documento:** 08 de 10  
**Versão:** 1.0  
**Data:** Janeiro 2026

---

## 🎯 VISÃO GERAL

O sistema de aprovação do IAMKT garante que todo conteúdo gerado passe por revisão antes de ser publicado, mantendo qualidade e alinhamento com as diretrizes da marca.

### Princípios

1. **Obrigatório para Publicação**: Conteúdo não aprovado não pode ser publicado
2. **Rastreável**: Histórico completo de aprovações
3. **Flexível**: Aprovação via sistema ou email
4. **Colaborativo**: Comentários e ajustes
5. **Notificações Automáticas**: Emails e alertas in-app

---

## 🔄 FLUXO DE APROVAÇÃO COMPLETO

### Diagrama

```
┌─────────────────────────────────────────────────────────┐
│                  WORKFLOW DE APROVAÇÃO                   │
└─────────────────────────────────────────────────────────┘

  [1] OPERACIONAL                                           
      Cria Conteúdo                                         
          │                                                  
          ▼                                                  
  [2] OPERACIONAL                                           
      Clica "Enviar para Aprovação"                        
          │                                                  
          ├──> Sistema registra solicitação                
          ├──> Status: "aguardando_aprovacao"              
          ├──> Email → Gestor da área                      
          └──> Notificação in-app                          
          │                                                  
          ▼                                                  
  [3] GESTOR                                                
      Recebe notificação                                    
          │                                                  
          ├──> Opção A: Acessa sistema                     
          └──> Opção B: Responde email                     
          │                                                  
          ▼                                                  
  [4] GESTOR REVISA                                         
      │                                                      
      ├──> [APROVAR]                                       
      │    ├──> Status: "aprovado"                         
      │    ├──> Notifica operacional                       
      │    └──> Pode agendar publicação (Fase 2)          
      │                                                      
      ├──> [SOLICITAR AJUSTES]                             
      │    ├──> Status: "em_ajuste"                        
      │    ├──> Adiciona comentários                       
      │    ├──> Notifica operacional                       
      │    └──> Volta para operacional editar              
      │                                                      
      └──> [REPROVAR]                                      
           ├──> Status: "arquivado"                        
           ├──> Justificativa obrigatória                  
           └──> Notifica operacional                       
           │                                                 
           ▼                                                 
  [5] OPERACIONAL                                           
      Se ajustes: edita e reenvia                          
      Se reprovado: arquiva ou refaz                       
```

---

## 📋 ESTADOS DO CONTEÚDO

### Ciclo de Vida

| Status | Descrição | Ações Disponíveis | Quem Pode |
|--------|-----------|-------------------|-----------|
| **rascunho** | Criado, não enviado | Editar, Enviar p/ aprovação, Deletar | Operacional (criador) |
| **aguardando_aprovacao** | Enviado, pendente | Cancelar solicitação | Operacional (criador) |
| **aguardando_aprovacao** | Enviado, pendente | Aprovar, Ajustes, Reprovar | Gestor |
| **em_ajuste** | Devolvido c/ comentários | Editar, Reenviar | Operacional (criador) |
| **aprovado** | Aprovado pelo gestor | Publicar (Fase 2), Exportar | Operacional, Gestor |
| **publicado** | Publicado nas redes (Fase 2) | Visualizar métricas | Operacional, Gestor |
| **arquivado** | Reprovado ou descartado | Visualizar (read-only) | Criador, Gestor |

### Transições Permitidas

```
rascunho
  └──> aguardando_aprovacao
        ├──> aprovado
        ├──> em_ajuste
        │     └──> aguardando_aprovacao
        └──> arquivado

aprovado
  └──> publicado (Fase 2)
```

---

## 📧 NOTIFICAÇÕES

### Eventos que Geram Notificação

| Evento | Destinatário | Canal | Conteúdo |
|--------|--------------|-------|----------|
| **Solicitação Enviada** | Gestor(es) da área | Email + In-app | Link para revisar, preview do conteúdo |
| **Conteúdo Aprovado** | Operacional (criador) | Email + In-app | Confirmação, próximos passos |
| **Ajustes Solicitados** | Operacional (criador) | Email + In-app | Comentários do gestor, link para editar |
| **Conteúdo Reprovado** | Operacional (criador) | Email + In-app | Justificativa, sugestões |
| **Prazo de Resposta** | Gestor | Email | Lembrete (48h sem resposta) |

### Template de Email - Solicitação

```
┌───────────────────────────────────────────────────┐
│  De: noreply@iamkt-femmeintegra.aisuites.com.br│
│  Para: joao.silva@femme.com.br                    │
│  Assunto: [IAMKT] Nova solicitação de aprovação│
├───────────────────────────────────────────────────┤
│                                                    │
│  Olá, João Silva!                                │
│                                                    │
│  Maria Santos solicitou aprovação para:          │
│                                                    │
│  📱 Post Instagram - "Cuide do Coração"           │
│  Área: Marketing                                  │
│  Projeto: Campanha Preventiva Q1                 │
│                                                    │
│  ┌──────────────────────────────────────┐        │
│  │  [Preview da Imagem]                 │        │
│  └──────────────────────────────────────┘        │
│                                                    │
│  Legenda: "Cuide do seu coração! Após os 40..."  │
│                                                    │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━         │
│                                                    │
│  🔗 VER E APROVAR NO SISTEMA                      │
│  https://iamkt-femmeintegra.aisuites.com.br/... │
│                                                    │
│  OU RESPONDER ESTE EMAIL:                         │
│  • Digite "APROVADO" para aprovar                │
│  • Digite "AJUSTES: [seus comentários]"          │
│  • Digite "REPROVADO: [justificativa]"           │
│                                                    │
└───────────────────────────────────────────────────┘
```

### Template In-App

```
┌──────────────────────────────────────────┐
│  🔔 NOTIFICAÇÕES                         │
├──────────────────────────────────────────┤
│                                           │
│  ⏰ NOVA    há 2 minutos                 │
│  📱 Post aguardando sua aprovação        │
│  "Cuide do Coração"                      │
│  Por: Maria Santos (Marketing)           │
│  [ Ver Agora ]                           │
│                                           │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━        │
│                                           │
│  ✅ LIDO    há 1 hora                    │
│  Post "Check-up Executivo" foi aprovado │
│  [ Ver Detalhes ]                        │
│                                           │
└──────────────────────────────────────────┘
```

---

## 🔍 INTERFACE DE APROVAÇÃO

### Dashboard do Gestor - Pendências

```
┌─────────────────────────────────────────────────────┐
│  ✅ APROVAÇÕES PENDENTES                            │
│  [ Todas ] [ Urgentes ] [ Esta Semana ]            │
├─────────────────────────────────────────────────────┤
│                                                      │
│  📱 POST INSTAGRAM                                  │
│  ┌────────────────────────────────────────────┐    │
│  │  [Thumbnail Imagem]  "Cuide do Coração"   │    │
│  │                                             │    │
│  │  Por: Maria Santos                         │    │
│  │  Área: Marketing                           │    │
│  │  Projeto: Campanha Preventiva Q1          │    │
│  │  Enviado: há 2 horas                      │    │
│  │                                             │    │
│  │  Legenda: "Cuide do seu coração..."       │    │
│  │  (ver mais)                                │    │
│  │                                             │    │
│  │  [ 👁️ Preview ] [ ✅ Aprovar ] [ ⚠️ Ajustes ]│    │
│  │  [ ❌ Reprovar ]                           │    │
│  └────────────────────────────────────────────┘    │
│                                                      │
│  📝 TEXTO PARA BLOG                                 │
│  ┌────────────────────────────────────────────┐    │
│  │  "Importância do Check-up..."              │    │
│  │                                             │    │
│  │  Por: Carlos Oliveira                      │    │
│  │  Área: Marketing                           │    │
│  │  Enviado: ontem                            │    │
│  │                                             │    │
│  │  [ 👁️ Preview ] [ ✅ Aprovar ] [ ⚠️ Ajustes ]│    │
│  └────────────────────────────────────────────┘    │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### Modal de Aprovação

```
┌─────────────────────────────────────────────────────┐
│  📱 POST: "Cuide do Coração"                   [X] │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌─────────────────┐                                │
│  │                 │  PREVIEW COMPLETO              │
│  │   [IMAGEM]      │                                │
│  │                 │  Rede: Instagram Feed (1:1)    │
│  │  1080x1080px    │  Template: Feed Padrão         │
│  │                 │                                 │
│  └─────────────────┘  Legenda:                      │
│                       "Cuide do seu coração! Após   │
│                        os 40, exames regulares..."  │
│                                                      │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━         │
│                                                      │
│  📋 INFORMAÇÕES                                      │
│  Criado por: Maria Santos                          │
│  Área: Marketing                                    │
│  Projeto: Campanha Preventiva Q1                   │
│  Modelo IA usado: OpenAI DALL-E 3 + GPT-4         │
│  Custo estimado: R$ 0,25                           │
│  Data criação: 12/01/2026 14:30                    │
│                                                      │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━         │
│                                                      │
│  ✅ APROVAR                                          │
│  ┌────────────────────────────────────────────┐    │
│  │ Comentário (opcional):                     │    │
│  │ [                                          ]│    │
│  │                                             │    │
│  └────────────────────────────────────────────┘    │
│                                                      │
│  ⚙️ OPÇÕES                                           │
│  [ ] Agendar publicação (Fase 2)                   │
│      Data: [__/__/____] Hora: [__:__]              │
│                                                      │
│  [ CONFIRMAR APROVAÇÃO ]                            │
│                                                      │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━         │
│                                                      │
│  ⚠️ SOLICITAR AJUSTES                                │
│  ┌────────────────────────────────────────────┐    │
│  │ Comentários (obrigatório):                 │    │
│  │ [                                          ]│    │
│  │                                             │    │
│  │ Sugestões:                                 │    │
│  │ • Ajustar tom de voz                       │    │
│  │ • Mudar cores da imagem                    │    │
│  │ • Reescrever legenda                       │    │
│  └────────────────────────────────────────────┘    │
│                                                      │
│  [ ENVIAR PARA AJUSTES ]                            │
│                                                      │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━         │
│                                                      │
│  ❌ REPROVAR                                         │
│  ┌────────────────────────────────────────────┐    │
│  │ Justificativa (obrigatório):               │    │
│  │ [                                          ]│    │
│  │                                             │    │
│  └────────────────────────────────────────────┘    │
│                                                      │
│  [ REPROVAR CONTEÚDO ]                              │
│                                                      │
└─────────────────────────────────────────────────────┘
```

---

## 📱 APROVAÇÃO VIA EMAIL

### Como Funciona

1. **Gestor recebe email** com preview do conteúdo
2. **Responde o email** com comando:
   - `APROVADO`
   - `AJUSTES: [comentários]`
   - `REPROVADO: [justificativa]`
3. **Sistema processa** resposta via email parser
4. **Atualiza status** automaticamente
5. **Notifica operacional** da decisão

### Parsing de Email

```python
def processar_resposta_email(email_content, approval_id):
    """
    Processa resposta de aprovação via email
    """
    content = email_content.lower().strip()
    
    approval = Approval.objects.get(id=approval_id)
    
    # APROVADO
    if content.startswith('aprovado'):
        approval.status = 'aprovado'
        approval.respondido_em = timezone.now()
        approval.mensagem_resposta = email_content
        approval.save()
        
        # Atualiza conteúdo
        approval.conteudo.status = 'aprovado'
        approval.conteudo.save()
        
        # Notifica operacional
        notificar_aprovacao(approval)
        
    # AJUSTES
    elif content.startswith('ajustes:'):
        comentarios = content.replace('ajustes:', '').strip()
        
        approval.status = 'em_ajuste'
        approval.respondido_em = timezone.now()
        approval.mensagem_resposta = comentarios
        approval.save()
        
        # Atualiza conteúdo
        approval.conteudo.status = 'em_ajuste'
        approval.conteudo.save()
        
        # Cria comentário
        ApprovalComment.objects.create(
            aprovacao=approval,
            usuario=approval.aprovador,
            comentario=comentarios
        )
        
        # Notifica operacional
        notificar_ajustes(approval, comentarios)
        
    # REPROVADO
    elif content.startswith('reprovado:'):
        justificativa = content.replace('reprovado:', '').strip()
        
        if not justificativa:
            raise ValueError("Justificativa obrigatória")
        
        approval.status = 'reprovado'
        approval.respondido_em = timezone.now()
        approval.mensagem_resposta = justificativa
        approval.save()
        
        # Atualiza conteúdo
        approval.conteudo.status = 'arquivado'
        approval.conteudo.save()
        
        # Notifica operacional
        notificar_reprovacao(approval, justificativa)
        
    else:
        raise ValueError("Comando não reconhecido")
```

### Segurança

- ✅ Valida que email vem do aprovador cadastrado
- ✅ Verifica domínio (@femme.com.br)
- ✅ Token único no email para evitar fraude
- ✅ Registra IP e timestamp no audit log

---

## 💬 COMENTÁRIOS E DISCUSSÃO

### Thread de Comentários

```
┌─────────────────────────────────────────────────────┐
│  💬 COMENTÁRIOS - Post "Cuide do Coração"          │
├─────────────────────────────────────────────────────┤
│                                                      │
│  👤 Maria Santos (Operacional)                      │
│  12/01/2026 14:30                                   │
│  Enviei para aprovação. Usei paleta FEMME e        │
│  tom de voz conforme guideline.                     │
│                                                      │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━         │
│                                                      │
│  👤 João Silva (Gestor)                             │
│  12/01/2026 15:15                                   │
│  Ótimo trabalho! Porém, sugiro mudar o CTA final   │
│  de "Agende seu exame" para "Cuide-se hoje".       │
│  Fica mais alinhado com nosso tom acolhedor.       │
│                                                      │
│  Status alterado: ⚠️ Em Ajuste                      │
│                                                      │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━         │
│                                                      │
│  👤 Maria Santos (Operacional)                      │
│  12/01/2026 15:45                                   │
│  Ajustei conforme solicitado! Reenviando.          │
│                                                      │
│  Status alterado: ⏳ Aguardando Aprovação           │
│                                                      │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━         │
│                                                      │
│  👤 João Silva (Gestor)                             │
│  12/01/2026 16:00                                   │
│  Perfeito! Aprovado. 👍                             │
│                                                      │
│  Status alterado: ✅ Aprovado                        │
│                                                      │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━         │
│                                                      │
│  [ Adicionar Comentário ]                           │
│                                                      │
└─────────────────────────────────────────────────────┘
```

---

## 📊 MÉTRICAS DE APROVAÇÃO

### Dashboard de Métricas (Gestor)

```
┌─────────────────────────────────────────────────────┐
│  📊 MÉTRICAS DE APROVAÇÃO - Marketing               │
│  Período: Janeiro 2026                              │
├─────────────────────────────────────────────────────┤
│                                                      │
│  TAXA DE APROVAÇÃO                                  │
│  ████████████████████░░░░░ 87%                     │
│  (39 aprovados de 45 solicitações)                 │
│                                                      │
│  TEMPO MÉDIO DE RESPOSTA                            │
│  ⏱️ 3.2 horas                                       │
│                                                      │
│  DISTRIBUIÇÃO                                        │
│  ✅ Aprovados na 1ª: 32 (71%)                       │
│  ⚠️ Ajustes solicitados: 7 (16%)                    │
│  ❌ Reprovados: 6 (13%)                             │
│                                                      │
│  MOTIVOS DE AJUSTE MAIS COMUNS                      │
│  1. Tom de voz (3 casos)                           │
│  2. Cores/visual (2 casos)                         │
│  3. CTA inadequado (2 casos)                       │
│                                                      │
│  [ Ver Relatório Completo ]                         │
└─────────────────────────────────────────────────────┘
```

### Relatório para Admin

```
┌─────────────────────────────────────────────────────┐
│  📊 RELATÓRIO GLOBAL DE APROVAÇÕES                  │
│  Janeiro 2026                                       │
├─────────────────────────────────────────────────────┤
│                                                      │
│  POR ÁREA                                            │
│  Marketing:     87% aprovação (45 solicitações)    │
│  Com. Interna:  92% aprovação (25 solicitações)    │
│  RH:            95% aprovação (20 solicitações)    │
│                                                      │
│  GESTORES MAIS RÁPIDOS                              │
│  1. Carlos Oliveira: 1.5h média                    │
│  2. Paula Souza: 2.1h média                        │
│  3. João Silva: 3.2h média                         │
│                                                      │
│  PENDÊNCIAS ANTIGAS                                  │
│  ⚠️ 2 aprovações com +48h sem resposta              │
│                                                      │
│  [ Exportar Relatório ] [ Enviar Lembretes ]       │
└─────────────────────────────────────────────────────┘
```

---

## ⚡ AUTOMAÇÕES

### Lembrete Automático

**Trigger:** Aprovação pendente há 48h

```python
@app.task
def enviar_lembrete_aprovacao():
    """
    Envia lembrete para aprovações pendentes há mais de 48h
    """
    limite = timezone.now() - timedelta(hours=48)
    
    pendentes = Approval.objects.filter(
        status='aguardando_aprovacao',
        created_at__lt=limite,
        lembrete_enviado=False
    )
    
    for approval in pendentes:
        enviar_email_lembrete(
            destinatario=approval.aprovador.email,
            assunto=f"Lembrete: Aprovação pendente há 48h",
            conteudo=f"O conteúdo '{approval.conteudo.titulo}' está aguardando sua aprovação..."
        )
        
        approval.lembrete_enviado = True
        approval.save()
```

### Escalação Automática

**Trigger:** Aprovação pendente há 72h (Fase 2)

```python
@app.task
def escalar_aprovacao():
    """
    Escala aprovação para gestor superior após 72h
    """
    limite = timezone.now() - timedelta(hours=72)
    
    pendentes = Approval.objects.filter(
        status='aguardando_aprovacao',
        created_at__lt=limite,
        escalado=False
    )
    
    for approval in pendentes:
        # Encontra gestor superior
        gestor_superior = encontrar_gestor_superior(approval.aprovador)
        
        # Cria nova approval
        Approval.objects.create(
            conteudo=approval.conteudo,
            solicitante=approval.solicitante,
            aprovador=gestor_superior,
            mensagem_solicitacao=f"[ESCALADO] {approval.mensagem_solicitacao}"
        )
        
        # Marca original como escalado
        approval.escalado = True
        approval.save()
        
        # Notifica
        notificar_escalacao(gestor_superior, approval)
```

---

**Próximo documento:** [09_IAMKT_Roadmap.md](09_IAMKT_Roadmap.md)
