{
  "username": "tanishq",
  "password": "123456"
}

On first terminal:
uvicorn app:main --reload  

To run on second terminal :
celery -A services.tasks worker --loglevel=info --pool=solo