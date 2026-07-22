"""
Arquetipos da THERMOMIX no dialeto AUTORADO (medicao visual sobre referencia).

Este dialeto e o formato de AUTORIA: coordenadas normalizadas (bbox_norm 0-1),
blocos por categoria e conteudo-exemplo com segmentos (trechos com cor/peso
proprios). E o mesmo formato que o futuro agente extrator (Fase 2 do plano)
emitira a partir de wireframe+imagem. A conversao para a spec v3 do engine
(services/thermomix/convert.py: authored_to_v3) acontece no seed — o banco
(PostArchetype.spec) guarda a spec v3 pronta.

Decisoes do dono (2026-07-21/22):
  - verde = o da PALETA da KB (#00AC46), nao o hex estimado da referencia;
  - selo (circulo) e pill seguem o contrato do CTA unificado (background_color
    + radius + texto centralizado);
  - lockups/icones serao subidos na KB (asset_ref abaixo indica o SLOT, o
    arquivo e ligado na aplicacao);
  - foto de fundo e retrato vem do MODAL (usage_type 'fundo' / 'pessoa');
    sem upload de fundo -> Gemini gera pela descricao do post.
"""

VERDE = '#00AC46'          # primaria da paleta thermomix na KB (dono, 2026-07-21)
TEXTO_ESCURO = '#23282A'   # cinza-escuro da paleta da KB
BRANCO = '#FFFFFF'

TMX_A = {
    'meta': {
        'schema_version': 1,
        'id': 'tmx-A',
        'marca': 'thermomix',
        'nome': 'Workshop: foto full-bleed + infos + retrato',
        'medicao': 'estimativa-visual',
        'formato': 'feed',
        'dimensoes': {'w': 1080, 'h': 1350},
    },

    'fundo': {
        'tipo': 'foto',
        'notas': ('Upload do usuario (usage_type=fundo); sem upload a IA gera '
                  'pela descricao. Scrim escuro degrade no topo p/ legibilidade.'),
        'scrim_topo': {'alpha': 140, 'ate_norm': 0.35},
    },

    'tokens': {
        'cores': {'verde': VERDE, 'texto_escuro': TEXTO_ESCURO, 'branco': BRANCO},
        # nomes de CustomFont da KB (Vorwerk); resolvidos em assets.py
        'tipografia': {'display': 'Vorwerk-Bold', 'corpo': 'Vorwerk-Medium',
                       'corpo_bold': 'Vorwerk-Bold'},
    },

    'blocos': [
        {
            'categoria': 'LOGOTIPO',
            'key': 'lockup_marca',
            'label': 'Lockup thermomix workshop',
            # tamanho/posicao de referencia do dono (prints 2026-07-22):
            # largura 59.5%; caixa JUSTA p/ o aspecto ~3.6:1 do SVG novo
            'bbox_norm': [0.085, 0.075, 0.595, 0.132],
            'asset_ref': 'brand_lockup',
        },
        {
            'categoria': 'SELO',
            'key': 'selo',
            'label': 'Selo cidade',
            'bbox_norm': [0.72, 0.072, 0.172, 0.138],
            'forma': {'tipo': 'circulo', 'cor': 'verde'},
            # tamanhos/pesos ajustados pelo dono no editor (prints 2026-07-22)
            'conteudo_fixo': {
                'align': 'center', 'valign': 'center',
                'linhas': [
                    {'key': 'selo_cidade', 'font_size_px': 34, 'segmentos': [
                        {'t': 'São Paulo', 'cor': 'branco', 'weight': 400}]},
                    {'key': 'selo_estado', 'font_size_px': 63, 'segmentos': [
                        {'t': 'SP', 'cor': 'branco', 'weight': 700}]},
                ],
            },
        },
        {
            'categoria': 'TITULO',
            'key': 'titulo',
            'label': 'Titulo do workshop',
            'bbox_norm': [0.082, 0.222, 0.52, 0.147],
            'texto': {'familia': 'display', 'weight': 700, 'font_size_px': 94,
                      'min_font_px': 60, 'line_height': 1.05, 'align': 'left',
                      'max_linhas': 2, 'overflow': 'shrink', 'cor': 'branco'},
            'exemplo': 'Cozinha do Dia a dia',
        },
        {
            'categoria': 'LISTA',
            'key': 'faixa_data',
            'label': 'Data e horario',
            'bbox_norm': [0.082, 0.403, 0.46, 0.10],
            'forma': {'tipo': 'faixa', 'cor': 'branco', 'opacidade': 0.75},
            'icones': [
                {'ref': 'icone_calendario', 'bbox_norm': [0.086, 0.408, 0.051, 0.041]},
            ],
            'indent_norm': 0.065,
            'linhas': [
                {'key': 'data', 'font_size_px': 60, 'familia': 'corpo_bold',
                 'segmentos': [{'t': '27/07', 'cor': 'verde', 'weight': 700}]},
                {'key': 'horarios', 'font_size_px': 42, 'familia': 'corpo',
                 'segmentos': [
                     {'t': 'às ', 'cor': 'texto_escuro', 'weight': 400},
                     {'t': '14h30', 'cor': 'texto_escuro', 'weight': 700},
                     {'t': ' ou ', 'cor': 'texto_escuro', 'weight': 400},
                     {'t': '18h30', 'cor': 'texto_escuro', 'weight': 700}]},
            ],
        },
        {
            'categoria': 'LISTA',
            'key': 'faixa_infos',
            'label': 'Infos fixas',
            'bbox_norm': [0.082, 0.512, 0.46, 0.125],
            'forma': {'tipo': 'faixa', 'cor': 'branco', 'opacidade': 0.75},
            'icones': [
                {'ref': 'icone_pessoas', 'bbox_norm': [0.086, 0.517, 0.051, 0.038]},
                {'ref': 'icone_whatsapp', 'bbox_norm': [0.086, 0.566, 0.051, 0.038]},
            ],
            'indent_norm': 0.065,
            'linhas': [
                {'key': 'modalidade', 'font_size_px': 42, 'familia': 'corpo',
                 'segmentos': [
                     {'t': 'Presencial', 'cor': 'verde', 'weight': 700},
                     {'t': ' ou ', 'cor': 'texto_escuro', 'weight': 400},
                     {'t': 'online', 'cor': 'verde', 'weight': 700}]},
                {'key': 'reserva_1', 'font_size_px': 42, 'familia': 'corpo',
                 'segmentos': [
                     {'t': 'Reserve sua vaga através', 'cor': 'texto_escuro',
                      'weight': 400}]},
                {'key': 'reserva_2', 'font_size_px': 42, 'familia': 'corpo',
                 'segmentos': [
                     {'t': 'do WhatsApp ', 'cor': 'texto_escuro', 'weight': 400},
                     {'t': '(11) 94353-2087', 'cor': 'texto_escuro', 'weight': 700},
                     {'t': '.', 'cor': 'texto_escuro', 'weight': 400}]},
            ],
        },
        {
            'categoria': 'ASSET_RETRATO',
            'key': 'retrato',
            'label': 'Retrato apresentadora',
            'bbox_norm': [0.07, 0.70, 0.19, 0.30],
            'z': 1,
            'notas': 'Upload do usuario (usage_type=pessoa); sangra na base.',
        },
        {
            'categoria': 'SELO',
            'key': 'pill_nome',
            'label': 'Pill nome apresentadora',
            'bbox_norm': [0.176, 0.828, 0.297, 0.044],
            'z': 2,
            'forma': {'tipo': 'pill', 'cor': 'branco'},
            'conteudo_fixo': {
                'align': 'center', 'valign': 'center',
                'linhas': [
                    {'key': 'apresentadora', 'font_size_px': 26, 'segmentos': [
                        {'t': 'Com ', 'cor': 'texto_escuro', 'weight': 400},
                        {'t': 'Carina Boniatti', 'cor': 'verde', 'weight': 700}]},
                ],
            },
        },
        {
            'categoria': 'ASSINATURA',
            'key': 'assinatura',
            'label': 'Lockup distribuidor',
            # posicao/tamanho ajustados pelo dono no editor (prints 2026-07-22)
            'bbox_norm': [0.30, 0.855, 0.53, 0.145],
            'asset_ref': 'distribuidor',
        },
    ],
}

TMX_A_STORY = {
    'meta': {
        'schema_version': 1,
        'id': 'tmx-A_story',
        'marca': 'thermomix',
        'nome': 'Workshop: foto full-bleed + infos + retrato (story)',
        'medicao': 'estimativa-visual',
        'formato': 'story',
        'dimensoes': {'w': 1080, 'h': 1920},
        # safe area IG story (0.14 topo / 0.20 base) — blocos de TEXTO dentro;
        # retrato/pill/assinatura aceitam a zona de risco (fiel a arte original)
        'safe_area': {'topo_norm': 0.14, 'base_norm': 0.20},
    },

    'fundo': {
        'tipo': 'foto',
        'notas': ('Mesma foto da variante feed, reenquadrada 9:16 (upload '
                  'usage_type=fundo; sem upload a IA gera). Scrim no topo.'),
        'scrim_topo': {'alpha': 140, 'ate_norm': 0.30},
    },

    'tokens': {
        'cores': {'verde': VERDE, 'texto_escuro': TEXTO_ESCURO, 'branco': BRANCO},
        'tipografia': {'display': 'Vorwerk-Bold', 'corpo': 'Vorwerk-Medium',
                       'corpo_bold': 'Vorwerk-Bold'},
    },

    'blocos': [
        # ---- overlays padrao (prints do dono 2026-07-22; primeiro = fundo) ----
        {
            'categoria': 'OVERLAY',
            'key': 'overlay_luz',
            'label': 'Overlay luz esquerda',
            'bbox_norm': [0.0, 0.0, 1.0, 1.0],
            'grad': {'tipo': 'linear', 'angulo': 90, 'escala': 100, 'stops': [
                {'cor': 'branco', 'opacidade': 100, 'pos': 0},
                {'cor': 'branco', 'opacidade': 0, 'pos': 100}]},
        },
        {
            'categoria': 'OVERLAY',
            'key': 'overlay_scrim',
            'label': 'Overlay scrim topo',
            'bbox_norm': [0.0, 0.0, 1.0, 1.0],
            'grad': {'tipo': 'linear', 'angulo': 180, 'escala': 40, 'stops': [
                {'cor': '#000000', 'opacidade': 45, 'pos': 0},
                {'cor': 'branco', 'opacidade': 0, 'pos': 100}]},
        },
        {
            'categoria': 'LOGOTIPO',
            'key': 'lockup_marca',
            'label': 'Lockup thermomix workshop',
            # mesma largura de referencia da feed (59.5%), caixa justa 3.6:1
            'bbox_norm': [0.085, 0.100, 0.595, 0.093],
            'asset_ref': 'brand_lockup',
        },
        {
            'categoria': 'SELO',
            'key': 'selo',
            'label': 'Selo cidade',
            'bbox_norm': [0.73, 0.106, 0.175, 0.098],
            'forma': {'tipo': 'circulo', 'cor': 'verde'},
            # tamanhos/pesos = defaults aprovados pelo dono na variante feed
            'conteudo_fixo': {
                'align': 'center', 'valign': 'center',
                'linhas': [
                    {'key': 'selo_cidade', 'font_size_px': 34, 'segmentos': [
                        {'t': 'São Paulo', 'cor': 'branco', 'weight': 400}]},
                    {'key': 'selo_estado', 'font_size_px': 63, 'segmentos': [
                        {'t': 'SP', 'cor': 'branco', 'weight': 700}]},
                ],
            },
        },
        {
            'categoria': 'TITULO',
            'key': 'titulo',
            'label': 'Titulo do workshop',
            'bbox_norm': [0.082, 0.222, 0.52, 0.103],
            'texto': {'familia': 'display', 'weight': 700, 'font_size_px': 94,
                      'min_font_px': 60, 'line_height': 1.05, 'align': 'left',
                      'max_linhas': 2, 'overflow': 'shrink', 'cor': 'branco',
                      # sombra padrao (print do dono 2026-07-22)
                      'sombra': {'dx': 2, 'dy': 3, 'blur': 16,
                                 'opacidade': 50, 'cor': '#000000'}},
            'exemplo': 'Cozinha do Dia a dia',
        },
        {
            'categoria': 'LISTA',
            'key': 'faixa_data',
            'label': 'Data e horario',
            'bbox_norm': [0.082, 0.366, 0.46, 0.072],
            'forma': {'tipo': 'faixa', 'cor': 'branco', 'opacidade': 0.75},
            'oculto': True,
            'icones': [
                {'ref': 'icone_calendario', 'bbox_norm': [0.086, 0.369, 0.051, 0.029]},
            ],
            'indent_norm': 0.065,
            'linhas': [
                {'key': 'data', 'font_size_px': 60, 'familia': 'corpo_bold',
                 'segmentos': [{'t': '27/07', 'cor': 'verde', 'weight': 700}]},
                {'key': 'horarios', 'font_size_px': 42, 'familia': 'corpo',
                 'segmentos': [
                     {'t': 'às ', 'cor': 'texto_escuro', 'weight': 400},
                     {'t': '14h30', 'cor': 'texto_escuro', 'weight': 700},
                     {'t': ' ou ', 'cor': 'texto_escuro', 'weight': 400},
                     {'t': '18h30', 'cor': 'texto_escuro', 'weight': 700}]},
            ],
        },
        {
            'categoria': 'LISTA',
            'key': 'faixa_infos',
            'label': 'Infos fixas',
            'bbox_norm': [0.082, 0.447, 0.46, 0.097],
            'forma': {'tipo': 'faixa', 'cor': 'branco', 'opacidade': 0.75},
            'oculto': True,
            'icones': [
                {'ref': 'icone_pessoas', 'bbox_norm': [0.086, 0.450, 0.051, 0.029]},
                {'ref': 'icone_whatsapp', 'bbox_norm': [0.086, 0.487, 0.051, 0.029]},
            ],
            'indent_norm': 0.065,
            'linhas': [
                {'key': 'modalidade', 'font_size_px': 42, 'familia': 'corpo',
                 'segmentos': [
                     {'t': 'Presencial', 'cor': 'verde', 'weight': 700},
                     {'t': ' ou ', 'cor': 'texto_escuro', 'weight': 400},
                     {'t': 'online', 'cor': 'verde', 'weight': 700}]},
                {'key': 'reserva_1', 'font_size_px': 42, 'familia': 'corpo',
                 'segmentos': [
                     {'t': 'Reserve sua vaga através', 'cor': 'texto_escuro',
                      'weight': 400}]},
                {'key': 'reserva_2', 'font_size_px': 42, 'familia': 'corpo',
                 'segmentos': [
                     {'t': 'do WhatsApp ', 'cor': 'texto_escuro', 'weight': 400},
                     {'t': '(11) 94353-2087', 'cor': 'texto_escuro', 'weight': 700},
                     {'t': '.', 'cor': 'texto_escuro', 'weight': 400}]},
            ],
        },
        {
            'categoria': 'ASSET_RETRATO',
            'key': 'retrato',
            'label': 'Retrato apresentadora',
            'bbox_norm': [0.07, 0.75, 0.20, 0.25],
            'z': 1,
            'notas': 'Upload do usuario (usage_type=pessoa); sangra na base.',
        },
        {
            'categoria': 'SELO',
            'key': 'pill_nome',
            'label': 'Pill nome apresentadora',
            'bbox_norm': [0.19, 0.858, 0.30, 0.033],
            'z': 2,
            'forma': {'tipo': 'pill', 'cor': 'branco'},
            'conteudo_fixo': {
                'align': 'center', 'valign': 'center',
                'linhas': [
                    {'key': 'apresentadora', 'font_size_px': 26, 'segmentos': [
                        {'t': 'Com ', 'cor': 'texto_escuro', 'weight': 400},
                        {'t': 'Carina Boniatti', 'cor': 'verde', 'weight': 700}]},
                ],
            },
        },
        {
            'categoria': 'ASSINATURA',
            'key': 'assinatura',
            'label': 'Lockup distribuidor',
            'bbox_norm': [0.27, 0.92, 0.46, 0.05],
            'asset_ref': 'distribuidor',
        },
    ],
}

AUTHORED = {'tmx-A': TMX_A, 'tmx-A_story': TMX_A_STORY}
