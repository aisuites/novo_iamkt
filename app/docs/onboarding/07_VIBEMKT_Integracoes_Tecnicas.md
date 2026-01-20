# 🔌 IAMKT - INTEGRAÇÕES TÉCNICAS

**Documento:** 07 de 10  
**Versão:** 1.0  
**Data:** Janeiro 2026

---

## 🎯 VISÃO GERAL

O IAMKT integra múltiplos serviços externos para fornecer funcionalidades completas de geração de conteúdo, armazenamento e análise de dados.

### Stack de Integrações

```
┌─────────────────────────────────────────┐
│          IAMKT PLATFORM               │
├─────────────────────────────────────────┤
│                                          │
│  APIs IA          Storage      Scraping │
│  ├─ OpenAI       ├─ AWS S3     ├─ Play │
│  ├─ Gemini       └─ (assets)   └─ wright│
│  └─ Grok                                │
│                                          │
│  Dados (Fase 2)  Cache        Queue     │
│  ├─ Athena       ├─ Redis     ├─ Celery│
│  └─ Bedrock      └─ (7 dias)  └─ Worker│
└─────────────────────────────────────────┘
```

---

## 🤖 APIS DE INTELIGÊNCIA ARTIFICIAL

### 1. OpenAI API

**Modelos Utilizados:**
- **GPT-4**: Geração de textos complexos
- **DALL-E 3**: Geração de imagens

#### Configuração

```python
# settings.py
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_ORG_ID = os.getenv('OPENAI_ORG_ID')  # Opcional

# Timeouts
OPENAI_TIMEOUT = 60  # segundos
OPENAI_MAX_RETRIES = 3
```

#### GPT-4 - Geração de Texto

**Casos de Uso:**
- Geração de pautas
- Geração de legendas para posts
- Análise de concorrentes
- Análise de trends
- Resumo de pesquisas web

**Parâmetros Padrão:**
```python
{
    "model": "gpt-4-turbo-preview",
    "temperature": 0.7,
    "max_tokens": 2000,
    "top_p": 1,
    "frequency_penalty": 0,
    "presence_penalty": 0
}
```

**Custos (estimados):**
- Input: $0.01 / 1K tokens
- Output: $0.03 / 1K tokens

**Exemplo de Chamada:**
```python
import openai

def gerar_pautas(tema, contexto_femme):
    prompt = f"""
    Contexto da marca:
    {contexto_femme}
    
    Gere 10 pautas sobre: {tema}
    """
    
    response = openai.ChatCompletion.create(
        model="gpt-4-turbo-preview",
        messages=[
            {"role": "system", "content": "Você é um especialista em marketing de saúde."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=2000
    )
    
    return response.choices[0].message.content
```

#### DALL-E 3 - Geração de Imagens

**Casos de Uso:**
- Geração de imagens para posts sociais
- Ilustrações para blogs (Fase 2)

**Parâmetros Padrão:**
```python
{
    "model": "dall-e-3",
    "size": "1024x1024",  # ou "1792x1024", "1024x1792"
    "quality": "hd",       # ou "standard"
    "style": "vivid"       # ou "natural"
}
```

**Custos:**
- Standard (1024x1024): $0.040 / imagem
- HD (1024x1024): $0.080 / imagem

**Exemplo de Chamada:**
```python
def gerar_imagem_post(tema, cores_femme, estilo):
    prompt = f"""
    Crie uma imagem para post de Instagram sobre {tema}.
    Estilo: {estilo}
    Paleta de cores: {', '.join(cores_femme)}
    Mood: profissional e acolhedor
    """
    
    response = openai.Image.create(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        quality="hd",
        n=1
    )
    
    return response.data[0].url
```

---

### 2. Google Gemini API

**Modelos Utilizados:**
- **Gemini Pro**: Textos (alternativa ao GPT-4)
- **Gemini Pro Vision**: Imagens (alternativa ao DALL-E)

#### Configuração

```python
# settings.py
GOOGLE_AI_API_KEY = os.getenv('GOOGLE_AI_API_KEY')

# Timeout
GEMINI_TIMEOUT = 60
```

#### Gemini Pro - Geração de Texto

**Vantagens:**
- Custo menor que GPT-4
- Boa performance em português
- Context window maior (32K tokens)

**Parâmetros Padrão:**
```python
{
    "model": "gemini-pro",
    "temperature": 0.7,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 2048
}
```

**Custos:**
- Input: $0.00025 / 1K tokens
- Output: $0.0005 / 1K tokens

**Exemplo de Chamada:**
```python
import google.generativeai as genai

genai.configure(api_key=GOOGLE_AI_API_KEY)

def gerar_pautas_gemini(tema, contexto_femme):
    model = genai.GenerativeModel('gemini-pro')
    
    prompt = f"""
    Contexto da marca:
    {contexto_femme}
    
    Gere 10 pautas sobre: {tema}
    """
    
    response = model.generate_content(prompt)
    return response.text
```

#### Gemini Pro Vision - Imagens

**Em avaliação** - Ainda não totalmente integrado na Fase 1.

---

### 3. Grok API (X.AI)

**Modelo:** Grok-1

**Casos de Uso:**
- Análise rápida de trends
- Interpretação de dados do Twitter/X
- Análise de sentimento

#### Configuração

```python
# settings.py
GROK_API_KEY = os.getenv('GROK_API_KEY')
GROK_API_URL = "https://api.x.ai/v1/chat/completions"
```

**Custos:** (A definir conforme plano contratado)

**Exemplo de Chamada:**
```python
import requests

def analisar_trend_grok(trend_data):
    headers = {
        "Authorization": f"Bearer {GROK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "grok-1",
        "messages": [
            {
                "role": "user",
                "content": f"Analise este trend: {trend_data}"
            }
        ]
    }
    
    response = requests.post(
        GROK_API_URL,
        headers=headers,
        json=payload,
        timeout=30
    )
    
    return response.json()
```

---

### 4. AWS Bedrock (Fase 2)

**Modelo:** Claude 2 / Titan

**Casos de Uso:**
- Insights avançados de dados (Athena)
- Análise de grandes volumes de texto
- Geração de relatórios complexos

#### Configuração

```python
import boto3

bedrock = boto3.client(
    'bedrock-runtime',
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name='us-east-1'
)
```

**Custos:**
- Claude 2: $0.008 / 1K input tokens, $0.024 / 1K output tokens
- Titan: $0.0008 / 1K input tokens, $0.0016 / 1K output tokens

---

## 💾 ARMAZENAMENTO (AWS S3)

### Estrutura de Buckets

```
iamkt-assets/
├── fonts/              # Fontes customizadas
│   ├── font1.otf
│   └── font2.ttf
│
├── logos/              # Logotipos
│   └── femme-logo.svg
│
├── references/         # Imagens de referência
│   ├── ref001.jpg
│   ├── ref002.png
│   └── ...
│
└── generated/          # Conteúdos gerados
    ├── posts/
    │   ├── 2026/01/
    │   │   ├── post_001.png
    │   │   └── post_002.png
    │   └── ...
    └── docs/
        └── ...
```

### Configuração

```python
# settings.py
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = 'iamkt-assets'
AWS_S3_REGION_NAME = 'us-east-1'

# Segurança
AWS_S3_FILE_OVERWRITE = False
AWS_DEFAULT_ACL = 'private'
AWS_S3_ENCRYPTION = True

# URLs com assinatura temporária
AWS_QUERYSTRING_AUTH = True
AWS_QUERYSTRING_EXPIRE = 3600  # 1 hora
```

### Upload de Arquivo

```python
import boto3
from botocore.exceptions import ClientError

s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_S3_REGION_NAME
)

def upload_to_s3(file_path, s3_key, content_type='image/png'):
    """
    Upload arquivo para S3
    """
    try:
        s3_client.upload_file(
            file_path,
            AWS_STORAGE_BUCKET_NAME,
            s3_key,
            ExtraArgs={
                'ContentType': content_type,
                'ServerSideEncryption': 'AES256'
            }
        )
        
        # Gera URL assinada
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': AWS_STORAGE_BUCKET_NAME,
                'Key': s3_key
            },
            ExpiresIn=3600
        )
        
        return url
        
    except ClientError as e:
        logger.error(f"Erro ao fazer upload: {e}")
        return None
```

### Política de Bucket (Privado)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyPublicAccess",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::iamkt-assets/*",
      "Condition": {
        "StringNotEquals": {
          "aws:PrincipalAccount": "YOUR_AWS_ACCOUNT_ID"
        }
      }
    }
  ]
}
```

---

## 🕷️ WEB SCRAPING

### Stack de Ferramentas

#### 1. Playwright (Sites Dinâmicos)

**Uso:** Sites com JavaScript, SPAs, conteúdo carregado dinamicamente.

**Instalação:**
```bash
pip install playwright --break-system-packages
playwright install chromium
```

**Exemplo:**
```python
from playwright.async_api import async_playwright

async def scrape_concorrente(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await page.goto(url, wait_until='networkidle')
        
        # Extrai conteúdo
        titulo = await page.title()
        descricao = await page.locator('meta[name="description"]').get_attribute('content')
        texto_principal = await page.locator('main').inner_text()
        
        await browser.close()
        
        return {
            'titulo': titulo,
            'descricao': descricao,
            'conteudo': texto_principal
        }
```

#### 2. BeautifulSoup (HTML Estático)

**Uso:** Sites simples, parsing de HTML já carregado.

**Exemplo:**
```python
import requests
from bs4 import BeautifulSoup

def scrape_html_simples(url):
    response = requests.get(url, timeout=10)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Extrai elementos
    titulo = soup.find('h1').text
    paragrafos = [p.text for p in soup.find_all('p')]
    
    return {
        'titulo': titulo,
        'paragrafos': paragrafos
    }
```

#### 3. Requests (APIs e Feeds)

**Uso:** RSS feeds, APIs REST simples.

**Exemplo:**
```python
import requests
import feedparser

def scrape_rss_feed(url):
    feed = feedparser.parse(url)
    
    artigos = []
    for entry in feed.entries[:10]:
        artigos.append({
            'titulo': entry.title,
            'link': entry.link,
            'resumo': entry.summary,
            'data': entry.published
        })
    
    return artigos
```

### Boas Práticas

1. **Respeitar robots.txt**
```python
from urllib.robotparser import RobotFileParser

def pode_scrape(url):
    rp = RobotFileParser()
    rp.set_url(f"{url}/robots.txt")
    rp.read()
    return rp.can_fetch("*", url)
```

2. **Rate Limiting**
```python
import time

def scrape_com_delay(urls, delay=2):
    resultados = []
    for url in urls:
        resultado = scrape(url)
        resultados.append(resultado)
        time.sleep(delay)  # Espera entre requisições
    return resultados
```

3. **User-Agent**
```python
headers = {
    'User-Agent': 'IAMKT Bot/1.0 (contato@femme.com.br)'
}
requests.get(url, headers=headers)
```

---

## 🗄️ CACHE (Redis)

### Estratégia de Cache para IA

**Objetivo:** Reduzir custos e tempo evitando chamadas duplicadas às APIs de IA.

#### Implementação

```python
import hashlib
import json
import redis

redis_client = redis.Redis(
    host='iamkt_redis',
    port=6379,
    db=0,
    decode_responses=True
)

def gerar_cache_key(prompt, modelo, temperatura):
    """
    Gera hash único para o prompt + parâmetros
    """
    data = f"{prompt}|{modelo}|{temperatura}"
    return f"ia_cache:{hashlib.sha256(data.encode()).hexdigest()}"

def buscar_cache(prompt, modelo, temperatura):
    """
    Busca resposta em cache
    """
    key = gerar_cache_key(prompt, modelo, temperatura)
    cached = redis_client.get(key)
    
    if cached:
        return json.loads(cached)
    return None

def salvar_cache(prompt, modelo, temperatura, resposta, ttl=604800):
    """
    Salva resposta em cache (TTL padrão: 7 dias)
    """
    key = gerar_cache_key(prompt, modelo, temperatura)
    redis_client.setex(
        key,
        ttl,
        json.dumps(resposta)
    )
```

#### Uso no Fluxo

```python
def gerar_conteudo_ia(prompt, modelo='gpt-4', temperatura=0.7):
    # 1. Tenta buscar em cache
    cached = buscar_cache(prompt, modelo, temperatura)
    if cached:
        logger.info("Cache hit!")
        return cached
    
    # 2. Cache miss - chama API
    logger.info("Cache miss - chamando API")
    resposta = openai.ChatCompletion.create(...)
    
    # 3. Salva em cache
    salvar_cache(prompt, modelo, temperatura, resposta)
    
    return resposta
```

### Métricas de Cache

```python
def calcular_taxa_cache():
    """
    Calcula hit rate do cache
    """
    hits = redis_client.get('cache:hits') or 0
    misses = redis_client.get('cache:misses') or 0
    
    total = int(hits) + int(misses)
    if total == 0:
        return 0
    
    return (int(hits) / total) * 100
```

---

## ⚙️ CELERY (PROCESSAMENTO ASSÍNCRONO)

### Worker Configuration

```python
# celery.py
from celery import Celery

app = Celery('iamkt')
app.config_from_object('django.conf:settings', namespace='CELERY')

# Configurações
app.conf.update(
    broker_url='redis://iamkt_redis:6379/0',
    result_backend='redis://iamkt_redis:6379/0',
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='America/Fortaleza',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutos
    task_soft_time_limit=240,  # 4 minutos
)

app.autodiscover_tasks()
```

### Tasks Principais

#### 1. Geração de Conteúdo
```python
@app.task(bind=True, max_retries=3)
def task_gerar_conteudo(self, content_id, ferramenta, inputs):
    try:
        # Busca Base FEMME
        base = KnowledgeBase.objects.first()
        
        # Monta contexto
        contexto = montar_contexto(base, inputs)
        
        # Chama IA (com cache)
        resultado = gerar_ia(contexto, inputs['modelo'])
        
        # Salva resultado
        content = GeneratedContent.objects.get(id=content_id)
        content.conteudo_texto = resultado['texto']
        content.save()
        
        return {'status': 'sucesso', 'content_id': content_id}
        
    except Exception as exc:
        # Retry com backoff exponencial
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
```

#### 2. Scraping de Concorrente
```python
@app.task
def task_scrape_competitor(competitor_id):
    competitor = Competitor.objects.get(id=competitor_id)
    
    # Scraping
    dados = scrape_concorrente(competitor.url)
    
    # Análise IA
    analise = ia_analisar_concorrente(dados)
    
    # Salva
    competitor.analise_posicionamento = analise['posicionamento']
    competitor.analise_diferenciais = analise['diferenciais']
    competitor.analise_tom_voz = analise['tom_voz']
    competitor.ultimo_scraping = timezone.now()
    competitor.save()
```

#### 3. Monitoramento de Trends (Periódica)
```python
from celery.schedules import crontab

@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    # Diariamente às 6h
    sender.add_periodic_task(
        crontab(hour=6, minute=0),
        task_monitor_trends.s(),
        name='monitor-trends-daily'
    )
    
    # Scraping concorrentes - semanal domingo 0h
    sender.add_periodic_task(
        crontab(hour=0, minute=0, day_of_week=0),
        task_scrape_all_competitors.s(),
        name='scrape-competitors-weekly'
    )

@app.task
def task_monitor_trends():
    # Busca em todas as fontes
    trends = []
    
    # Fontes pré-configuradas
    trends.extend(scrape_google_trends())
    trends.extend(scrape_reddit())
    trends.extend(scrape_twitter())
    
    # Fontes customizadas
    base = KnowledgeBase.objects.first()
    for canal in base.canais_monitoramento_trends:
        trends.extend(scrape_canal_custom(canal))
    
    # Analisa relevância com IA
    for trend in trends:
        relevancia = ia_analisar_relevancia(trend, base)
        
        if relevancia['score'] >= 70:
            TrendMonitor.objects.create(
                titulo=trend['titulo'],
                fonte=trend['fonte'],
                relevancia_score=relevancia['score'],
                analise_ia=relevancia['analise']
            )
```

### Monitoramento

```python
# Flower (Web UI para Celery)
# Acesso: http://iamkt-femmeintegra.aisuites.com.br:5555

# Comandos
# Ver workers ativos
celery -A iamkt inspect active

# Ver tasks agendadas
celery -A iamkt inspect scheduled

# Ver stats
celery -A iamkt inspect stats
```

---

## 📊 AWS ATHENA (FASE 2)

### Configuração

```python
import boto3

athena_client = boto3.client(
    'athena',
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name='us-east-1'
)

def executar_query_athena(sql, database='femme_analytics'):
    response = athena_client.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={'Database': database},
        ResultConfiguration={
            'OutputLocation': 's3://iamkt-athena-results/'
        }
    )
    
    query_execution_id = response['QueryExecutionId']
    
    # Aguarda conclusão
    while True:
        status = athena_client.get_query_execution(
            QueryExecutionId=query_execution_id
        )
        
        state = status['QueryExecution']['Status']['State']
        
        if state in ['SUCCEEDED', 'FAILED', 'CANCELLED']:
            break
        
        time.sleep(2)
    
    if state == 'SUCCEEDED':
        results = athena_client.get_query_results(
            QueryExecutionId=query_execution_id
        )
        return results
    else:
        raise Exception(f"Query falhou: {state}")
```

---

**Próximo documento:** [08_IAMKT_Workflow_Aprovacoes.md](08_IAMKT_Workflow_Aprovacoes.md)
