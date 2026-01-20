from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Area, UsageLimit, AuditLog, SystemConfig


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


@admin.register(UsageLimit)
class UsageLimitAdmin(admin.ModelAdmin):
    list_display = [
        'area', 'month', 'current_generations', 'max_generations',
        'current_cost_usd', 'max_cost_usd', 'get_generation_percentage'
    ]
    list_filter = ['month', 'area', 'alert_80_sent', 'alert_100_sent']
    search_fields = ['area__name']
    readonly_fields = ['created_at', 'updated_at']
    
    def get_generation_percentage(self, obj):
        return f"{obj.get_generation_percentage():.1f}%"
    get_generation_percentage.short_description = 'Uso (%)'


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
