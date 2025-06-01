from pathlib import Path
import os
from dotenv import load_dotenv
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
DEBUG = os.getenv('DJANGO_DEBUG')

ALLOWED_HOSTS_STRING = os.getenv("ALLOWED_HOSTS")
ALLOWED_HOSTS = [host.strip() for host in ALLOWED_HOSTS_STRING.split(',') if host.strip()]


INSTALLED_APPS = [
    'jazzmin',

    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Custom apps
    'corsheaders',
    # Third-party apps
    'rest_framework',
    'rest_framework.authtoken',
    'dj_rest_auth',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',  # Optional for social login

    'import_export',
    'custom_user',
    'visions',
    'wallet'
]

MIDDLEWARE = [
    # Cors Headers
    'corsheaders.middleware.CorsMiddleware', 

    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    # G-auth Middleware
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "auth_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS":[os.path.join(BASE_DIR,'templates')],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "auth_backend.wsgi.application"


# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT=os.path.join(BASE_DIR,'staticfiles')
STATICFILES_DIRS=[os.path.join(BASE_DIR,'static')]

MEDIA_URL='/media/'
MEDIA_ROOT=os.path.join(BASE_DIR,'media')

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST_KEY')
EMAIL_PORT = os.getenv('EMAIL_HOST_PORT')
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER_EMAIL")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_USER_PASSWORD")
EMAIL_USE_TLS=os.getenv("EMAIL_USE_TLS")
EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend'

ACCOUNT_EMAIL_REQUIRED = os.getenv('EMAIL_ACCOUNT_REQUIRED')
ACCOUNT_EMAIL_VERIFICATION = os.getenv('EMAIL_ACCOUNT_VERIFICATION')
LOGIN_REDIRECT_URL = os.getenv('EMAIL_LOGIN_REDIRECT_URL')


# -----------------------------------------------------------------------------------------------
# ---------------------CUSTOM SETTINGS-----------------------------------------------------------
# -----------------------------------------------------------------------------------------------

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

SITE_ID = 1
ACCOUNT_LOGIN_METHODS = ['email']
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

JAZZMIN_SETTINGS = {
    "site_title": "visora",
    "site_header": "visora Dashboard",
    "site_brand": "visora",
    "site_logo": "../static/assets/img/avatar.webp", 
    "login_logo": "../static/assets/img/avatar.webp",
    "welcome_sign": "Welcome to visora Admin Panel",
    "copyright": "visora © 2025",
    "user_avatar": "profile.picture", 


    # Footer Links
    "footer_links": [
        {"name": "visora", "url": "https://visora.cloud", "new_window": True},
        {"name": "Support", "url": "mailto:support@@gmail.com", "new_window": True},
    ],

    "custom_css": "../static/assets/css/jazzmin.css",
    "custom_js": "../static/assets/js/jazzmin.js"
}

AUTH_USER_MODEL = "custom_user.CustomUser"

REST_AUTH_REGISTER_SERIALIZERS = {
    "REGISTER_SERIALIZER": "custom_user.serializers.CustomRegisterSerializer",
    'LOGIN_SERIALIZER': 'custom_user.serializers.CustomLoginSerializer',
}

REST_AUTH_SERIALIZERS = {
    "USER_DETAILS_SERIALIZER": "custom_user.serializers.CustomUserDetailsSerializer",
}


VISIORA_BACKEND_SECRET_KEY= os.getenv('DJANGO_ADMIN_SECRET_PATH')
VISIORA_DATA_API_URL= os.getenv('VISIORA_DATA_SERVER_API_URL')


RAZORPAY_KEY_ID= os.getenv('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET=os.getenv('RAZORPAY_KEY_SECRET')


# -----------------------------------------------------------------------------------------------
# ---------------------CUSTOM SETTINGS-----------------------------------------------------------
# -----------------------------------------------------------------------------------------------


# CORS Settings

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept', 'accept-encoding', 'authorization', 'content-type',
    'dnt', 'origin', 'user-agent', 'x-csrftoken', 'x-requested-with', 'x-anonymous-user-id',
]
CORS_ALLOW_METHODS = [
    'DELETE', 'GET', 'OPTIONS', 'PATCH', 'POST', 'PUT',
]

# CSRF Settings
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SECURE = False
