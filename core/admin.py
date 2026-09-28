from django.contrib import admin

from .models import ClothingRequest, Event, EventSignup, Notification

admin.site.register(Event)
admin.site.register(EventSignup)
admin.site.register(ClothingRequest)
admin.site.register(Notification)
