from openai import OpenAI
from dotenv import load_dotenv
import os
from fastapi import FastAPI, File, HTTPException, UploadFile, Form, Depends
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
import json
import shutil
from pathlib import Path
from models.document_type import DocumentType
from models.query import Query
from models.misc_query import MiscQuery
from models.user import User
from pydantic import BaseModel
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("data")
UPLOAD_DIR.mkdir(exist_ok=True)


client = OpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url=os.getenv("GEMINI_BASE_URL"),
)





@app.get("/")
def home():
    return {"message": "Medical RAG API is running."}

@app.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    user = postgresDB.get_user_by_username(current_user.get("username", ""))
    return {"username": user["username"]} if user else {"username": "User"}

@app.get("/sessions")
def get_sessions(current_user: dict = Depends(get_current_user)):
    return postgresDB.get_chat_sessions(current_user["user_id"])

class RenameSessionRequest(BaseModel):
    title: str

@app.put("/sessions/{session_id}/title")
def rename_session(session_id: str, req: RenameSessionRequest, current_user: dict = Depends(get_current_user)):
    postgresDB.rename_chat_session(session_id, current_user["user_id"], req.title)
    return {"message": "Session renamed successfully"}

@app.get("/sessions/{session_id}")
def get_session_history(session_id: str, current_user: dict = Depends(get_current_user)):
    return postgresDB.get_chat_history(session_id, current_user["user_id"])


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
    
    ext = file.filename.lower().split('.')[-1]
    if ext not in ["pdf", "png", "jpg", "jpeg"]:
        raise HTTPException(
            status_code=400,
            detail="Only PDF and Image (PNG, JPG, JPEG) files are allowed.",
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
    elif task_result.status == "PROGRESS":
        result["task_info"] = task_result.info

    return result

@app.post("/ask")
def ask(query:Query, current_user:dict = Depends(get_current_user)):
    if query.session_id:
        title = query.question[:30] + "..." if len(query.question) > 30 else query.question
        postgresDB.create_chat_session(current_user["user_id"], query.session_id, title)
        
    def event_stream():
        # Yield the starting state
        yield f"data: {json.dumps({'type': 'status', 'message': 'Processing query...'})}\n\n"
        
        for event in rag_chain.stream({
            "query": query, 
            "user_id": current_user["user_id"]
        }):
            node_name = list(event.keys())[0]
            
            # Map node names to human-readable statuses
            status_msg = f"Executing {node_name}..."
            if node_name == "agent_router": status_msg = "Deciding routing strategy..."
            elif node_name == "query_analyzer": status_msg = "Analyzing medical concepts..."
            elif node_name == "retrieve": status_msg = "Searching your medical records..."
            elif node_name == "generate": status_msg = "Synthesizing medical answer..."
            elif node_name == "timeline": status_msg = "Generating chronological timeline..."
            elif node_name == "explainability": status_msg = "Structuring final report..."
            
            yield f"data: {json.dumps({'type': 'status', 'message': status_msg})}\n\n"
            
            if node_name in ["explainability", "casual"] or (node_name == "cache_check" and "final_response" in event[node_name]):
                # Stream the final response
                yield f"data: {json.dumps({'type': 'final', 'message': event[node_name]['final_response']})}\n\n"
                
    return StreamingResponse(event_stream(), media_type="text/event-stream")


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

@app.get("/user/statistics")
def get_user_statistics(current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    stats = postgresDB.get_user_statistics(user_id)
    return stats
