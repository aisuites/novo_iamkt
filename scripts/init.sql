-- =============================================================================
-- IAMKT - SCRIPT DE INICIALIZAÇÃO DO POSTGRESQL
-- =============================================================================
-- Este script é executado automaticamente quando o PostgreSQL é criado
-- Data: 20/01/2026

-- =============================================================================
-- EXTENSÕES ÚTEIS PARA IAMKT
-- =============================================================================

-- UUID para IDs únicos
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Texto completo (Full Text Search) para busca em documentos
CREATE EXTENSION IF NOT EXISTS "unaccent";

-- Trigram para busca aproximada
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- =============================================================================
-- FUNÇÕES ÚTEIS PARA IAMKT
-- =============================================================================

-- Função para slugify (converter texto em slug)
CREATE OR REPLACE FUNCTION slugify(value TEXT)
RETURNS TEXT AS $$
BEGIN
    RETURN trim(both '-' from regexp_replace(lower(unaccent(value)), '[^a-z0-9\\-_]+', '-', 'gi'));
END;
$$ LANGUAGE plpgsql IMMUTABLE STRICT;

-- Função para normalizar CPF/CNPJ (remove formatação)
CREATE OR REPLACE FUNCTION normalize_document(doc TEXT)
RETURNS TEXT AS $$
BEGIN
    RETURN regexp_replace(doc, '[^0-9]', '', 'g');
END;
$$ LANGUAGE plpgsql IMMUTABLE STRICT;

-- =============================================================================
-- CONFIGURAÇÕES DE DESENVOLVIMENTO
-- =============================================================================

-- Timezone para Fortaleza/Ceará
SET timezone = 'America/Fortaleza';

-- Configurações de memória para desenvolvimento (256MB container)
ALTER SYSTEM SET shared_buffers = '64MB';
ALTER SYSTEM SET work_mem = '2MB';
ALTER SYSTEM SET maintenance_work_mem = '32MB';
ALTER SYSTEM SET effective_cache_size = '192MB';

-- Reload das configurações
SELECT pg_reload_conf();

-- =============================================================================
-- LOG DE INICIALIZAÇÃO
-- =============================================================================

DO $$
BEGIN
    RAISE NOTICE 'IAMKT PostgreSQL inicializado com sucesso!';
    RAISE NOTICE 'Database: %', current_database();
    RAISE NOTICE 'Versão: %', version();
    RAISE NOTICE 'Timezone: %', current_setting('timezone');
    RAISE NOTICE 'Data/Hora: %', now();
END $$;
