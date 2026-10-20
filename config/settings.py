"""
Configuración del proyecto SGR - Sistema de Gestión de Resultados
Delegaciones municipales - Ilustre Municipalidad de La Serena

Base de datos: MySQL/MariaDB administrada desde phpMyAdmin.
Las credenciales y secretos se leen desde el archivo .env (no se versiona).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "si", "on")


# ---------------------------------------------------------------------------
# Seguridad
# ---------------------------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "cambia-esta-clave-solo-para-desarrollo")
DEBUG = env_bool("DEBUG", True)
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if h.strip()]

# ---------------------------------------------------------------------------
# Aplicaciones (carpetas en inglés, según estructura del proyecto)
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Apps del SGR
    "core",
    "organizations",   # Delegacion, Cargo, ItemMedible, Funcionario, Rol, FuncionarioRol, Usuario
    "catalogs",        # Catalogo
    "measurement",     # Periodo, Meta, Indicador, Ajuste
    "activities",      # Actividad, Evidencia, Validacion
    "agenda",          # Compromiso, HistorialTransiciones
    "social",          # UsuarioSocial, AtencionSocial
    "audit",           # Auditoria
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.sgr_context",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Base de datos (MySQL / MariaDB - phpMyAdmin)
# Requiere: pip install mysqlclient
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("DB_NAME", "sgr_db"),
        "USER": os.getenv("DB_USER", "root"),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("DB_PORT", "3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

# ---------------------------------------------------------------------------
# Autenticación
# Usuario propio (tabla de credenciales del diagrama de clases),
# enlazado 1 a 1 con Funcionario. Los roles se asignan por FuncionarioRol.
# IMPORTANTE: definir antes de la primera migración.
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "organizations.Usuario"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Hash seguro (PBKDF2 por defecto de Django)
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"

# Sesiones protegidas
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 60 * 60 * 8          # 8 horas (jornada laboral)
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
CSRF_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)

# ---------------------------------------------------------------------------
# Internacionalización
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "es-cl"
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Archivos estáticos y evidencias (media)
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Parámetros de negocio del SGR (RF-007, RN-005, RN-006, RN-008, RNF-017)
# Son valores por defecto configurables; no se codifican dentro de la lógica.
# ---------------------------------------------------------------------------
SGR_TOPE_CUMPLIMIENTO = float(os.getenv("SGR_TOPE_CUMPLIMIENTO", 150))   # % máximo computable
SGR_UMBRAL_COLECTIVO = float(os.getenv("SGR_UMBRAL_COLECTIVO", 80))      # % umbral mínimo colectivo
SGR_SEMAFORO_AMBAR = float(os.getenv("SGR_SEMAFORO_AMBAR", 60))          # % del esperado para ámbar
SGR_SUMA_PONDERADORES = float(os.getenv("SGR_SUMA_PONDERADORES", 100))   # RN-001
SGR_MAX_GESTIONES_SOCIAL = int(os.getenv("SGR_MAX_GESTIONES_SOCIAL", 3)) # RN-012
SGR_DIAS_ALERTA_VENCIMIENTO = int(os.getenv("SGR_DIAS_ALERTA_VENCIMIENTO", 3))

# Evidencias (RNF-017)
SGR_EVIDENCIA_MAX_MB = int(os.getenv("SGR_EVIDENCIA_MAX_MB", 5))
SGR_EVIDENCIA_EXTENSIONES = ["jpg", "jpeg", "png", "pdf"]
FILE_UPLOAD_MAX_MEMORY_SIZE = SGR_EVIDENCIA_MAX_MB * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = FILE_UPLOAD_MAX_MEMORY_SIZE
