#!/bin/sh
# Run from project root directory via command `docker build -t app-fe -f /docker/Dockerfile-test .`

# If 'command' is passed to the entryscript, run the command and exit
if [ "$#" -gt 0 ]; then
    exec "$@"
    exit 0
fi

echo "Running database migrations.."
python manage.py makemigrations --noinput
python manage.py migrate --noinput

echo "Starting Django server.."
exec uvicorn backend.asgi:application --host 0.0.0.0 --port 8000