from openai import OpenAI
from dotenv import load_dotenv
import os
from fastapi import FastAPI, File, HTTPException, UploadFile, Form, Depends
from fastapi.security import OAuth2PasswordRequestForm
import shutil
from pathlib import Path
from models.document_type import DocumentType
from models.query import Query
from models.misc_query import MiscQuery
from models.user import User
from services.qdrantDB import qdrantDB
from services.postgresDB import postgresDB
from services.semantic_cache import semanticCache
from services.auth import get_current_user, create_access_token, verify_password, get_password_hash
from services.langgraph_orchestration import rag_chain, process_misc_tools
from celery.result import AsyncResult
from services.tasks import process_document_task, celery_app
from config import settings


load_dotenv()

app = FastAPI(
    title="Medical Assistant RAG",
    version="1.0.0",
)

UPLOAD_DIR = Path("data")
UPLOAD_DIR.mkdir(exist_ok=True)


client = OpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url=os.getenv("GEMINI_BASE_URL"),
)

# -------------------------
# Prompt
# -------------------------
SYSTEM_PROMPT = """
You are an experienced medical assistant.

Explain medical reports in simple language.

Rules:
- Also ONLY answer if context is related to medical as you are a Medical Assistant.
- If Question is not related to Medical then dont answer. Simply say ONLY ask questions related to medical reports.
- Answer ONLY from the provided context.
- Do not hallucinate.
- Mention abnormal values first.
- Explain findings in simple language.
- Mention normal findings briefly.
- Do NOT diagnose diseases.
- Do NOT prescribe medications.
- If the answer is not present in the context, clearly say so.
- End with a short bullet list of important findings.
- ALWAYS include inline citations in your answer using the provided Citation ID (e.g., [1], [2]) immediately after every claim or fact derived from the context.
"""



@app.get("/")
def home():
    return {"message": "Medical RAG API is running."}


@app.post("/register")
def register(user:User):
    existing = postgresDB.get_user_by_username(user.username)
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")
    hashed = get_password_hash(user.password)
    new_user = postgresDB.create_user(user.username, hashed)
    return {"message": "User created successfully", "user_id": new_user["id"]}

@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = postgresDB.get_user_by_username(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    access_token = create_access_token(data={"sub": user["username"], "user_id": user["id"]})
    return {"access_token": access_token, "token_type": "bearer"}
    

@app.post("/upload")
def upload_file(
    file:UploadFile=File(...),
    document_type:DocumentType=Form(...),
    current_user: dict = Depends(get_current_user)
    ):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed.",
        )

    filepath = UPLOAD_DIR/file.filename

    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    task = process_document_task.delay(str(filepath),document_type.value,current_user["user_id"])

    return {
        "message": "PDF uploaded successfully.",
        "task_id":task.id,
        "filename": file.filename,
        "document_type": document_type,
        "user_id":current_user["user_id"]
    }


@app.get("/upload/status/{task_id}")
def get_upload_status(task_id:str,current_user:dict=Depends(get_current_user)):
    task_result = AsyncResult(task_id,app=celery_app)

    result = {
        "task_id":task_id,
        "task_status":task_result.status
    }

    if task_result.status == "SUCCESS":
        result["task_result"] = task_result.result
    elif task_result.status == "FAILURE":
        result["task_error"] = str(task_result.result)
        
    return result

@app.post("/ask")
def ask(query:Query, current_user:dict = Depends(get_current_user)):
    
    # 1. Execute the entire LCEL chain
    result_state = rag_chain.invoke({
        "query": query, 
        "user_id": current_user["user_id"]
    })
    
    # 2. Return the final output
    return result_state["final_response"]


@app.post("/tools")
def run_tools(query: MiscQuery, current_user:dict = Depends(get_current_user)):
    # Run the standalone tools process
    result = process_misc_tools(query.question)
    return result


@app.delete("/clear")
def clear_all_data(current_user: dict = Depends(get_current_user)):
    # 1. Clear PostgreSQL
    postgresDB.clear_data()
    
    # 2. Clear Qdrant
    qdrantDB.clear_data()
    
    # 3. Clear Semantic Cache (Redis)
    semanticCache.clear()
    
    # 3. Clear PDF files in data directory
    for item in UPLOAD_DIR.iterdir():
        if item.is_file():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)
            
    return {"message": "All database records and uploaded files cleared successfully."}

