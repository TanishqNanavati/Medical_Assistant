import os
import base64
from typing import List
from langchain_core.documents import Document
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class ImageProcessor:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("GEMINI_API_KEY"),
            base_url=os.getenv("GEMINI_BASE_URL"),
        )
        self.model = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
        
    def _encode_image(self, filepath: str) -> str:
        with open(filepath, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
            
    def _get_mime_type(self, filepath: str) -> str:
        ext = filepath.lower().split('.')[-1]
        if ext in ['jpg', 'jpeg']:
            return "image/jpeg"
        elif ext == 'png':
            return "image/png"
        return "image/jpeg"

    def load(self, filepath: str) -> List[Document]:
        """
        Loads an image, sends it to Gemini for medical analysis, 
        and returns the result wrapped in a Document (matching doc_loader output).
        """
        base64_image = self._encode_image(filepath)
        mime_type = self._get_mime_type(filepath)
        
        prompt = (
            "You are an expert Chief Medical Radiologist and Analyst. "
            "Analyze this medical image (which could be an X-ray, MRI, CT scan, ECG, or lab report) in extreme detail. "
            "Extract all text, findings, anomalies, diagnoses, and measurements. "
            "Format your output as a highly structured clinical report containing: "
            "1. Primary Findings: Detailed description of what is seen. "
            "2. Differential Diagnoses: Possible conditions or diseases based on the findings. "
            "3. Severity/Urgency: Is this life-threatening, urgent, or routine? "
            "4. Clinical Recommendations: What should the next steps be (e.g., follow-up imaging, biopsy)?"
        )
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            temperature=0
        )
        
        # Wrap in a Langchain Document so chunker and vector DB can process it exactly like a PDF
        doc = Document(
            page_content=response.choices[0].message.content,
            metadata={"page": 0, "source": filepath}
        )
        
        return [doc]

image_processor = ImageProcessor()
