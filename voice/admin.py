from django.contrib import admin
from .models import LovedOne


@admin.register(LovedOne)
class LovedOneAdmin(admin.ModelAdmin):
    list_display = ('name', 'relationship', )
    search_fields = ('name', 'relationship')
    list_filter = ('relationship',)
    
