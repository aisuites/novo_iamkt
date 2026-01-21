from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, Area, AuditLog, SystemConfig,
    Organization, QuotaUsageDaily, QuotaAdjustment, QuotaAlert
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'profile', 'is_active']
    list_filter = ['profile', 'is_active', 'is_staff', 'areas']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    filter_horizontal = ['areas', 'groups', 'user_permissions']
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Informações Adicionais', {
            'fields': ('profile', 'areas', 'phone')
        }),
    )


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'is_active', 'created_at']
    list_filter = ['is_active', 'parent']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']


# UsageLimit foi DEPRECADO - usar Organization e QuotaUsageDaily
# Mantido apenas para migração de dados históricos


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'model_name', 'object_repr', 'created_at']
    list_filter = ['action', 'model_name', 'created_at']
    search_fields = ['user__username', 'object_repr']
    readonly_fields = ['user', 'action', 'model_name', 'object_id', 'object_repr', 
                      'changes', 'ip_address', 'user_agent', 'created_at']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    list_display = ['key', 'value', 'is_active', 'updated_at']
    list_filter = ['is_active']
    search_fields = ['key', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'slug', 'plan_type', 'is_active',
        'quota_pautas_dia', 'quota_posts_dia', 'quota_posts_mes'
    ]
    list_filter = ['plan_type', 'is_active', 'created_at']
    search_fields = ['name', 'slug']
    readonly_fields = ['created_at', 'updated_at', 'approved_at']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('name', 'slug', 'is_active', 'approved_at')
        }),
        ('Plano e Quotas', {
            'fields': (
                'plan_type',
                'quota_pautas_dia',
                'quota_posts_dia',
                'quota_posts_mes',
                'quota_cost_mes_usd'
            )
        }),
        ('Alertas', {
            'fields': (
                'alert_enabled',
                'alert_email',
                'alert_threshold_80',
                'alert_threshold_100'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'approved_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(QuotaUsageDaily)
class QuotaUsageDailyAdmin(admin.ModelAdmin):
    list_display = [
        'organization', 'date', 'pautas_count', 'posts_count',
        'cost_usd', 'get_total_items'
    ]
    list_filter = ['date', 'organization']
    search_fields = ['organization__name']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'date'
    
    def get_total_items(self, obj):
        return obj.pautas_count + obj.posts_count
    get_total_items.short_description = 'Total Itens'


@admin.register(QuotaAdjustment)
class QuotaAdjustmentAdmin(admin.ModelAdmin):
    list_display = [
        'organization', 'adjustment_type', 'quota_type',
        'amount', 'reason', 'created_by', 'created_at'
    ]
    list_filter = ['adjustment_type', 'quota_type', 'created_at']
    search_fields = ['organization__name', 'reason']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Ajuste', {
            'fields': ('organization', 'adjustment_type', 'quota_type', 'amount')
        }),
        ('Detalhes', {
            'fields': ('reason', 'reference_pauta', 'reference_post', 'created_by')
        }),
        ('Timestamp', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(QuotaAlert)
class QuotaAlertAdmin(admin.ModelAdmin):
    list_display = [
        'organization', 'alert_type', 'threshold_percentage',
        'current_usage', 'quota_limit', 'sent_at'
    ]
    list_filter = ['alert_type', 'threshold_percentage', 'sent_at']
    search_fields = ['organization__name']
    readonly_fields = ['sent_at', 'email_sent_to']
    date_hierarchy = 'sent_at'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
