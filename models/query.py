from pydantic import BaseModel,Field
from models.document_type import DocumentType

class Query(BaseModel):
    question:str=Field(...,description="Question related to medical report")
    patient_id: str=Field(...,description="Patient ID")
    document_type: DocumentType=Field(...,description="Type of document")