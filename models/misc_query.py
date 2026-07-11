from pydantic import BaseModel, Field

class MiscQuery(BaseModel):
    question: str = Field(..., description="Miscellaneous question (e.g., calculators, drug interactions)")
