"""
Django settings for olympiadesnsi project.

Generated by 'django-admin startproject' using Django 5.0.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.0/ref/settings/
"""

from pathlib import Path

from dotenv import load_dotenv
import os
from decouple import Config, Csv


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# path of env variables
env_path = BASE_DIR + "/.env"

load_dotenv(dotenv_path=env_path)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
# config Object with right path
config = Config(env_path)


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY')

EMAIL_HOST = config('EMAIL_HOST')
EMAIL_PORT = config('EMAIL_PORT')
ADMIN_NAME = config('ADMIN_NAME')
EMAIL_HOST_USER = config('EMAIL_HOST_USER')
ADMIN_EMAIL = config('ADMIN_EMAIL')
EMAIL_WITH_PASSWORD = config('EMAIL_WITH_PASSWORD', cast=bool)
if EMAIL_WITH_PASSWORD:
    EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
EMAIL_BACKEND = config('EMAIL_BACKEND')
EMAIL_USE_TLS = config('EMAIL_USE_TLS', cast=bool)
EMAIL_USE_SSL = config('EMAIL_USE_SSL', cast=bool)

SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', cast=bool)
CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', cast=bool)
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', cast=bool)


# SECURITY WARNING: don't run with debug turned on in production!

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost', cast=Csv())

DEBUG = config("DEBUG", default=False, cast=bool)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "crispy_forms",
    "crispy_bootstrap5",
    "olympiadesnsi",
    "accueil",
    "login",
    "epreuve",
    "intranet",
    "inscription",
    "captcha",
    "django_extensions",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django_ratelimit.middleware.RatelimitMiddleware',
]

# Dans settings.py
RATELIMIT_VIEW = 'olympiadesnsi.views.ratelimited_error'

RATELIMIT_USE_CACHE = 'default'
RATELIMIT_ENABLE = True

ROOT_URLCONF = "olympiadesnsi.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, 'olympiadesnsi/templates'),
                 os.path.join(BASE_DIR, 'login/templates'),
                 os.path.join(BASE_DIR, 'accueil/templates')],
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

WSGI_APPLICATION = "olympiadesnsi.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': config('NAME_OLYMPIADESNSI_DB'),
        'USER': config('USER_ADMIN_OLYMPIADESNSI_DB'),
        'PASSWORD': config('PASSWORD_ADMIN_OLYMPIADESNSI_DB'),
        'HOST': config('HOST_DB'),
        'PORT': '5432',
    }
}

# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'fr-fr'

TIME_ZONE = 'Europe/Paris'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGOUT_REDIRECT_URL = 'home'

CRISPY_ALLOWED_TEMPLATE_PACKS = ["bootstrap5"]

CRISPY_TEMPLATE_PACK = 'bootstrap5'
