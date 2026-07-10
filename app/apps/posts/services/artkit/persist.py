"""Cauda comum das tasks de arte — origem: tasks_todxs/vb/samsung (blocos gemeos).

persist_rendered_art faz o nucleo identico das 3 caudas:
  upload raw+final -> PostImage (max_order+1) -> designer_payload['_layout_elements']
  -> raw_image_s3_key -> campos de conteudo/imagem -> generated_images append.

NAO salva o post e NAO seta status: o caller ainda atualiza trace/ctx proprios
(que dependem das URLs retornadas) e fecha com status='image_ready' + save() —
mesma ordem de sempre. So atribui os campos cujo kwarg veio != None (cada org
mantem suas fontes/semantica: ex. title ja vem computado com o fallback
`or post.title` feito no caller).
"""


def persist_rendered_art(post, *, raw_png, final_png, elements,
                         title=None, subtitle=None, caption=None, hashtags=None,
                         image_prompt=None, ia_model_image=None,
                         ia_provider=None, ia_model_text=None,
                         set_raw_url=False):
    """Retorna {'raw_key','raw_url','s3_key','s3_url'}."""
    from django.db.models import Max
    from apps.posts.models import PostImage
    from apps.posts.tasks import _upload_image_to_s3

    org_id = post.organization_id
    raw_key, raw_url = _upload_image_to_s3(
        org_id=org_id, post_id=post.id, png_bytes=raw_png, mime_type='image/png')
    s3_key, s3_url = _upload_image_to_s3(
        org_id=org_id, post_id=post.id, png_bytes=final_png, mime_type='image/png')

    max_order = post.images.aggregate(Max('order'))['order__max']
    PostImage.objects.create(
        post=post, s3_key=s3_key, s3_url=s3_url,
        order=(max_order if max_order is not None else -1) + 1,
    )

    dp = post.designer_payload if isinstance(post.designer_payload, dict) else {}
    dp['_layout_elements'] = elements
    post.designer_payload = dp
    post.raw_image_s3_key = raw_key
    if set_raw_url:  # vb historicamente tambem persiste a URL do raw
        post.raw_image_s3_url = raw_url

    if title is not None:
        post.title = title
    if subtitle is not None:
        post.subtitle = subtitle
    if caption is not None:
        post.caption = caption
    if hashtags is not None:
        post.hashtags = hashtags
    if image_prompt is not None:
        post.image_prompt = image_prompt
    if ia_provider is not None:
        post.ia_provider = ia_provider
    if ia_model_text is not None:
        post.ia_model_text = ia_model_text
    if ia_model_image is not None:
        post.ia_model_image = ia_model_image

    post.image_s3_key = s3_key
    post.image_s3_url = s3_url
    post.has_image = True
    existing = post.generated_images if isinstance(post.generated_images, list) else []
    existing.append({'s3_key': s3_key, 'url': s3_url})
    post.generated_images = existing

    return {'raw_key': raw_key, 'raw_url': raw_url,
            's3_key': s3_key, 's3_url': s3_url}
