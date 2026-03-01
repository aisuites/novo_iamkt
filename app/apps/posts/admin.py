from django.contrib import admin
from .models import Post, PostImage, PostChangeRequest, PostFormat


class PostImageInline(admin.TabularInline):
    model = PostImage
    extra = 1
    fields = ('image_file', 's3_url', 'order')
    readonly_fields = ('s3_url',)
    verbose_name = 'Imagem do Post'
    verbose_name_plural = 'Imagens do Post'


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    inlines = [PostImageInline]
    list_display = [
        'id',
        'title',
        'social_network',
        'content_type',
        'status',
        'user',
        'organization',
        'created_at',
    ]
    list_filter = [
        'status',
        'social_network',
        'content_type',
        'is_carousel',
        'created_at',
    ]
    search_fields = [
        'title',
        'subtitle',
        'caption',
        'requested_theme',
        'user__email',
    ]
    readonly_fields = [
        'created_at',
        'updated_at',
        'organization',
        'image_s3_url',
        'image_s3_key',
        'has_image',
    ]
    fieldsets = (
        ('Informações Básicas', {
            'fields': (
                'user',
                'area',
                'pauta',
                'organization',
            )
        }),
        ('Conteúdo', {
            'fields': (
                'requested_theme',
                'title',
                'subtitle',
                'caption',
                'hashtags',
                'cta',
                'cta_requested',
            )
        }),
        ('Configurações', {
            'fields': (
                'social_network',
                'content_type',
                'formats',
                'is_carousel',
                'image_count',
                'slides_metadata',
            )
        }),
        ('IA', {
            'fields': (
                'ia_provider',
                'ia_model_text',
                'ia_model_image',
                'thread_id',
            )
        }),
        ('Imagem', {
            'fields': (
                'post_format',
                'has_image',
                'image_s3_url',
                'image_s3_key',
                'image_prompt',
                'image_width',
                'image_height',
                'reference_images',
            ),
            'description': 'Campos de referência da imagem principal. Para fazer upload de imagens, use a seção "POST IMAGES" abaixo.'
        }),
        ('Status e Revisões', {
            'fields': (
                'status',
                'revisions_remaining',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            )
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(organization=request.user.organization)


@admin.register(PostChangeRequest)
class PostChangeRequestAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'post',
        'change_type',
        'is_initial',
        'requester_name',
        'requester_email',
        'created_at',
    ]
    list_filter = [
        'change_type',
        'is_initial',
        'created_at',
    ]
    search_fields = [
        'message',
        'requester_name',
        'requester_email',
        'post__title',
    ]
    readonly_fields = [
        'created_at',
    ]
    fieldsets = (
        ('Solicitação', {
            'fields': (
                'post',
                'change_type',
                'is_initial',
                'message',
            )
        }),
        ('Solicitante', {
            'fields': (
                'requester_name',
                'requester_email',
            )
        }),
        ('Timestamp', {
            'fields': (
                'created_at',
            )
        }),
    )


@admin.register(PostFormat)
class PostFormatAdmin(admin.ModelAdmin):
    list_display = ['social_network', 'name', 'width', 'height', 'aspect_ratio', 'is_active', 'order']
    list_filter = ['social_network', 'is_active']
    list_editable = ['order', 'is_active']
    search_fields = ['name', 'social_network']
    ordering = ['social_network', 'order', 'name']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('social_network', 'name', 'is_active', 'order')
        }),
        ('Dimensões', {
            'fields': ('width', 'height', 'aspect_ratio')
        }),
    )
