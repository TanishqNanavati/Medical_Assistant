#!/bin/bash

# Start the Celery worker in the background
echo "Starting Celery Worker..."
celery -A services.tasks worker --loglevel=info --pool=solo &

# Start the FastAPI backend in the background
echo "Starting FastAPI Backend..."
uvicorn main:app --host 0.0.0.0 --port 8000 &

# Start the Next.js frontend
echo "Starting Next.js Frontend..."
cd frontend && npm start &

# Wait for any process to exit (if any crashes, the container stops)
wait -n
exit $?
