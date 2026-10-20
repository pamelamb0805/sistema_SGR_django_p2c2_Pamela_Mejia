"""
Modelos de organizations, 100 % basados en el diagrama E-R:
DELEGACION, CARGO, ITEM_MEDIBLE, FUNCIONARIO, ROL, FUNCIONARIO_ROL.

Además incluye Usuario (credenciales de acceso, tomado del diagrama de clases),
enlazado 1 a 1 con Funcionario. Un funcionario puede tener varios roles
mediante FUNCIONARIO_ROL.
"""
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


# ---------------------------------------------------------------------------
# DELEGACION
# ---------------------------------------------------------------------------
class Delegacion(models.Model):
    ESTADO_ACTIVA = "Activa"
    ESTADO_INACTIVA = "Inactiva"
    ESTADOS = [(ESTADO_ACTIVA, "Activa"), (ESTADO_INACTIVA, "Inactiva")]

    id_delegacion = models.AutoField(primary_key=True)
    nombre = models.CharField(
        max_length=100, unique=True,
        error_messages={"unique": "Ya existe una delegación con ese nombre."},
    )
    estado = models.CharField(max_length=10, choices=ESTADOS, default=ESTADO_ACTIVA)
    ambito = models.CharField(max_length=150)

    class Meta:
        db_table = "delegacion"
        ordering = ["nombre"]
        verbose_name = "delegación"
        verbose_name_plural = "delegaciones"

    def __str__(self):
        return self.nombre

    @property
    def activa(self):
        return self.estado == self.ESTADO_ACTIVA


# ---------------------------------------------------------------------------
# CARGO
# ---------------------------------------------------------------------------
class CargoQuerySet(models.QuerySet):
    def vigentes(self, fecha=None):
        fecha = fecha or timezone.localdate()
        return self.filter(vigencia_desde__lte=fecha).filter(
            Q(vigencia_hasta__isnull=True) | Q(vigencia_hasta__gte=fecha)
        )


class Cargo(models.Model):
    id_cargo = models.AutoField(primary_key=True)
    nombre_cargo = models.CharField(
        max_length=100, unique=True,
        error_messages={"unique": "Ya existe un cargo con ese nombre."},
    )
    vigencia_desde = models.DateField()
    vigencia_hasta = models.DateField(null=True, blank=True)

    objects = CargoQuerySet.as_manager()

    class Meta:
        db_table = "cargo"
        ordering = ["nombre_cargo"]

    def __str__(self):
        return self.nombre_cargo

    def clean(self):
        if self.vigencia_desde and self.vigencia_hasta and self.vigencia_hasta < self.vigencia_desde:
            raise ValidationError({"vigencia_hasta": "La vigencia final no puede ser anterior a la inicial."})

    @property
    def vigente(self):
        hoy = timezone.localdate()
        return self.vigencia_desde <= hoy and (self.vigencia_hasta is None or self.vigencia_hasta >= hoy)


# ---------------------------------------------------------------------------
# ITEM_MEDIBLE
# ---------------------------------------------------------------------------
class ItemMedible(models.Model):
    TIPO_CUANTITATIVO = "Cuantitativo"
    TIPO_PORCENTUAL = "Porcentual"   # RN-002: debe declarar fórmula específica
    TIPOS = [(TIPO_CUANTITATIVO, "Cuantitativo"), (TIPO_PORCENTUAL, "Porcentual")]

    id_item = models.AutoField(primary_key=True)
    nombre_item = models.CharField(max_length=150)
    tipo = models.CharField(max_length=15, choices=TIPOS, default=TIPO_CUANTITATIVO)
    vigencia = models.BooleanField(default=True)
    cargo = models.ForeignKey(
        Cargo, on_delete=models.CASCADE, db_column="id_cargo", related_name="items",
    )

    class Meta:
        db_table = "item_medible"
        ordering = ["cargo", "nombre_item"]
        constraints = [
            models.UniqueConstraint(fields=["cargo", "nombre_item"], name="uq_item_cargo_nombre"),
        ]
        verbose_name = "ítem medible"
        verbose_name_plural = "ítems medibles"

    def __str__(self):
        return f"{self.nombre_item} ({self.cargo})"


# ---------------------------------------------------------------------------
# ROL
# ---------------------------------------------------------------------------
class Rol(models.Model):
    id_rol = models.AutoField(primary_key=True)
    nombre_rol = models.CharField(
        max_length=50, unique=True,
        error_messages={"unique": "Ya existe un rol con ese nombre."},
    )
    descripcion = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "rol"
        ordering = ["nombre_rol"]
        verbose_name_plural = "roles"

    def __str__(self):
        return self.nombre_rol


# ---------------------------------------------------------------------------
# FUNCIONARIO
# ---------------------------------------------------------------------------
class Funcionario(models.Model):
    ESTADO_ACTIVO = "Activo"
    ESTADO_INACTIVO = "Inactivo"
    ESTADOS = [(ESTADO_ACTIVO, "Activo"), (ESTADO_INACTIVO, "Inactivo")]

    id_funcionario = models.AutoField(primary_key=True)
    identificador_institucional = models.CharField(
        max_length=30, unique=True,
        error_messages={"unique": "Ya existe un funcionario con ese identificador institucional."},
    )
    nombre = models.CharField(max_length=150)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=ESTADO_ACTIVO)
    cargo = models.ForeignKey(
        Cargo, on_delete=models.PROTECT, db_column="id_cargo", related_name="funcionarios",
    )
    delegacion = models.ForeignKey(
        Delegacion, on_delete=models.PROTECT, db_column="id_delegacion", related_name="funcionarios",
    )
    roles = models.ManyToManyField(Rol, through="FuncionarioRol", related_name="funcionarios")

    class Meta:
        db_table = "funcionario"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    @property
    def activo(self):
        return self.estado == self.ESTADO_ACTIVO


# ---------------------------------------------------------------------------
# FUNCIONARIO_ROL
# ---------------------------------------------------------------------------
class FuncionarioRol(models.Model):
    id_funcionario_rol = models.AutoField(primary_key=True)
    funcionario = models.ForeignKey(
        Funcionario, on_delete=models.CASCADE, db_column="id_funcionario",
        related_name="funcionario_roles",
    )
    rol = models.ForeignKey(
        Rol, on_delete=models.PROTECT, db_column="id_rol", related_name="funcionario_roles",
    )

    class Meta:
        db_table = "funcionario_rol"
        constraints = [
            models.UniqueConstraint(fields=["funcionario", "rol"], name="uq_funcionario_rol"),
        ]

    def __str__(self):
        return f"{self.funcionario} - {self.rol}"


# ---------------------------------------------------------------------------
# USUARIO DE ACCESO (credenciales) - tabla agregada al E-R por requerimiento
# ---------------------------------------------------------------------------
class UsuarioManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, username, password=None, funcionario=None, **extra):
        if not username:
            raise ValueError("El nombre de usuario es obligatorio.")
        usuario = self.model(username=username, funcionario=funcionario, **extra)
        usuario.set_password(password)   # hash seguro, nunca texto plano
        usuario.save(using=self._db)
        return usuario

    def create_superuser(self, username, password=None, **extra):
        extra.setdefault("is_superuser", True)
        return self.create_user(username, password, **extra)


class Usuario(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(max_length=150, unique=True)
    password = models.CharField("contraseña", max_length=128, db_column="contrasenia")
    funcionario = models.OneToOneField(
        Funcionario, on_delete=models.PROTECT, db_column="id_funcionario",
        related_name="usuario", null=True, blank=True,
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    objects = UsuarioManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "usuario_acceso"
        verbose_name = "usuario de acceso"
        verbose_name_plural = "usuarios de acceso"

    def __str__(self):
        return self.username

    @property
    def is_active(self):
        """Un funcionario inactivo no puede ingresar (RF-002)."""
        if self.funcionario_id:
            return self.funcionario.estado == Funcionario.ESTADO_ACTIVO
        return self.is_superuser

    @property
    def is_staff(self):
        """Solo el superusuario técnico entra al /admin de Django."""
        return self.is_superuser
