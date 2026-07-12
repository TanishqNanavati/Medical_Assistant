from celery import Celery
import os
from config import settings
from services.docs_loader import doc_loader
from services.image_processor import image_processor
from services.chunker import chunker
from services.qdrantDB import qdrantDB
from services.postgresDB import postgresDB


celery_app = Celery(
    "medical tasks",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)


@celery_app.task(bind=True,name="process_document_task")
def process_document_task(self,filepath:str,document_type:str,user_id:int):
    try:
        print(f"Starting background processing for {filepath}...")
        
        ext = filepath.lower().split('.')[-1]
        if ext in ['png', 'jpg', 'jpeg']:
            pages = image_processor.load(filepath)
        elif ext == 'pdf':
            pages = doc_loader.load(filepath)
        else:
            raise ValueError(f"Unsupported file format: {ext}")

        for page in pages:
            page.metadata["document_type"] = document_type
            page.metadata["user_id"] = user_id 

        chunks = chunker.chunk(pages)
        
        qdrantDB.add_documents(chunks)
        postgresDB.add_documents(chunks)

        from openai import OpenAI
        client = OpenAI(
            api_key=os.getenv("GEMINI_API_KEY"),
            base_url=os.getenv("GEMINI_BASE_URL"),
        )
        
        full_text = "\n".join([p.page_content for p in pages])
        # Generate summary
        summary_res = client.chat.completions.create(
            model=os.getenv("GEMINI_MODEL"),
            messages=[
                {"role": "system", "content": "You are a medical summarizer. Summarize the following medical document in 2-3 sentences max."},
                {"role": "user", "content": full_text[:30000]}
            ]
        )
        summary = summary_res.choices[0].message.content
        filename = os.path.basename(filepath)
        postgresDB.add_document(user_id, filename, document_type, summary)

        print("Background processing complete!")
        return {
            "status": "Success",
            "message": "PDF processed successfully.",
            "pages": len(pages),
            "chunks": len(chunks)
        }
    except Exception as e:
        print(f"Task Failed: {e}")
        raise e
        