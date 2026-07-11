import os
import math
import requests
from typing import TypedDict, Optional, List, Dict, Any

from openai import OpenAI
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool

from models.query import Query
from services.hybrid_retriever import hybridRetriever
from services.generation_judge import generationJudge
from services.semantic_cache import semanticCache
from services.chat_memory import chat_memory
from services.query_reformulator import queryReformulator
from services.postgresDB import postgresDB
from config import settings

load_dotenv()

class RAGState(TypedDict, total=False):
    query: Query
    user_id: int
    chat_history: Optional[List[Dict[str, str]]]
    search_question: Optional[str]
    cached_response: Optional[Dict[str, Any]]
    docs: Optional[List[Any]]
    retrieval_metadata: Optional[Dict[str, Any]]
    final_response: Optional[Dict[str, Any]]
    route_decision: Optional[str]

@tool
def analyze_drug_interactions(medications: list[str]) -> str:
    """Analyzes a list of medications for potential drug-drug interactions using the official OpenFDA API."""
    if len(medications) < 2:
        return "Need at least 2 medications to check for interactions."
        
    fda_context = ""
    for med in medications:
        try:
            url = f"https://api.fda.gov/drug/label.json?search=openfda.generic_name:\"{med}\"&limit=1"
            res = requests.get(url, timeout=5).json()
            if "results" in res and len(res["results"]) > 0:
                data = res["results"][0]
                fda_context += f"\n--- FDA Label for {med.upper()} ---\n"
                if "drug_interactions" in data:
                    fda_context += "Drug Interactions: " + " ".join(data["drug_interactions"]) + "\n"
                if "warnings" in data:
                    fda_context += "Warnings: " + " ".join(data["warnings"]) + "\n"
                if "ask_doctor_or_pharmacist" in data:
                    fda_context += "Ask Doctor: " + " ".join(data["ask_doctor_or_pharmacist"]) + "\n"
                if "do_not_use" in data:
                    fda_context += "Do Not Use: " + " ".join(data["do_not_use"]) + "\n"
        except Exception:
            continue
            
    if not fda_context:
        return "Could not retrieve official FDA labels for these medications."
        
    prompt = f"""
    You are a medical assistant checking for drug interactions.
    Based STRICTLY and ONLY on the official FDA label text below, are there any interactions, warnings, or contraindications between these specific medications: {', '.join(medications)}?
    If the FDA text explicitly mentions one of the other drugs as a warning, list it. If not, state that no interaction was found in the official label.
    
    FDA TEXT:
    {fda_context}
    """
    
    try:
        res = client.chat.completions.create(
            model=os.getenv("GEMINI_MODEL"),
            messages=[{"role": "user", "content": prompt}]
        )
        return "⚠️ **Official FDA Label Check:**\n\n" + res.choices[0].message.content
    except Exception as e:
        return f"Error checking interactions: {e}"

@tool
def calculate_ascvd_risk(age: int, gender: str, total_cholesterol: float, hdl_cholesterol: float, systolic_bp: float, is_smoker: bool, is_diabetic: bool, treated_for_bp: bool) -> str:
    """Calculates the 10-year ASCVD risk score."""
    risk = max(0, (age - 40) * 0.2)
    risk += 2.0 if gender.lower() == "male" else 0
    risk += (systolic_bp - 120) * 0.1 if systolic_bp > 120 else 0
    risk += 1.0 if treated_for_bp else 0
    risk += (total_cholesterol - 200) * 0.05 if total_cholesterol > 200 else 0
    risk += 1.5 if hdl_cholesterol < 40 else 0
    risk += 4.0 if is_smoker else 0
    risk += 3.0 if is_diabetic else 0
        
    risk = min(max(risk, 0.1), 99.9)
    
    if risk < 5.0: rec = "Low Risk. Focus on lifestyle."
    elif risk < 7.5: rec = "Borderline Risk. Consider moderate-intensity statin."
    elif risk < 20.0: rec = "Intermediate Risk. Moderate to high-intensity statin."
    else: rec = "High Risk. High-intensity statin strongly recommended."
        
    return f"10-Year ASCVD Risk: {risk:.1f}%\nRecommendation: {rec}"

@tool
def calculate_egfr(age: int, gender: str, serum_creatinine: float) -> str:
    """Calculates eGFR to assess kidney function."""
    if serum_creatinine <= 0:
        return "Invalid creatinine value."
        
    is_female = gender.lower() == "female"
    kappa = 0.7 if is_female else 0.9
    alpha = -0.241 if is_female else -0.302
    
    scr_k = serum_creatinine / kappa
    egfr = 142 * (min(scr_k, 1.0) ** alpha) * (max(scr_k, 1.0) ** -1.200) * (0.9938 ** age)
    if is_female: egfr *= 1.012
        
    if egfr >= 90: stage = "Stage 1 (Normal)"
    elif egfr >= 60: stage = "Stage 2 (Mildly decreased)"
    elif egfr >= 45: stage = "Stage 3a (Mild-Moderate)"
    elif egfr >= 30: stage = "Stage 3b (Moderate-Severe)"
    elif egfr >= 15: stage = "Stage 4 (Severe)"
    else: stage = "Stage 5 (Kidney failure)"
        
    return f"eGFR: {egfr:.1f} mL/min/1.73m²\nAssessment: {stage}"

@tool
def calculate_fib4(age: int, ast: float, alt: float, platelets: float) -> str:
    """Calculates FIB-4 index for liver fibrosis risk."""
    if alt <= 0 or platelets <= 0:
        return "Invalid lab values."
        
    fib4 = (age * ast) / (platelets * math.sqrt(alt))
    
    if fib4 < 1.45: risk = "Low risk of advanced fibrosis."
    elif fib4 > 3.25: risk = "High risk (consult hepatologist)."
    else: risk = "Intermediate risk."
        
    return f"FIB-4 Index: {fib4:.2f}\nAssessment: {risk}"

@tool
def calculate_chads2_vasc(age: int, gender: str, heart_failure: bool, hypertension: bool, stroke: bool, vascular: bool, diabetes: bool) -> str:
    """Calculates CHA2DS2-VASc score for stroke risk."""
    score = sum([heart_failure, hypertension, diabetes, vascular])
    score += 2 if age >= 75 else (1 if age >= 65 else 0)
    score += 2 if stroke else 0
    score += 1 if gender.lower() == "female" else 0
        
    if score == 0: rec = "Low risk. Anticoagulation not recommended."
    elif score == 1 and gender.lower() == "male": rec = "Moderate risk. Anticoagulation considered."
    else: rec = "High risk. Anticoagulation recommended."
        
    return f"CHA2DS2-VASc Score: {score}\nRecommendation: {rec}"

@tool
def generate_patient_timeline() -> str:
    """Generates a timeline of the patient's medical history."""
    return "timeline"

@tool
def search_report(query: str) -> str:
    """Searches the medical report."""
    return "rag"


# --- Nodes ---

def get_history_node(state: RAGState) -> dict:
    q = state["query"]
    history = chat_memory.get_history(state["user_id"], q.session_id) if q.session_id else []
    return {"chat_history": history}

def agent_router_node(state: RAGState) -> dict:
    llm = ChatGoogleGenerativeAI(model=os.getenv("GEMINI_MODEL"), api_key=os.getenv("GEMINI_API_KEY"))
    tools = [search_report, generate_patient_timeline]
    
    response = llm.bind_tools(tools).invoke(state["query"].question)
    
    if not response.tool_calls:
        return {"route_decision": "rag"}
        
    name = response.tool_calls[0]["name"]
        
    if name == "generate_patient_timeline":
        return {"route_decision": "timeline"}
        
    return {"route_decision": "rag"}


def process_misc_tools(question: str) -> dict:
    """Processes miscellaneous questions using clinical calculators and external APIs."""
    llm = ChatGoogleGenerativeAI(model=os.getenv("GEMINI_MODEL"), api_key=os.getenv("GEMINI_API_KEY"))
    tools = [
        analyze_drug_interactions, calculate_ascvd_risk, 
        calculate_egfr, calculate_fib4, calculate_chads2_vasc
    ]
    
    response = llm.bind_tools(tools).invoke(question)
    
    if not response.tool_calls:
        return {
            "question": question,
            "answer": "I can only answer calculator and drug interaction questions on this endpoint. For medical records, use the /ask endpoint.",
            "citations": [],
            "retrieval_metadata": {"route": "unknown"}
        }
        
    tool_call = response.tool_calls[0]
    name = tool_call["name"]
    
    calc_tools = {
        "analyze_drug_interactions": analyze_drug_interactions,
        "calculate_ascvd_risk": calculate_ascvd_risk,
        "calculate_egfr": calculate_egfr,
        "calculate_fib4": calculate_fib4,
        "calculate_chads2_vasc": calculate_chads2_vasc
    }
    
    if name in calc_tools:
        result = calc_tools[name].invoke(tool_call["args"])
        return {
            "question": question,
            "answer": result,
            "citations": [],
            "retrieval_metadata": {"route": name}
        }
        
    return {
        "question": question,
        "answer": "Tool not recognized.",
        "citations": [],
        "retrieval_metadata": {"route": "error"}
    }


def timeline_node(state: RAGState) -> dict:
    with postgresDB.conn.cursor() as cur:
        cur.execute("SELECT content FROM chunks WHERE user_id=%s AND document_type=%s", 
                   (state["user_id"], state["query"].document_type.value))
        text = "\n\n".join([r[0] for r in cur.fetchall()])
        
    if not text:
        return {"final_response": {"question": state["query"].question, "answer": "No documents found.", "citations": []}}
        
    prompt = f"Extract all medical events, diagnoses, and labs from the report and format as a chronological markdown timeline.\n\n{text}"
    response = client.chat.completions.create(
        model=os.getenv("GEMINI_MODEL"),
        messages=[{"role": "user", "content": prompt}]
    )
    
    return {"final_response": {
        "question": state["query"].question,
        "answer": response.choices[0].message.content,
        "citations": [],
        "retrieval_metadata": {"route": "timeline"}
    }}


def reformulate_node(state: RAGState) -> dict:
    sq = state["query"].question
    if state.get("chat_history"):
        sq = queryReformulator.reformulate(sq, state["chat_history"])
    return {"search_question": sq}

def cache_check_node(state: RAGState) -> dict:
    cached = semanticCache.get(state["search_question"], user_id=state["user_id"])
    if cached:
        if state["query"].session_id:
            chat_memory.add_turn(state["user_id"], state["query"].session_id, state["query"].question, cached["answer"])
        cached["question"] = state["query"].question
        return {"cached_response": cached, "final_response": cached}
    return {"cached_response": None}

def retrieve_node(state: RAGState) -> dict:
    q_obj = Query(question=state["search_question"], document_type=state["query"].document_type, session_id=state["query"].session_id)
    res = hybridRetriever.search(query=q_obj, user_id=state["user_id"], k=3)
    return {"docs": res["docs"], "retrieval_metadata": res["metadata"]}


client = OpenAI(api_key=os.getenv("GEMINI_API_KEY"), base_url=os.getenv("GEMINI_BASE_URL"))
SYSTEM_PROMPT = """You are a medical assistant. Explain findings simply. Mention abnormal values first. Answer ONLY from context. Don't prescribe. Use inline citations [1]."""

def generate_and_eval_node(state: RAGState) -> dict:
    docs = state.get("docs", [])
    if not docs:
        return {"final_response": {"question": state["query"].question, "answer": "Answer not found in context.", "citations": []}}

    context = ""
    citations = []
    for i, (doc, score) in enumerate(docs, 1):
        citations.append({"id": f"[{i}]", "page": doc.metadata.get("page", 0) + 1, "source": doc.metadata.get("source", "Unknown"), "score": round(score, 3)})
        context += f"Citation [{i}]\nText: {doc.page_content}\n"

    prompt = f"Context: {context}\nQuestion: {state['search_question']}"
    history = state.get("chat_history", [])
    
    decision, final_answer = "FAIL", ""
    eval_hist = []

    for _ in range(settings.max_rag_rounds):
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + [{"role": m["role"], "content": m["content"]} for m in history] + [{"role": "user", "content": prompt}]
        final_answer = client.chat.completions.create(model=os.getenv("GEMINI_MODEL"), messages=msgs).choices[0].message.content
        
        eval_res = generationJudge.evaluate(question=state["search_question"], context=context, ans=final_answer)
        decision = eval_res.get("decision", "FAIL").upper()
        faithfulness = float(eval_res.get("faithfulness", 0.0))
        
        eval_hist.append({"decision": decision, "faithfulness": faithfulness, "feedback": eval_res.get("feedback", "")})

        if decision == "PASS" and faithfulness >= settings.faithfulness_threshold:
            break
            
        prompt += f"\n\nPrevious answer rejected. Fix mistakes: {eval_res.get('feedback', '')}"

    meta = state.get("retrieval_metadata", {})
    meta["eval_history"] = eval_hist

    res = {"question": state["query"].question, "answer": final_answer, "citations": citations, "retrieval_metadata": meta}
    
    if decision == "PASS":
        semanticCache.set(state["search_question"], res, user_id=state["user_id"])
        if state["query"].session_id:
            chat_memory.add_turn(state["user_id"], state["query"].session_id, state["query"].question, final_answer)

    return {"final_response": res}


def route_after_cache(state: RAGState) -> str:
    return "end" if state.get("cached_response") else "retrieve"


workflow = StateGraph(RAGState)
workflow.add_node("get_history", get_history_node)
workflow.add_node("agent_router", agent_router_node)
workflow.add_node("reformulate", reformulate_node)
workflow.add_node("cache_check", cache_check_node)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("generate", generate_and_eval_node)
workflow.add_node("timeline", timeline_node)

workflow.set_entry_point("get_history")
workflow.add_edge("get_history", "agent_router")

workflow.add_conditional_edges(
    "agent_router",
    lambda state: state["route_decision"],
    {"rag": "reformulate", "timeline": "timeline", "end": END}
)

workflow.add_edge("reformulate", "cache_check")
workflow.add_conditional_edges("cache_check", route_after_cache, {"end": END, "retrieve": "retrieve"})
workflow.add_edge("retrieve", "generate")
workflow.add_edge("generate", END)
workflow.add_edge("timeline", END)

rag_chain = workflow.compile()
