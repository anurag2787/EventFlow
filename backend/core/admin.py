from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Activity, Event, Organization, Repository, User, WebhookSubscription


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    readonly_fields = ('created_at',)
    list_display = ('username', 'email', 'is_staff', 'is_active', 'created_at')
    ordering = ('username',)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)


@admin.register(Repository)
class RepositoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'provider', 'external_id', 'organization', 'created_at')
    list_filter = ('provider',)
    search_fields = ('name', 'external_id')


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = (
        'provider',
        'external_id',
        'event_type',
        'status',
        'repository',
        'received_at',
        'processed_at',
        'retry_count',
    )
    list_filter = ('provider', 'status')
    search_fields = ('external_id', 'event_type')


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('activity_type', 'repository', 'actor', 'target_id', 'created_at')
    list_filter = ('activity_type',)
    search_fields = ('target_id',)


@admin.register(WebhookSubscription)
class WebhookSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('provider', 'organization', 'repository', 'active', 'created_at')
    list_filter = ('provider', 'active')
    search_fields = ('provider',)
