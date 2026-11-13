from django.contrib import admin

from .models import Registration, ScrimLog, ScrimSession, ScrimSettings, Suspension

admin.site.register(ScrimSettings)
admin.site.register(ScrimSession)
admin.site.register(Registration)
admin.site.register(Suspension)
admin.site.register(ScrimLog)
