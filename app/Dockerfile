# =============================================================================
# NTO - DOCKERFILE
# =============================================================================
# Multi-stage build para otimizar imagem final
# Data: 22/12/2025 | Versão: 2.1

# -----------------------------------------------------------------------------
# STAGE 1: BASE PYTHON
# -----------------------------------------------------------------------------
FROM python:3.11-slim as python-base

# Variáveis de ambiente Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# -----------------------------------------------------------------------------
# STAGE 2: BUILDER (Dependências)
# -----------------------------------------------------------------------------
FROM python-base as builder

# Instalar dependências do sistema para compilação
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Criar ambiente virtual
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copiar e instalar dependências Python
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# -----------------------------------------------------------------------------
# STAGE 3: RUNTIME
# -----------------------------------------------------------------------------
FROM python-base as runtime

# Instalar dependências de runtime
RUN apt-get update && apt-get install -y \
    libpq5 \
    netcat-traditional \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Criar usuário não-root
RUN groupadd -r django && useradd -r -g django django

# Copiar ambiente virtual do builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Configurar diretório de trabalho
WORKDIR /app

# Copiar código da aplicação
COPY . .

# Copiar script de entrada
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Criar diretórios necessários
RUN mkdir -p /app/staticfiles /app/media && \
    chown -R django:django /app

# Expor porta
EXPOSE 8000

# Usuário não-root
USER django

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Comando padrão
ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "sistema.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
