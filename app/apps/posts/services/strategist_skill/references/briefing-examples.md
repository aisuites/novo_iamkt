# Exemplos de Payloads — Strategy & Briefing

---

## Exemplo 1 — Briefing promocional direto (texto de cliente)

**Input recebido:**
> "Preciso de um post pro insta da loja de roupas femininas. Promoção de inverno, 40% off
> em toda a coleção. Só até domingo. Público são mulheres de 25 a 40 anos. Cores da marca
> são rose gold e preto."

```json
{
  "briefing_meta": {
    "source": "texto_livre",
    "confidence": "medium",
    "missing_fields": ["nome_da_marca", "imagem_produto", "cta_destino"]
  },
  "intention": {
    "primary": "promocional",
    "secondary": "conversao_direta",
    "visual_triggers": [
      "40% off → número grande em destaque; elemento de preço riscado recomendado",
      "só até domingo → barra de urgência; cor de alerta (vermelho ou laranja sobre rose gold)"
    ]
  },
  "audience": {
    "profile": "Mulheres, 25–40 anos, consumidoras de moda feminina",
    "context": "B2C_lifestyle",
    "platform": "instagram",
    "emotional_driver": "aspiração + senso de oportunidade (não perder a promoção)",
    "pain_point": "Medo de perder oferta limitada; desejo de renovar guarda-roupa com custo menor"
  },
  "brand_tone": {
    "verbal": "descontraido",
    "visual": "jovem",
    "contrast_level": "high",
    "whitespace": "balanced",
    "source": "briefing_explicito"
  },
  "format": {
    "type": "feed_square",
    "dimensions_px": { "width": 1080, "height": 1080 },
    "safe_zone_inset_px": { "top": 80, "right": 80, "bottom": 80, "left": 80 }
  },
  "visual_direction": {
    "hierarchy": [
      { "layer": 1, "element": "40% OFF", "role": "impacto imediato — precisa parar o scroll" },
      { "layer": 2, "element": "coleção de inverno + prazo", "role": "contexto e urgência" },
      { "layer": 3, "element": "CTA + logo", "role": "ação e identidade" }
    ],
    "composition": "Número '40% OFF' dominando o centro/topo. Produto ou modelo no canto inferior. CTA com fundo contrastante na base.",
    "color_mood": "Rose gold como base; preto para tipografia de impacto; toque de vermelho ou laranja apenas no elemento de urgência (prazo)",
    "typography_style": "sans bold para o número; sans regular para corpo",
    "image_style": "produto hero ou modelo usando peça da coleção",
    "special_elements": ["badge de desconto", "barra de urgência com prazo 'Só até domingo'"]
  },
  "copy_direction": {
    "framework": "PAS",
    "angle": "Oportunidade escassa — urgência de prazo + magnitude do desconto",
    "key_message": "40% de desconto em toda a coleção — só até domingo",
    "cta_type": "compra",
    "tone_notes": "Copy curto e direto. Número em destaque. Prazo explícito. Verbo no imperativo no CTA."
  },
  "priority_chain": {
    "user_explicit": ["plataforma: instagram", "desconto: 40%", "prazo: domingo", "público: mulheres 25–40", "cores: rose gold e preto"],
    "reference_visual": [],
    "brand_kb": [],
    "inferred": ["formato: feed_square (padrão Instagram sem especificação)", "tom: descontraído (segmento moda feminina B2C)", "composição: número em destaque (intenção promocional)"]
  },
  "flags": [
    {
      "type": "warning",
      "message": "Nome da marca não identificado no briefing — logo/marca pode ficar ausente da peça",
      "affects": "designer"
    },
    {
      "type": "suggestion",
      "message": "Versão para Stories recomendada para maximizar urgência — Stories têm taxa de CTA maior para promoções com prazo",
      "affects": "ambos"
    }
  ]
}
```

---

## Exemplo 2 — Briefing de lançamento B2B (LinkedIn)

**Input recebido:**
> "Vamos lançar uma nova funcionalidade no nosso SaaS de gestão de projetos — integração
> nativa com Slack e Teams. Queremos anunciar para gestores de TI e PMOs. LinkedIn é o canal
> principal. Tom da marca é técnico mas acessível. Precisamos de credibilidade, não de hype."

```json
{
  "briefing_meta": {
    "source": "texto_livre",
    "confidence": "high",
    "missing_fields": ["nome_do_produto", "data_de_disponibilidade", "imagem_da_feature"]
  },
  "intention": {
    "primary": "lancamento",
    "secondary": "awareness",
    "visual_triggers": [
      "integração nativa → ícones do Slack e Teams em destaque; layout técnico",
      "credibilidade, não hype → composição limpa; sem grafismos excessivos"
    ]
  },
  "audience": {
    "profile": "Gestores de TI e PMOs, tomadores de decisão técnica, empresas mid-to-large",
    "context": "B2B",
    "platform": "linkedin",
    "emotional_driver": "Eficiência operacional; redução de fricção entre ferramentas; justificativa racional para adoção",
    "pain_point": "Excesso de ferramentas desconectadas que forçam mudança de contexto constante"
  },
  "brand_tone": {
    "verbal": "profissional",
    "visual": "confiavel",
    "contrast_level": "medium",
    "whitespace": "generous",
    "source": "briefing_explicito"
  },
  "format": {
    "type": "feed_landscape",
    "dimensions_px": { "width": 1200, "height": 628 },
    "safe_zone_inset_px": { "top": 60, "right": 60, "bottom": 60, "left": 60 }
  },
  "visual_direction": {
    "hierarchy": [
      { "layer": 1, "element": "headline de lançamento + logos Slack/Teams", "role": "impacto e reconhecimento imediato" },
      { "layer": 2, "element": "benefício principal em 1 linha", "role": "proposta de valor racional" },
      { "layer": 3, "element": "CTA + logo da marca", "role": "próximo passo e credibilidade" }
    ],
    "composition": "Layout dividido: esquerda com texto, direita com screenshot da integração ou ícones das plataformas. Grid limpo, muito respiro.",
    "color_mood": "Azul corporativo ou cor principal da marca; branco; cinza claro. Sem saturação excessiva. Logos Slack/Teams devem aparecer nas cores originais.",
    "typography_style": "sans-serif; hierarquia clara; peso medium para headline",
    "image_style": "screenshot da integração ou mockup de interface; ícones técnicos",
    "special_elements": ["badge 'Novo' ou 'Disponível agora'", "logos das plataformas integradas (Slack, Teams)"]
  },
  "copy_direction": {
    "framework": "FAB",
    "angle": "Feature técnica com benefício de produtividade mensurável — eliminar troca de contexto",
    "key_message": "Gerencie projetos de onde sua equipe já está — sem mudar de ferramenta",
    "cta_type": "descoberta",
    "tone_notes": "Vocabulário técnico acessível. Dado ou métrica se disponível. Sem exclamações. CTA formal: 'Saiba mais' ou 'Veja como funciona'."
  },
  "priority_chain": {
    "user_explicit": ["plataforma: linkedin", "audiência: gestores de TI e PMOs", "tom: técnico mas acessível", "objetivo: credibilidade, não hype", "feature: integração Slack e Teams"],
    "reference_visual": [],
    "brand_kb": [],
    "inferred": ["formato: feed_landscape (padrão LinkedIn)", "composição: split layout (lançamento técnico B2B)", "framework: FAB (awareness de feature)"]
  },
  "flags": [
    {
      "type": "warning",
      "message": "Nome do produto SaaS não informado — placeholder necessário na arte",
      "affects": "designer"
    },
    {
      "type": "suggestion",
      "message": "Incluir um dado de eficiência ('economize X horas/semana') aumentaria conversão de cliques em posts LinkedIn para público PMO",
      "affects": "copywriter"
    }
  ]
}
```

---

## Exemplo 3 — Briefing vago (confidence low)

**Input recebido:**
> "Faz um post bonito pro nosso restaurante"

```json
{
  "briefing_meta": {
    "source": "texto_livre",
    "confidence": "low",
    "missing_fields": ["intencao", "plataforma", "publico", "oferta_ou_mensagem", "tom_da_marca", "nome_do_restaurante"]
  },
  "intention": {
    "primary": "awareness",
    "secondary": null,
    "visual_triggers": [
      "restaurante → foto de prato ou ambiente; atmosfera de hospitalidade inferida"
    ]
  },
  "audience": {
    "profile": "Clientes de restaurante — inferido como B2C local",
    "context": "B2C_lifestyle",
    "platform": "instagram",
    "emotional_driver": "Prazer, socialização, experiência gastronômica",
    "pain_point": "Não identificado no briefing"
  },
  "brand_tone": {
    "verbal": "descontraido",
    "visual": "inspiracional",
    "contrast_level": "medium",
    "whitespace": "balanced",
    "source": "segmento_inferido"
  },
  "format": {
    "type": "feed_square",
    "dimensions_px": { "width": 1080, "height": 1080 },
    "safe_zone_inset_px": { "top": 80, "right": 80, "bottom": 80, "left": 80 }
  },
  "visual_direction": {
    "hierarchy": [
      { "layer": 1, "element": "foto do prato ou ambiente", "role": "apelo sensorial e identidade" },
      { "layer": 2, "element": "nome do restaurante ou tagline", "role": "marca" },
      { "layer": 3, "element": "CTA leve", "role": "engajamento" }
    ],
    "composition": "Foto hero ocupando a maior parte da arte. Texto sobreposto com overlay suave. Logo/nome do restaurante em posição de destaque.",
    "color_mood": "Tons quentes (âmbar, marrom, creme) — remetem a gastronomia e hospitalidade. Paleta a confirmar com identidade da marca.",
    "typography_style": "serifada elegante ou sans-serif limpa — a confirmar com brand guide",
    "image_style": "editorial de prato ou ambiente — foto de alta qualidade obrigatória",
    "special_elements": []
  },
  "copy_direction": {
    "framework": "Hook+Valor+CTA",
    "angle": "Experiência sensorial — apelar ao prazer da refeição",
    "key_message": "A confirmar — briefing não especifica mensagem principal",
    "cta_type": "engajamento",
    "tone_notes": "Tom acolhedor e sensorial. Copy curto. Sem promoção (não mencionada no briefing)."
  },
  "priority_chain": {
    "user_explicit": ["tipo de negócio: restaurante"],
    "reference_visual": [],
    "brand_kb": [],
    "inferred": ["intencao: awareness (padrão para briefing vago de restaurante)", "plataforma: instagram (padrão B2C local)", "tom: inspiracional (segmento gastronomia)", "composição: foto hero (padrão restaurante)"]
  },
  "flags": [
    {
      "type": "blocker",
      "message": "Nome do restaurante não informado — arte não pode ser finalizada sem ele",
      "affects": "designer"
    },
    {
      "type": "blocker",
      "message": "Nenhuma mensagem ou oferta específica no briefing — copywriter não tem ângulo concreto para trabalhar",
      "affects": "copywriter"
    },
    {
      "type": "warning",
      "message": "Confidence baixo — 6 de 7 campos críticos foram inferidos. Recomendado solicitar ao orquestrador um refinamento do briefing antes de gerar a arte.",
      "affects": "ambos"
    }
  ]
}
```
