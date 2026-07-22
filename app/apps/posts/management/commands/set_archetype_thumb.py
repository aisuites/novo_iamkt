"""
Define a THUMBNAIL de um PostArchetype (card do modal "Usar template").

Fonte da imagem (uma das duas):
  --from-post <id>  arte FINAL de um post ja gerado (bonita, com foto real)
  (default)         preview deterministico da spec do banco (placeholder cinza)

A imagem vira uma ReferenceImage da KB (title 'thumb-arquetipo-<key>',
idempotente: re-rodar substitui o arquivo da MESMA ReferenceImage) e e ligada
em PostArchetype.thumbnail — o get_org_assets presigna e o modal exibe.

  python manage.py set_archetype_thumb --org thermomix --archetype tmx-A --from-post 303
"""
import io

from django.core.management.base import BaseCommand

from apps.core.models import Organization


class Command(BaseCommand):
    help = 'Gera/atualiza a thumbnail de um PostArchetype (card do modal).'

    def add_arguments(self, parser):
        parser.add_argument('--org', required=True, help='slug da organizacao')
        parser.add_argument('--archetype', required=True, help='key do arquetipo')
        parser.add_argument('--from-post', type=int, default=None,
                            help='usa a arte final deste post (senao: preview da spec)')
        parser.add_argument('--from-ref', type=int, default=None,
                            help='liga uma ReferenceImage EXISTENTE da KB (sem re-upload)')
        parser.add_argument('--width', type=int, default=480,
                            help='largura da thumb (default 480px)')

    def handle(self, *args, **o):
        from PIL import Image
        from apps.knowledge.models import KnowledgeBase, ReferenceImage
        from apps.posts.models import Post, PostArchetype
        from apps.core.services.s3_service import S3Service

        try:
            org = Organization.objects.get(slug=o['org'])
        except Organization.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"org {o['org']!r} nao encontrada"))
            return
        kb = KnowledgeBase.objects.filter(organization=org).first()
        if not kb:
            self.stderr.write(self.style.ERROR('org sem KnowledgeBase'))
            return
        try:
            arch = PostArchetype.objects.get(organization=org, key=o['archetype'])
        except PostArchetype.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"arquetipo {o['archetype']!r} nao existe"))
            return

        # ---- from-ref: liga ReferenceImage existente e encerra ----
        if o['from_ref']:
            try:
                ref = ReferenceImage.objects.get(id=o['from_ref'], knowledge_base=kb)
            except ReferenceImage.DoesNotExist:
                self.stderr.write(self.style.ERROR(
                    f"ReferenceImage {o['from_ref']} nao existe nesta KB"))
                return
            arch.thumbnail = ref
            arch.save(update_fields=['thumbnail'])
            self.stdout.write(self.style.SUCCESS(
                f'OK: thumbnail do {arch.key} -> ReferenceImage {ref.id} (existente)'))
            return

        # ---- imagem-fonte ----
        if o['from_post']:
            import urllib.request
            post = Post.objects.get(id=o['from_post'], organization=org)
            url = S3Service.generate_presigned_download_url(post.image_s3_key,
                                                            expires_in=600)
            with urllib.request.urlopen(url, timeout=60) as r:
                png = r.read()
            source = f'post {post.id}'
        else:
            from apps.posts.services.preview import render_preview
            png = render_preview(org, kb, o['archetype'])
            source = 'preview deterministico'

        img = Image.open(io.BytesIO(png)).convert('RGB')
        w = int(o['width'])
        img = img.resize((w, int(img.height * w / img.width)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, 'JPEG', quality=85)
        data = buf.getvalue()

        # ---- upload S3 + ReferenceImage idempotente por title ----
        title = f'thumb-arquetipo-{arch.key}'
        s3_key = f'org-{org.id}/archetype-thumbs/{arch.key}.jpg'
        client = S3Service._get_s3_client()
        if hasattr(S3Service, '_get_bucket_name'):
            bucket = S3Service._get_bucket_name()
        else:
            from django.conf import settings as dj_settings
            bucket = dj_settings.AWS_BUCKET_NAME
        client.put_object(Bucket=bucket, Key=s3_key, Body=data,
                          ContentType='image/jpeg')
        ref, created = ReferenceImage.objects.get_or_create(
            knowledge_base=kb, title=title,
            defaults={'s3_key': s3_key, 's3_url': '', 'file_size': len(data),
                      'width': img.width, 'height': img.height},
        )
        if not created:
            ref.s3_key = s3_key
            ref.file_size = len(data)
            ref.width, ref.height = img.width, img.height
            ref.save(update_fields=['s3_key', 'file_size', 'width', 'height'])
        arch.thumbnail = ref
        arch.save(update_fields=['thumbnail'])

        self.stdout.write(self.style.SUCCESS(
            f'OK: thumbnail do {arch.key} ({source}, {w}px, {len(data)//1024}KB) '
            f'-> ReferenceImage {ref.id} ({s3_key})'))
