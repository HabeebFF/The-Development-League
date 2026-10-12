from django.contrib import admin

from .models import PageView


@admin.register(PageView)
class PageViewAdmin(admin.ModelAdmin):
    list_display = ["created_at", "path", "source", "device", "browser", "audience"]
    list_filter = ["audience", "device", "browser"]
    search_fields = ["path", "source"]
