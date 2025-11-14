from django.contrib import admin
from django.utils.html import format_html
from .models import Driver, Admin, Rider, Tricycle

# Inline for Tricycle to show in Driver admin
class TricycleInline(admin.TabularInline):
    model = Tricycle
    extra = 0
    fields = ['plate_number', 'color', 'max_capacity', 'image_link', 'or_link', 'cr_link', 'mtop_link']
    readonly_fields = ['image_link', 'or_link', 'cr_link', 'mtop_link']
    
    def image_link(self, obj):
        if obj.image_url:
            return format_html('<a href="{}" target="_blank">View Tricycle Image</a>', obj.image_url)
        return "No image"
    image_link.short_description = 'Tricycle Image'
    
    def or_link(self, obj):
        if obj.or_image_url:
            return format_html('<a href="{}" target="_blank">View OR</a>', obj.or_image_url)
        return "No OR"
    or_link.short_description = 'Official Receipt'
    
    def cr_link(self, obj):
        if obj.cr_image_url:
            return format_html('<a href="{}" target="_blank">View CR</a>', obj.cr_image_url)
        return "No CR"
    cr_link.short_description = 'Certificate of Registration'
    
    def mtop_link(self, obj):
        if obj.mtop_image_url:
            return format_html('<a href="{}" target="_blank">View MTOP</a>', obj.mtop_image_url)
        return "No MTOP"
    mtop_link.short_description = 'MTOP/Franchise'

@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ['user', 'license_number', 'is_verified', 'status', 'date_hired']
    list_filter = ['is_verified', 'status']
    search_fields = ['user__username', 'user__email', 'license_number']
    readonly_fields = ['license_image_link', 'date_hired', 'years_of_service']
    inlines = [TricycleInline]
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Driver Details', {
            'fields': ('license_number', 'license_expiry', 'license_image_link', 'status', 'is_verified')
        }),
        ('Employment', {
            'fields': ('date_hired', 'years_of_service')
        }),
        ('Location', {
            'fields': ('current_latitude', 'current_longitude'),
            'classes': ('collapse',)
        }),
    )
    
    def license_image_link(self, obj):
        if obj.license_image_url:
            return format_html('<a href="{}" target="_blank">View License Image</a>', obj.license_image_url)
        return "No license image"
    license_image_link.short_description = "Driver's License Image"

@admin.register(Tricycle)
class TricycleAdmin(admin.ModelAdmin):
    list_display = ['plate_number', 'color', 'max_capacity', 'driver']
    search_fields = ['plate_number', 'driver__user__username']
    readonly_fields = ['image_link', 'or_link', 'cr_link', 'mtop_link', 'created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('plate_number', 'color', 'max_capacity', 'driver')
        }),
        ('Images', {
            'fields': ('image_url', 'image_link')
        }),
        ('Registration Documents', {
            'fields': ('or_image_url', 'or_link', 'cr_image_url', 'cr_link', 'mtop_image_url', 'mtop_link')
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def image_link(self, obj):
        if obj.image_url:
            return format_html('<a href="{}" target="_blank">View Tricycle Image</a>', obj.image_url)
        return "No image"
    image_link.short_description = 'Tricycle Image Preview'
    
    def or_link(self, obj):
        if obj.or_image_url:
            return format_html('<a href="{}" target="_blank">View OR Document</a>', obj.or_image_url)
        return "No OR uploaded"
    or_link.short_description = 'Official Receipt Preview'
    
    def cr_link(self, obj):
        if obj.cr_image_url:
            return format_html('<a href="{}" target="_blank">View CR Document</a>', obj.cr_image_url)
        return "No CR uploaded"
    cr_link.short_description = 'Certificate of Registration Preview'
    
    def mtop_link(self, obj):
        if obj.mtop_image_url:
            return format_html('<a href="{}" target="_blank">View MTOP Document</a>', obj.mtop_image_url)
        return "No MTOP uploaded"
    mtop_link.short_description = 'MTOP/Franchise Preview'

# Register your models here.
admin.site.register(Admin)
admin.site.register(Rider)