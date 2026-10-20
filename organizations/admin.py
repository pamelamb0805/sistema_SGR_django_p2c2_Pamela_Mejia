from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import Cargo, Delegacion, Funcionario, FuncionarioRol, ItemMedible, Rol, Usuario


@admin.register(Delegacion)
class DelegacionAdmin(admin.ModelAdmin):
    list_display = ("id_delegacion", "nombre", "ambito", "estado")
    list_filter = ("estado",)
    search_fields = ("nombre", "ambito")


class ItemMedibleInline(admin.TabularInline):
    model = ItemMedible
    extra = 0


@admin.register(Cargo)
class CargoAdmin(admin.ModelAdmin):
    list_display = ("id_cargo", "nombre_cargo", "vigencia_desde", "vigencia_hasta")
    search_fields = ("nombre_cargo",)
    inlines = [ItemMedibleInline]


@admin.register(ItemMedible)
class ItemMedibleAdmin(admin.ModelAdmin):
    list_display = ("id_item", "nombre_item", "tipo", "cargo", "vigencia")
    list_filter = ("tipo", "vigencia", "cargo")
    search_fields = ("nombre_item",)


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ("id_rol", "nombre_rol", "descripcion")
    search_fields = ("nombre_rol",)


class FuncionarioRolInline(admin.TabularInline):
    model = FuncionarioRol
    extra = 0


@admin.register(Funcionario)
class FuncionarioAdmin(admin.ModelAdmin):
    list_display = ("id_funcionario", "identificador_institucional", "nombre", "cargo", "delegacion", "estado")
    list_filter = ("estado", "delegacion", "cargo")
    search_fields = ("nombre", "identificador_institucional")
    inlines = [FuncionarioRolInline]


class UsuarioCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ("username", "funcionario")


class UsuarioChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = Usuario
        fields = "__all__"


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    form = UsuarioChangeForm
    add_form = UsuarioCreationForm
    list_display = ("username", "funcionario", "is_superuser", "last_login")
    search_fields = ("username", "funcionario__nombre")
    ordering = ("username",)
    list_filter = ("is_superuser",)
    filter_horizontal = ("groups", "user_permissions")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Funcionario", {"fields": ("funcionario",)}),
        ("Permisos técnicos", {"fields": ("is_superuser", "groups", "user_permissions")}),
        ("Fechas", {"fields": ("last_login",)}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("username", "funcionario", "password1", "password2")}),
    )
