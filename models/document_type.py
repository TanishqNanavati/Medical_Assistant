from enum import Enum

class DocumentType(str,Enum):
    PATIENT_HISTORY = "patient_history"
    LAB_REPORT = "lab_report"
    MEDICAL_GUIDELINE = "medical_guideline"
    UNKNOWN = "unknown"


