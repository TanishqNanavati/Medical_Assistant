# This is only for inserting in postgress db for bm25 search not dense -->(qdrant)

from pydantic import BaseModel,Field


class Chunk(BaseModel):
    content: str
    page: int
    source: str

    patient_id: str
    report_id: str
    document_type: str

