from pydantic import BaseModel,Field
from typing import Optional
from models.document_type import DocumentType

class Query(BaseModel):
    question:str=Field(...,description="Question related to medical report")
    document_type: DocumentType=Field(...,description="Type of document")
    session_id:Optional[str] = Field(None,description="Session ID for conversation history")