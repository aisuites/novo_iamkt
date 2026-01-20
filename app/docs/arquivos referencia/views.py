from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import (
    BrandCore, PilarEstrategico, Diferencial, 
    SegmentoPublico, TomVoz, TomVozFraseAncora, TomVozNaoUsar,
    IdentidadeVisual, CorIdentidade, ImagemReferencia, FonteIdentidade,
    ContextoComunicacao, StatusConteudo
)


def dashboard(request):
    """
    Dashboard principal do IAMKT.
    Mostra visão geral da base de conhecimento, ferramentas e atividades.
    """
    context = {
        'user_name': request.user.first_name or request.user.username if request.user.is_authenticated else 'Visitante',
        'user_initial': request.user.first_name[0].upper() if request.user.is_authenticated and request.user.first_name else 'V',
    }
    
    # Verificar se existe BrandCore
    try:
        brand_core = BrandCore.objects.first()
        context['has_brand_core'] = True
        context['brand_core'] = brand_core
    except:
        context['has_brand_core'] = False
    
    return render(request, 'core/dashboard.html', context)


def base_femme_form(request, pk=None):
    """
    Formulário de criação/edição da Base FEMME (BrandCore).
    """
    context = {
        'user_name': request.user.first_name or request.user.username if request.user.is_authenticated else 'Visitante',
        'user_initial': request.user.first_name[0].upper() if request.user.is_authenticated and request.user.first_name else 'V',
    }
    
    # Se pk foi fornecido, buscar BrandCore existente
    if pk is not None:
        brand_core = get_object_or_404(BrandCore, pk=pk)
        context['brand_core'] = brand_core
        context['is_edit'] = True
        
        # Carregar dados relacionados
        context['publico_principal'] = brand_core.segmentos.filter(nome_segmento='Público Principal').first()
        context['publicos_secundarios'] = brand_core.segmentos.filter(nome_segmento='Públicos Secundários').first()
        context['segmentos_internos'] = brand_core.segmentos.filter(nome_segmento='Segmentos Internos').first()
        
        context['tom_externo'] = brand_core.tons_voz.filter(tipo=ContextoComunicacao.EXTERNO).first()
        context['tom_interno'] = brand_core.tons_voz.filter(tipo=ContextoComunicacao.INTERNO).first()
        
        context['identidade_visual'] = brand_core.identidade_visual.first()
        context['diferenciais'] = brand_core.diferenciais.all()
        context['concorrencia'] = brand_core.pilares.filter(titulo='Concorrência').first()
        context['fontes_dados_obj'] = brand_core.pilares.filter(titulo='Fontes de Dados').first()
        context['regras_interpretacao_obj'] = brand_core.pilares.filter(titulo='Regras de Interpretação').first()
        
        # Carregar logo e refs visuais
        if context['identidade_visual']:
            context['logo'] = context['identidade_visual'].imagens_referencia.filter(descricao='Logotipo principal').first()
            context['refs_visuais_obj'] = context['identidade_visual'].imagens_referencia.filter(descricao='Referências visuais').first()
        
    else:
        # Verificar se já existe algum BrandCore
        existing = BrandCore.objects.first()
        if existing:
            # Redirecionar para edição do existente
            return redirect('core:base_femme_edit', pk=existing.pk)
        brand_core = None
        context['is_edit'] = False
    
    # Processar POST (salvamento)
    if request.method == 'POST':
        action = request.POST.get('action', 'save')
        
        try:
            # BLOCO 1 - INSTITUCIONAL
            if brand_core:
                # Atualizar existente
                brand_core.nome = request.POST.get('nome_marca', brand_core.nome)
                brand_core.descricao_resumida = request.POST.get('descricao_resumida', brand_core.descricao_resumida)
                brand_core.missao = request.POST.get('missao', brand_core.missao)
                brand_core.visao = request.POST.get('visao', brand_core.visao)
                brand_core.proposito = request.POST.get('valores', brand_core.proposito)
            else:
                # Criar novo
                brand_core = BrandCore.objects.create(
                    nome=request.POST.get('nome_marca', 'FEMME'),
                    descricao_resumida=request.POST.get('descricao_resumida', ''),
                    missao=request.POST.get('missao', ''),
                    visao=request.POST.get('visao', ''),
                    proposito=request.POST.get('valores', ''),
                    criado_por=request.user if request.user.is_authenticated else None
                )
            
            brand_core.save()
            
            # BLOCO 2 - PÚBLICOS
            publico_principal = request.POST.get('publico_principal', '')
            if publico_principal:
                SegmentoPublico.objects.update_or_create(
                    brand_core=brand_core,
                    nome_segmento='Público Principal',
                    defaults={
                        'descricao_segmento': publico_principal
                    }
                )
            
            publicos_secundarios = request.POST.get('publicos_secundarios', '')
            if publicos_secundarios:
                SegmentoPublico.objects.update_or_create(
                    brand_core=brand_core,
                    nome_segmento='Públicos Secundários',
                    defaults={
                        'descricao_segmento': publicos_secundarios
                    }
                )
            
            segmentos_internos = request.POST.get('segmentos_internos', '')
            if segmentos_internos:
                SegmentoPublico.objects.update_or_create(
                    brand_core=brand_core,
                    nome_segmento='Segmentos Internos',
                    defaults={
                        'descricao_segmento': segmentos_internos
                    }
                )
            
            # BLOCO 3 - POSICIONAMENTO
            posicionamento = request.POST.get('posicionamento', '')
            if posicionamento:
                brand_core.historia_resumida = posicionamento
                brand_core.save()
            
            # Diferenciais
            diferenciais_text = request.POST.get('diferenciais', '')
            if diferenciais_text:
                # Limpar diferenciais antigos
                brand_core.diferenciais.all().delete()
                # Criar novos (separados por linha)
                for idx, diferencial in enumerate(diferenciais_text.strip().split('\n')):
                    if diferencial.strip():
                        Diferencial.objects.create(
                            brand_core=brand_core,
                            descricao=diferencial.strip(),
                            ordem=idx
                        )
            
            # Concorrência - salvar em PilarEstrategico com título especial
            concorrencia = request.POST.get('concorrencia', '')
            if concorrencia:
                PilarEstrategico.objects.update_or_create(
                    brand_core=brand_core,
                    titulo='Concorrência',
                    defaults={
                        'descricao': concorrencia,
                        'ordem': 999  # Ordem alta para ficar no final
                    }
                )
            
            # BLOCO 4 - TOM DE VOZ
            tom_externo = request.POST.get('tom_voz_externo', '')
            palavras_chave_externo = request.POST.get('palavras_chave_externo', '')
            
            if tom_externo:
                tom_ext_obj, created = TomVoz.objects.update_or_create(
                    brand_core=brand_core,
                    tipo=ContextoComunicacao.EXTERNO,
                    defaults={'descricao': tom_externo}
                )
                
                # Salvar palavras-chave como frases âncora
                if palavras_chave_externo:
                    tom_ext_obj.frases_ancora.all().delete()
                    for idx, palavra in enumerate(palavras_chave_externo.strip().split('\n')):
                        if palavra.strip():
                            TomVozFraseAncora.objects.create(
                                tom_voz=tom_ext_obj,
                                texto=palavra.strip(),
                                ordem=idx
                            )
            
            tom_interno = request.POST.get('tom_voz_interno', '')
            evitar_linguagem = request.POST.get('evitar_linguagem', '')
            
            if tom_interno:
                tom_int_obj, created = TomVoz.objects.update_or_create(
                    brand_core=brand_core,
                    tipo=ContextoComunicacao.INTERNO,
                    defaults={'descricao': tom_interno}
                )
                
                # Salvar palavras a evitar
                if evitar_linguagem:
                    tom_int_obj.nao_usar.all().delete()
                    for idx, palavra in enumerate(evitar_linguagem.strip().split('\n')):
                        if palavra.strip():
                            TomVozNaoUsar.objects.create(
                                tom_voz=tom_int_obj,
                                texto=palavra.strip(),
                                ordem=idx
                            )
            
            # BLOCO 5 - IDENTIDADE VISUAL
            # Obter ou criar IdentidadeVisual
            identidade_visual, created = IdentidadeVisual.objects.get_or_create(
                brand_core=brand_core
            )
            
            # Tipografia
            tipografia = request.POST.get('tipografia', '')
            if tipografia:
                identidade_visual.tipografia_titulos = tipografia
                identidade_visual.save()
            
            # Cores - processar array dinâmico
            # Limpar cores antigas
            identidade_visual.cores.all().delete()
            
            # Processar cores do formulário
            cores_data = {}
            for key in request.POST:
                if key.startswith('cores['):
                    # Extrair índice e campo: cores[0][hex] ou cores[0][nome]
                    import re
                    match = re.match(r'cores\[(\d+)\]\[(\w+)\]', key)
                    if match:
                        idx, field = match.groups()
                        if idx not in cores_data:
                            cores_data[idx] = {}
                        cores_data[idx][field] = request.POST[key]
            
            # Criar cores
            for idx, cor_data in cores_data.items():
                hex_value = cor_data.get('hex', '')
                nome = cor_data.get('nome', '')
                if hex_value:
                    CorIdentidade.objects.create(
                        identidade_visual=identidade_visual,
                        hex=hex_value,
                        nome_uso=nome,
                        ordem=int(idx)
                    )
            
            # Processar fontes tipográficas
            identidade_visual.fontes.all().delete()  # Limpar fontes antigas
            
            fontes_data = {}
            for key in request.POST:
                if key.startswith('fontes[') and '][' in key:
                    # Extrair índice e campo: fontes[0][nome_fonte]
                    parts = key.replace('fontes[', '').replace(']', '').split('[')
                    if len(parts) == 2:
                        idx, field = parts
                        if idx not in fontes_data:
                            fontes_data[idx] = {}
                        fontes_data[idx][field] = request.POST[key]
            
            # Criar fontes
            for idx, fonte_data in fontes_data.items():
                tipo = fonte_data.get('tipo', 'GOOGLE')
                uso = fonte_data.get('uso', 'TITULO')
                
                if tipo == 'GOOGLE':
                    nome_fonte = fonte_data.get('nome_fonte', '')
                    variante = fonte_data.get('variante', '400')
                    
                    if nome_fonte:
                        FonteIdentidade.objects.create(
                            identidade_visual=identidade_visual,
                            tipo=tipo,
                            nome_fonte=nome_fonte,
                            variante=variante,
                            uso=uso,
                            ordem=int(idx)
                        )
                elif tipo == 'UPLOAD':
                    nome_fonte = fonte_data.get('nome_fonte_upload', '')
                    arquivo_key = f'fontes[{idx}][arquivo]'
                    
                    if arquivo_key in request.FILES:
                        FonteIdentidade.objects.create(
                            identidade_visual=identidade_visual,
                            tipo=tipo,
                            nome_fonte=nome_fonte or 'Custom Font',
                            uso=uso,
                            arquivo_ttf=request.FILES[arquivo_key],
                            ordem=int(idx)
                        )
            
            # BLOCO 6 - DADOS & INSIGHTS
            fontes_dados = request.POST.get('fontes_dados', '')
            regras_interpretacao = request.POST.get('regras_interpretacao', '')
            
            # Salvar fontes de dados como PilarEstrategico
            if fontes_dados:
                PilarEstrategico.objects.update_or_create(
                    brand_core=brand_core,
                    titulo='Fontes de Dados',
                    defaults={
                        'descricao': fontes_dados,
                        'ordem': 998
                    }
                )
            
            # Salvar regras de interpretação como PilarEstrategico
            if regras_interpretacao:
                PilarEstrategico.objects.update_or_create(
                    brand_core=brand_core,
                    titulo='Regras de Interpretação',
                    defaults={
                        'descricao': regras_interpretacao,
                        'ordem': 997
                    }
                )
            
            # Logo URL e Referências Visuais
            logo_url = request.POST.get('logo_url', '')
            if logo_url:
                # Salvar como ImagemReferencia
                ImagemReferencia.objects.update_or_create(
                    identidade_visual=identidade_visual,
                    descricao='Logotipo principal',
                    defaults={
                        'url': logo_url
                    }
                )
            
            refs_visuais = request.POST.get('refs_visuais', '')
            if refs_visuais:
                # Salvar referências visuais como ImagemReferencia
                ImagemReferencia.objects.update_or_create(
                    identidade_visual=identidade_visual,
                    descricao='Referências visuais',
                    defaults={
                        'url': refs_visuais if refs_visuais.startswith('http') else ''
                    }
                )
            
            # Mensagem de sucesso
            if action == 'draft':
                messages.success(request, '💾 Base FEMME salva como rascunho!')
            else:
                messages.success(request, '✅ Base FEMME salva com sucesso!')
            
            # Redirecionar para edição
            return redirect('core:base_femme_edit', pk=brand_core.pk)
            
        except Exception as e:
            messages.error(request, f'❌ Erro ao salvar: {str(e)}')
            context['error'] = str(e)
    
    return render(request, 'core/base_femme_form.html', context)
