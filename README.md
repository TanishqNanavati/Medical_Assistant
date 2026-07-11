{
  "username": "abc",
  "password": "123456"
},
{
  "username": "def",
  "password": "1234567890"
}


On first terminal:
uvicorn app:main --reload  

To run on second terminal :
celery -A services.tasks worker --loglevel=info --pool=solo