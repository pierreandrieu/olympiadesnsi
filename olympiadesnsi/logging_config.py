import os
from pathlib import Path
from django.conf import settings

BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

MAX_LOG_SIZE = 2 * 1024 * 1024  # 2 Mo
BACKUP_COUNT = 5

DEFAULT_FORMAT = '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s'
DATE_FORMAT = '%d/%m/%Y %H:%M:%S'

logfile_debug = LOGS_DIR / 'django_debug.log'
logfile_prod = LOGS_DIR / 'django_production.log'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,

    'formatters': {
        'standard': {
            'format': DEFAULT_FORMAT,
            'datefmt': DATE_FORMAT,
        },
    },

    'handlers': {
        'rotating_file': {
            'level': 'DEBUG' if settings.DEBUG else 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(logfile_debug if settings.DEBUG else logfile_prod),
            'maxBytes': MAX_LOG_SIZE,
            'backupCount': BACKUP_COUNT,
            'formatter': 'standard',
        },
    },

    'loggers': {
        'django': {
            'handlers': ['rotating_file'],
            'level': 'DEBUG' if settings.DEBUG else 'WARNING',
            'propagate': True,
        },
        'django.request': {
            'handlers': ['rotating_file'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}
