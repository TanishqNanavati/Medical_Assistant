from pydantic import BaseModel,Field

class User(BaseModel):
    username:str = Field(...,description="User's username")
    password:str = Field(...,description="User's unique password")

