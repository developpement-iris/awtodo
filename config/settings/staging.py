from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")

SECRET_KEY = env("DJANGO_SECRET_KEY")

DATABASES = {
    "default": env.db("DATABASE_URL"),
}
