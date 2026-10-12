from django.contrib import admin

from .models import Adjustment, Period, Task, TaskResult


@admin.register(Period)
class PeriodAdmin(admin.ModelAdmin):
    list_display = ["name", "starts_on", "ends_on"]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["date", "title", "rule", "pp_done", "pp_not_done", "is_published"]
    list_filter = ["period", "rule"]


@admin.register(TaskResult)
class TaskResultAdmin(admin.ModelAdmin):
    list_display = ["task", "team", "done", "override", "pp"]
    list_filter = ["task__period"]


@admin.register(Adjustment)
class AdjustmentAdmin(admin.ModelAdmin):
    list_display = ["period", "team", "kind", "pp", "reason"]
    list_filter = ["period", "kind"]
