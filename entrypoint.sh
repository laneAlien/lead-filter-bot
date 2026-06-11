#!/bin/sh
set -e
alembic upgrade head
exec python -m apps.bot.main
