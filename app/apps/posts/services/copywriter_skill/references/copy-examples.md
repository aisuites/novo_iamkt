# Exemplos de Copy — Payloads Prontos

Exemplos reais de saída para calibrar qualidade e formato esperado.

---

## Exemplo 1 — Suplemento alimentar, objetivo conversão, Instagram feed

**Briefing**: Produto: Whey Protein sabor chocolate. Objetivo: conversão. Público: homens 25–35 que
treinam 3x/semana. Tom: urgente. Diferencial: dissolve em 10 segundos, sem grumos. CTA: comprar no site.

```json
{
  "briefing_parsed": {
    "produto": "Whey Protein sabor chocolate",
    "objetivo": "conversao",
    "publico": "homens 25–35 que treinam 3x/semana",
    "tom": "urgente",
    "formato": "feed_square",
    "plataforma": "instagram",
    "framework_usado": "PAS",
    "variantes_solicitadas": 2
  },
  "variants": [
    {
      "id": "v1",
      "label": "dor do shaker + solução direta",
      "framework": "PAS",
      "copy": {
        "headline": "Cansado de grumos no seu shake?",
        "body": "Você mistura, mistura e ainda tem aquela pelota no fundo.\n\nNão é falta de técnica — é o produto errado.\n\nO Whey X dissolve em 10 segundos, sem grumos, sem shaker na mão por 3 minutos.\n\nChocolate real. Proteína de verdade. Sem desculpa pra errar a nutrição.",
        "cta": "Garanta o seu com frete grátis hoje",
        "hashtags": ["#wheyprotein", "#suplementacao", "#treino", "#ganhodemassa", "#proteina", "#bodybuilding", "#nutricaoesportiva"],
        "alt_text": "Foto de produto: embalagem do Whey Protein sabor chocolate sobre balcão de academia — Whey X"
      },
      "metrics": {
        "headline_words": 6,
        "body_chars": 271,
        "cta_words": 6,
        "hashtag_count": 7,
        "estimated_read_time_seconds": 7
      },
      "notes": "Framework PAS clássico. O 'problema' é visceral e específico (grumo), não genérico. A solução entra com dado concreto (10 segundos)."
    },
    {
      "id": "v2",
      "label": "gancho numérico + benefício imediato",
      "framework": "Hook+Valor+CTA",
      "copy": {
        "headline": "10 segundos. Sem grumos. Sem drama.",
        "body": "A maioria dos wheys promete sabor e entrega areia dissolvida.\n\nO Whey X foi reformulado para dissolver completo — na colher, no copo, no shaker.\n\nSabor chocolate que parece achocolatado. Sem deixar resíduo.\n\n30g de proteína por dose. Chega de improvisar na nutrição.",
        "cta": "Peça agora e receba em 2 dias",
        "hashtags": ["#wheyprotein", "#suplementacao", "#treino", "#ganhodemassa", "#proteina", "#fitness", "#musculacao"],
        "alt_text": "Foto de produto: embalagem do Whey Protein sabor chocolate com copo de shake ao lado — Whey X"
      },
      "metrics": {
        "headline_words": 6,
        "body_chars": 289,
        "cta_words": 6,
        "hashtag_count": 7,
        "estimated_read_time_seconds": 7
      },
      "notes": "Headline com três afirmações em paralelo cria ritmo. Body usa contraste ('promete X, entrega Y') antes de apresentar o produto."
    }
  ],
  "recommended_variant": "v1",
  "recommendation_reason": "Para objetivo de conversão com público que já conhece o produto (suplementistas ativos), atacar a dor específica (grumo) converte melhor que headline numérica que pode parecer genérica.",
  "design_hints": [
    "Headline em destaque máximo — é o gancho principal; sugerir fonte grande no terço superior da arte",
    "Body tem 4 parágrafos curtos — ideal para carrossel (1 parágrafo por slide) se o designer preferir",
    "CTA deve estar em botão com cor de alto contraste; texto cabe em 1 linha de até 320px",
    "Imagem do produto deve aparecer em destaque — copy referencia a embalagem diretamente"
  ]
}
```

---

## Exemplo 2 — Curso online, objetivo engajamento, Instagram Stories

**Briefing**: Produto: curso de Excel para iniciantes. Objetivo: engajamento (salvar e compartilhar).
Público: profissionais de RH e financeiro sem experiência em Excel. Tom: educativo. Plataforma: Instagram Stories.

```json
{
  "briefing_parsed": {
    "produto": "Curso de Excel para Iniciantes",
    "objetivo": "engajamento",
    "publico": "profissionais de RH e financeiro sem experiência em Excel",
    "tom": "educativo",
    "formato": "stories",
    "plataforma": "instagram",
    "framework_usado": "Hook+Valor+CTA",
    "variantes_solicitadas": 2
  },
  "variants": [
    {
      "id": "v1",
      "label": "dado chocante + CTA de salvamento",
      "framework": "Hook+Valor+CTA",
      "copy": {
        "headline": "73% dos erros de planilha são de iniciante",
        "body": "E a maioria deles você aprende a evitar em 1 hora.\n\nSem fórmulas difíceis.\nSem vídeo de 8 horas.\nSem precisar ser de TI.",
        "cta": "Salva esse slide — você vai precisar",
        "hashtags": ["#excel", "#planilha", "#cursoonline", "#rh", "#financas", "#produtividade"],
        "alt_text": "Slide educativo com fundo azul escuro e texto branco mostrando estatística sobre erros em planilhas Excel"
      },
      "metrics": {
        "headline_words": 9,
        "body_chars": 118,
        "cta_words": 6,
        "hashtag_count": 6,
        "estimated_read_time_seconds": 3
      },
      "notes": "Para Stories, body ultra-curto é obrigatório — o usuário vê por 5–15 segundos. Três linhas paralelas com negação criam ritmo visual e são fáceis de escanear."
    },
    {
      "id": "v2",
      "label": "pergunta de identificação + CTA de compartilhamento",
      "framework": "Hook+Valor+CTA",
      "copy": {
        "headline": "Você ainda abre planilha com medo?",
        "body": "Faz parte. Mas dá pra mudar isso rápido.\n\n3 funções resolvem 80% do seu dia no Excel.\n\nE nenhuma delas é difícil.",
        "cta": "Manda pra aquele amigo que precisa disso",
        "hashtags": ["#excel", "#planilha", "#cursoonline", "#rh", "#dicas", "#aprendizado"],
        "alt_text": "Slide com pergunta em destaque e fundo claro, remetendo a aprendizado de Excel de forma leve e acessível"
      },
      "metrics": {
        "headline_words": 7,
        "body_chars": 131,
        "cta_words": 8,
        "hashtag_count": 6,
        "estimated_read_time_seconds": 3
      },
      "notes": "Pergunta de identificação ('com medo?') gera empatia imediata com o público iniciante. CTA de compartilhamento potencializa o alcance orgânico."
    }
  ],
  "recommended_variant": "v2",
  "recommendation_reason": "Para engajamento em Stories, pergunta de identificação gera mais respostas e compartilhamentos do que dado estatístico. O público-alvo (RH/financeiro) se identifica emocionalmente com a pergunta.",
  "design_hints": [
    "Stories: headline deve ocupar pelo menos 40% da tela — fonte grande, máx 2 linhas",
    "Body de v1 tem 3 linhas paralelas — ideal para animar entrada de cada linha (slide animado)",
    "CTA deve aparecer na metade inferior da tela, fora da zona de perfil (topo 250px)",
    "Usar fundo sólido ou gradiente — facilita leitura do texto em 3 segundos"
  ]
}
```

---

## Exemplo 3 — E-commerce de moda, objetivo awareness, Instagram Feed

**Briefing**: Produto: coleção de verão. Objetivo: awareness. Público: mulheres 20–35, classe B/C.
Tom: inspiracional. Diferencial: peças leves, sustentáveis, preço acessível.

```json
{
  "briefing_parsed": {
    "produto": "Coleção de Verão — linha sustentável",
    "objetivo": "awareness",
    "publico": "mulheres 20–35, classe B/C",
    "tom": "inspiracional",
    "formato": "feed_portrait",
    "plataforma": "instagram",
    "framework_usado": "FAB",
    "variantes_solicitadas": 2
  },
  "variants": [
    {
      "id": "v1",
      "label": "leveza como estilo de vida",
      "framework": "FAB",
      "copy": {
        "headline": "Leve por fora, consciente por dentro",
        "body": "Nossa coleção de verão foi feita com tecidos naturais que respiram com você.\n\nCada peça usa 40% menos água no processo de fabricação — sem abrir mão do caimento e do preço justo.\n\nVerão é pra ser vivido, não carregado.",
        "cta": "Descubra a coleção completa",
        "hashtags": ["#modasustentavel", "#verao2025", "#modafeminina", "#sustentabilidade", "#modaconsciente", "#estilodevida", "#moda"],
        "alt_text": "Foto editorial: modelo usando vestido leve da coleção de verão em ambiente ao ar livre com luz natural"
      },
      "metrics": {
        "headline_words": 6,
        "body_chars": 246,
        "cta_words": 4,
        "hashtag_count": 7,
        "estimated_read_time_seconds": 6
      },
      "notes": "FAB aplicado: Feature (tecido natural), Advantage (40% menos água, caimento), Benefit (leveza, verão vivido). Dado concreto de sustentabilidade diferencia da comunicação vaga do segmento."
    },
    {
      "id": "v2",
      "label": "storytelling do verão + pertencimento",
      "framework": "Storytelling",
      "copy": {
        "headline": "O verão não espera você estar pronta",
        "body": "Mas a gente preparou uma coleção que te deixa pronta em segundos.\n\nTecidos que não grudam, cores que não desbotam, preços que não assustam.\n\nFeito pra quem vive de verdade — e quer parecer que se importou muito.",
        "cta": "Vem ver o que chegou",
        "hashtags": ["#modafeminina", "#verao2025", "#moda", "#modabrasileira", "#estilo", "#colecaoverão", "#modaconsciente"],
        "alt_text": "Foto editorial: modelo sorrindo com vestido da coleção de verão em cenário de praia ou área aberta"
      },
      "metrics": {
        "headline_words": 8,
        "body_chars": 238,
        "cta_words": 4,
        "hashtag_count": 7,
        "estimated_read_time_seconds": 6
      },
      "notes": "Abordagem de storytelling com humor leve na última frase ('quer parecer que se importou muito'). Conecta com público que quer praticidade sem abrir mão da aparência."
    }
  ],
  "recommended_variant": "v1",
  "recommendation_reason": "Para awareness com diferencial de sustentabilidade, dado concreto (40% menos água) ancora a credibilidade da marca e diferencia de comunicação apenas emocional, comum no segmento.",
  "design_hints": [
    "Headline curta — pode ser sobreposta diretamente na foto editorial em fonte grande",
    "Body tem 3 parágrafos curtos — cabe confortavelmente na legenda sem 'ver mais'",
    "Foto editorial de alta qualidade é essencial — copy de awareness depende do visual para o primeiro impacto",
    "CTA simples e curto ('Descubra a coleção') não compete com a headline — manter como texto menor"
  ]
}
```
