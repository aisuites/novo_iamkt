"""
Testes do PIPELINE SIMPLES (v2) — cobertura mínima do fluxo live-facing.

Mocka chamadas externas (OpenAI/Gemini/S3); foca na lógica que é nossa:
criação/roteamento da view, admin-gating, preenchimento do Post pela task de
texto, presign do logo (regressão) e parsing de JSON do agente.

Rodar: docker exec iamkt_web python manage.py test apps.posts.test_simple_pipeline
"""
import json
from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model

from apps.core.models import Organization
from apps.posts.models import Post, PostFormat

User = get_user_model()


def make_org_user(profile='operacional', slug='org-x', email='u@test.com'):
    org = Organization.objects.create(name=slug, slug=slug, is_active=True)
    user = User.objects.create_user(
        username=email, email=email, password='test123',
        organization=org, profile=profile,
    )
    return org, user


def make_simple_post(org, user, **over):
    data = dict(
        organization=org, user=user, requested_theme='Tema teste',
        social_network='instagram', content_type='post', formats=['feed'],
        cta_requested=True, is_carousel=False, image_count=1, reference_images=[],
        status='pending', caption='', hashtags=[], ia_provider='openai',
        ia_model_text='gpt-4o-mini', pipeline_used='simple',
        copy_payload={}, designer_payload={}, local_pipeline_context={},
    )
    data.update(over)
    return Post.objects.create(**data)


class FormatosApiTests(TestCase):
    """Regressão do bug que apareceu em prod: formatos não apareciam no modal."""

    def setUp(self):
        self.org, self.user = make_org_user()
        self.client.force_login(self.user)

    def test_instagram_retorna_formatos(self):
        # A migration 0012 popula PostFormat no banco de teste.
        resp = self.client.get(reverse('posts:api_formatos'), {'rede_social': 'instagram'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertGreaterEqual(len(data['formatos']), 1, 'PostFormat deve estar populado (migration 0012)')

    def test_rede_obrigatoria(self):
        resp = self.client.get(reverse('posts:api_formatos'))
        self.assertEqual(resp.status_code, 400)


class GerarSimplesViewTests(TestCase):
    def setUp(self):
        self.org, self.user = make_org_user()
        self.url = reverse('posts:gerar_simples')

    def _payload(self, **over):
        p = dict(rede_social='instagram', tema='Tema teste', formato='feed',
                 cta_requested=True, is_carousel=False, image_count=1)
        p.update(over)
        return json.dumps(p)

    def test_exige_login(self):
        resp = self.client.post(self.url, self._payload(), content_type='application/json')
        self.assertIn(resp.status_code, (302, 403))

    @patch('apps.posts.views_gerar_simples.generate_post_simple_task')
    def test_cria_post_simple_e_enfileira(self, mock_task):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, self._payload(), content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body['success'])
        self.assertEqual(body['pipeline'], 'simple')
        post = Post.objects.get(id=body['id'])
        self.assertEqual(post.pipeline_used, 'simple')
        self.assertEqual(post.status, 'generating')
        mock_task.delay.assert_called_once_with(post.id)

    @patch('apps.posts.views_gerar_simples.generate_post_simple_task')
    def test_rede_invalida_400(self, _m):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, self._payload(rede_social='orkut'),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    @patch('apps.posts.views_gerar_simples.generate_post_simple_task')
    def test_tema_obrigatorio_400(self, _m):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, self._payload(tema=''),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    @override_settings(ENABLE_SIMPLE_PIPELINE=False)
    @patch('apps.posts.views_gerar_simples.generate_post_simple_task')
    def test_desabilitado_403(self, _m):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, self._payload(), content_type='application/json')
        self.assertEqual(resp.status_code, 403)


class AdminGatingTests(TestCase):
    """simple-debug é admin-only (visível em prod só para admin)."""

    def setUp(self):
        self.org, self.common = make_org_user(profile='operacional', slug='org-c', email='c@test.com')
        # admin na MESMA org
        self.admin = User.objects.create_user(
            username='adm@test.com', email='adm@test.com', password='x',
            organization=self.org, profile='admin',
        )
        self.post = make_simple_post(self.org, self.common,
                                     local_pipeline_context={'simple_image': {'bg_prompt': 'x'}})
        self.url = reverse('posts:simple_debug', args=[self.post.id])

    def test_nao_admin_403(self):
        self.client.force_login(self.common)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 403)

    def test_admin_200(self):
        self.client.force_login(self.admin)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get('pipeline'), 'simple')


class SimpleTextTaskTests(TestCase):
    """generate_post_simple_task preenche o Post a partir do agente (mockado)."""

    def setUp(self):
        self.org, self.user = make_org_user(slug='org-t', email='t@test.com')
        self.post = make_simple_post(self.org, self.user, status='generating')

    @patch('apps.posts.tasks._reference_images_from_post', return_value=[])
    @patch('apps.posts.tasks._logos_from_org', return_value=[])
    @patch('apps.posts.tasks._build_kb_summary', return_value='KB resumo')
    @patch('apps.posts.services.simple_post_agent.generate_simple_post')
    def test_preenche_campos_e_normaliza_hashtags(self, mock_gen, *_mocks):
        mock_gen.return_value = {
            'structured': {
                'title': 'Título', 'subtitle': 'Sub', 'image_prompt': 'cena',
                'visual_brief': 'brief', 'caption': 'legenda', 'cta_text': 'Clique',
                'hashtags': ['SemHash', '#JaTem'],
            },
            'usage': {'input_tokens': 10, 'output_tokens': 5, 'cost_usd': 0.001},
            'model': 'gpt-4o-mini',
        }
        from apps.posts.tasks import generate_post_simple_task
        generate_post_simple_task.run(self.post.id)
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, 'pending')
        self.assertEqual(self.post.title, 'Título')
        self.assertEqual(self.post.cta, 'Clique')
        self.assertEqual(self.post.ia_provider, 'openai')
        # hashtags normalizadas com '#'
        self.assertEqual(self.post.hashtags, ['#SemHash', '#JaTem'])
        self.assertIn('_simple_agent', self.post.copy_payload)


class LogosPresignTests(TestCase):
    """Regressão: _logos_from_org deve presignar (corrige 403 no download)."""

    def setUp(self):
        from apps.knowledge.models import KnowledgeBase, Logo
        self.org, self.user = make_org_user(slug='org-l', email='l@test.com')
        self.kb = KnowledgeBase.objects.create(organization=self.org)
        Logo.objects.create(knowledge_base=self.kb, s3_key='org/logos/sec.png',
                            s3_url='https://raw/sec.png', is_primary=False)
        Logo.objects.create(knowledge_base=self.kb, s3_key='org/logos/prim.png',
                            s3_url='https://raw/prim.png', is_primary=True)

    @patch('apps.core.services.s3_service.S3Service.generate_presigned_download_url')
    def test_presigna_e_primario_primeiro(self, mock_presign):
        mock_presign.side_effect = lambda key, expires_in=3600: f'https://signed/{key}?sig=1'
        from apps.posts.tasks import _logos_from_org
        urls = _logos_from_org(self.org, post=None)
        self.assertEqual(len(urls), 2)
        # primario (prim.png) deve vir primeiro (order_by -is_primary)
        self.assertIn('prim.png', urls[0])
        # presignado (nao a s3_url crua)
        self.assertTrue(all('sig=1' in u for u in urls))


class ParseJsonTests(TestCase):
    def test_parse_plain_e_cercado(self):
        from apps.posts.services.simple_post_agent import _parse_json
        self.assertEqual(_parse_json('{"a": 1}'), {'a': 1})
        self.assertEqual(_parse_json('```json\n{"a": 2}\n```'), {'a': 2})
        self.assertEqual(_parse_json('prosa {"a": 3} fim'), {'a': 3})
        self.assertEqual(_parse_json('sem json'), {})


def _anthropic_status_error(status, message='erro', cls=None):
    """Constroi um anthropic.APIStatusError (ou subclasse) com um status HTTP
    arbitrario, sem tocar a rede."""
    import httpx
    import anthropic
    req = httpx.Request('POST', 'https://api.anthropic.com/v1/messages')
    resp = httpx.Response(status, request=req)
    cls = cls or anthropic.APIStatusError
    return cls(message, response=resp, body=None)


class ClaudeOverloadRetryTests(TestCase):
    """Cobre a correcao do 529: orquestrador sobrecarregado -> backoff/retry da
    task; 400 permanente -> falha rapida; cache de texto entre retries; e o
    estado de falha (sem travar em 'generating')."""

    def setUp(self):
        self.org, self.user = make_org_user(slug='org-529', email='r@test.com')
        # Post com os textos do OpenAI JA persistidos (simula 1a tentativa que
        # gerou o texto) -> a task pula o OpenAI e vai direto ao orquestrador.
        self.post = make_simple_post(
            self.org, self.user, status='generating',
            ia_model_text='gpt-4o-mini',
            copy_payload={'_simple_agent': {'title': 'T', 'subtitle': 'S',
                                            'caption': 'c', 'hashtags': ['#x'],
                                            'cta_text': 'CTA'}},
            local_pipeline_context={'simple_text_saved': True},
        )

    @patch('apps.posts.services.simple_post_agent.generate_simple_post')
    @patch('apps.posts.tasks_simple._simple_orchestrate_into_image_prompt')
    def test_529_transitorio_faz_retry_sem_falhar(self, mock_orch, mock_openai):
        from celery.exceptions import Retry
        from apps.posts.tasks_simple import generate_post_simple_task
        mock_orch.side_effect = _anthropic_status_error(529, 'overloaded')

        with patch.object(generate_post_simple_task, 'retry', side_effect=Retry()) as m_retry:
            with self.assertRaises(Retry):
                generate_post_simple_task.run(self.post.id)
        m_retry.assert_called_once()
        mock_openai.assert_not_called()  # cache: nao re-chamou o OpenAI
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, 'generating')  # NAO falhou (transitorio)

    @patch('apps.posts.services.simple_post_agent.generate_simple_post')
    @patch('apps.posts.tasks_simple._simple_orchestrate_into_image_prompt')
    def test_400_permanente_falha_rapido(self, mock_orch, mock_openai):
        import anthropic
        from apps.posts.tasks_simple import generate_post_simple_task, GENERATION_FAILED_MESSAGE
        mock_orch.side_effect = _anthropic_status_error(
            400, 'credit balance too low', cls=anthropic.BadRequestError)

        with patch.object(generate_post_simple_task, 'retry') as m_retry:
            res = generate_post_simple_task.run(self.post.id)
        m_retry.assert_not_called()  # permanente: NAO queima retries
        self.assertFalse(res['success'])
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, 'failed')
        self.assertEqual(self.post.local_pipeline_context.get('last_error'),
                         GENERATION_FAILED_MESSAGE)

    @patch('apps.posts.services.simple_post_agent.generate_simple_post')
    @patch('apps.posts.tasks_simple._simple_orchestrate_into_image_prompt')
    def test_529_retries_esgotados_marca_failed(self, mock_orch, mock_openai):
        from apps.posts.tasks_simple import generate_post_simple_task, GENERATION_FAILED_MESSAGE
        mock_orch.side_effect = _anthropic_status_error(529, 'overloaded')

        # Simula a ULTIMA tentativa (retries == max_retries).
        generate_post_simple_task.push_request(retries=generate_post_simple_task.max_retries)
        try:
            with patch.object(generate_post_simple_task, 'retry') as m_retry:
                res = generate_post_simple_task.run(self.post.id)
        finally:
            generate_post_simple_task.pop_request()
        m_retry.assert_not_called()  # esgotado: nao re-tenta, marca falha
        self.assertFalse(res['success'])
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, 'failed')
        self.assertEqual(self.post.local_pipeline_context.get('last_error'),
                         GENERATION_FAILED_MESSAGE)

    @patch('apps.posts.services.simple_post_agent.generate_simple_post')
    @patch('apps.posts.tasks_simple._simple_orchestrate_into_image_prompt')
    def test_cache_texto_nao_rechama_openai(self, mock_orch, mock_openai):
        from apps.posts.tasks_simple import generate_post_simple_task

        def _orch_ok(post):
            post.image_prompt = 'cena gerada'
            return True
        mock_orch.side_effect = _orch_ok

        res = generate_post_simple_task.run(self.post.id)
        self.assertTrue(res['success'])
        mock_openai.assert_not_called()  # texto reaproveitado do cache
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, 'pending')
        self.assertEqual(self.post.image_prompt, 'cena gerada')


class RetryVsRegenerateTests(TestCase):
    """Contrato dos dois botoes:
    - 'Tentar de novo' (retry_post): REAPROVEITA o texto -> preserva
      simple_text_saved, limpa so o last_error. A task pula o OpenAI (gasta menos).
    - 'Gerar Novamente' (regenerate_post): descarta tudo -> limpa o cache de
      texto, forcando a task a re-gerar no OpenAI."""

    def setUp(self):
        self.org, self.user = make_org_user(slug='org-retry', email='rt@test.com')
        self.post = make_simple_post(
            self.org, self.user, status='failed',
            copy_payload={'_simple_agent': {'title': 'T'}},
            local_pipeline_context={'simple_text_saved': True,
                                    'last_error': 'sobrecarga'},
        )
        self.client.force_login(self.user)

    @patch('apps.posts.tasks_simple.generate_post_simple_task')
    def test_retry_preserva_cache_de_texto(self, mock_task):
        resp = self.client.post(reverse('posts:retry', args=[self.post.id]),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, 'generating')
        ctx = self.post.local_pipeline_context or {}
        self.assertTrue(ctx.get('simple_text_saved'))   # cache PRESERVADO (reaproveita)
        self.assertIsNone(ctx.get('last_error'))        # erro limpo
        mock_task.delay.assert_called_once_with(self.post.id)

    @patch('apps.posts.tasks_simple.generate_post_simple_task')
    def test_regenerate_limpa_cache_de_texto(self, mock_task):
        resp = self.client.post(reverse('posts:regenerate', args=[self.post.id]),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.post.refresh_from_db()
        ctx = self.post.local_pipeline_context or {}
        self.assertIsNone(ctx.get('simple_text_saved'))  # cache LIMPO (gera do zero)
        self.assertIsNone(ctx.get('last_error'))
        mock_task.delay.assert_called_once_with(self.post.id)
