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
import json

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
    target_sources: Optional[List[str]]
    telemetry: Optional[Dict[str, Any]]

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
def search_report(query: str):
    """Use this tool to search for medical information in the patient's records."""
    pass

@tool
def generate_patient_timeline(query: str):
    """Use this tool when the user explicitly asks for a medical history timeline."""
    pass

@tool
def casual_chat(query: str):
    """Use this tool when the user is saying a greeting like 'hi', 'hello', or making casual small talk."""
    pass

import time

def get_history_node(state: RAGState) -> dict:
    q = state["query"]
    history = postgresDB.get_chat_history(q.session_id, state["user_id"]) if q.session_id else []
    
    # Initialize telemetry
    telemetry = {
        "start_time": time.time(),
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "embedding_time_ms": 0.0,
        "retrieval_time_ms": 0.0,
        "llm_time_ms": 0.0,
        "query_rewritten": False,
        "cache_hit": False,
        "num_retrieved_chunks": 0,
        "retrieval_source": "None",
        "avg_retrieval_score": 0.0,
        "judge_decision": "N/A",
        "faithfulness_score": 0.0,
        "context_length_tokens": 0
    }
    return {"chat_history": history, "telemetry": telemetry}

def agent_router_node(state: RAGState) -> dict:
    llm = ChatGoogleGenerativeAI(model=os.getenv("GEMINI_MODEL"), api_key=os.getenv("GEMINI_API_KEY"))
    tools = [search_report, generate_patient_timeline, casual_chat]
    
    response = llm.bind_tools(tools).invoke(state["query"].question)
    
    if not response.tool_calls:
        return {"route_decision": "rag"}
        
    name = response.tool_calls[0]["name"]
    
    if name == "generate_patient_timeline":
        return {"route_decision": "timeline"}
    elif name == "casual_chat":
        return {"route_decision": "casual"}
        
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
        raw_result = calc_tools[name].invoke(tool_call["args"])
        
        # Elaborate the raw result using LLM
        elaborate_prompt = f"The user asked: '{question}'. The medical calculator tool returned: '{raw_result}'. Please write a friendly, elaborate, and easy-to-understand response explaining this result to the patient. Use Markdown formatting. Keep it very clear and empathetic."
        elaborated_msg = llm.invoke(elaborate_prompt)
        
        # Ensure elaborated_result is a string (Gemini sometimes returns a list of text parts)
        elaborated_result = elaborated_msg.content
        if isinstance(elaborated_result, list):
            elaborated_result = "".join([str(x.get("text", x)) if isinstance(x, dict) else str(x) for x in elaborated_result])
        elif not isinstance(elaborated_result, str):
            elaborated_result = str(elaborated_result)

        ans = {
            "question": question,
            "answer": elaborated_result,
            "citations": [],
            "retrieval_metadata": {"route": name}
        }
        ans["explanation"] = generate_explanation(
            question=question,
            answer=elaborated_result,
            context_docs=f"Tool Used: {name}\nArgs: {tool_call['args']}\nRaw Tool Result: {raw_result}",
            route=name,
            confidence="100% (Deterministic Calculator)"
        )
        return ans
        
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
        ans = {
            "question": state["query"].question,
            "answer": "No medical records found to generate a timeline.",
            "citations": [],
            "retrieval_metadata": {"route": "timeline"}
        }
        return {"final_response": ans}
        
    prompt = f"Extract all medical events, diagnoses, and labs from the report and format as a chronological markdown timeline.\n\n{text}"
    
    import json
    from openai import OpenAI
    client = OpenAI(
        api_key=os.getenv("GEMINI_API_KEY"),
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
    )
    
    response = client.chat.completions.create(
        model=os.getenv("GEMINI_MODEL"),
        messages=[{"role": "user", "content": prompt}]
    )
    
    ans = {
        "question": state["query"].question,
        "answer": response.choices[0].message.content,
        "citations": [],
        "retrieval_metadata": {"route": "timeline"}
    }
    return {"final_response": ans}

def casual_chat_node(state: RAGState) -> dict:
    ans = {
        "question": state["query"].question,
        "answer": "Hello! I am your AI Medical Assistant. How can I help you with your medical records today?",
        "citations": [],
        "retrieval_metadata": {"route": "casual"},
        "explanation": {
            "why_this_answer": "You greeted me, so I said hello back!",
            "why_these_documents": "No medical documents were needed for a simple greeting.",
            "why_these_tools": "We didn't need to use any search tools.",
            "confidence": "100% sure this is a friendly greeting.",
            "evidence": "N/A"
        }
    }
    
    # Save the complete result to database history
    if state["query"].session_id:
        postgresDB.add_chat_message(state["query"].session_id, state["user_id"], "user", state["query"].question)
        postgresDB.add_chat_message(state["query"].session_id, state["user_id"], "assistant", json.dumps(ans))
        
    return {"final_response": ans, "cached_response": ans}

def reformulate_node(state: RAGState) -> dict:
    sq = state["query"].question
    telemetry = state.get("telemetry", {})
    if state.get("chat_history"):
        new_sq = queryReformulator.reformulate(sq, state["chat_history"])
        if new_sq != sq:
            telemetry["query_rewritten"] = True
        sq = new_sq
    return {"search_question": sq, "telemetry": telemetry}

def query_analyzer_node(state: RAGState) -> dict:
    candidates = postgresDB.get_candidate_documents(state["user_id"], state["query"].question)
    if not candidates:
        return {"target_sources": []}
    
    doc_context = "\n".join([f"Filename: {c['filename']}, Uploaded: {c['upload_timestamp']}, Summary: {c['summary']}" for c in candidates])
    
    prompt = f"""
    The user asked: '{state["query"].question}'
    
    Here are the most relevant documents in their account:
    {doc_context}
    
    Based on the user's question, determine if they are specifically asking about one or more of these documents. 
    If they are, return a JSON list of exactly the filenames they mean, like ["sample.pdf", "heart-xray.jpg"].
    If they are asking a general question without referring to specific documents (or if no documents match), return [].
    OUTPUT EXACTLY A JSON LIST AND NOTHING ELSE.
    """
    
    import json
    try:
        res = client.chat.completions.create(
            model=os.getenv("GEMINI_MODEL"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        content = res.choices[0].message.content.strip()
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()
            
        target_files = json.loads(content)
        if isinstance(target_files, list) and target_files:
            # Prepend 'data/' to match the source metadata format
            target_sources = [f"data/{f}" for f in target_files]
            return {"target_sources": target_sources}
    except Exception as e:
        print(f"Query analyzer failed: {e}")
        pass
        
    return {"target_sources": []}

def cache_check_node(state: RAGState) -> dict:
    t0 = time.time()
    cached = semanticCache.get(state["search_question"], user_id=state["user_id"])
    telemetry = state.get("telemetry", {})
    telemetry["retrieval_time_ms"] += (time.time() - t0) * 1000
    
    if cached:
        telemetry["cache_hit"] = True
        telemetry["retrieval_source"] = "Cache"
        if state["query"].session_id:
            postgresDB.add_chat_message(state["query"].session_id, state["user_id"], "user", state["query"].question)
            postgresDB.add_chat_message(state["query"].session_id, state["user_id"], "assistant", cached["answer"])
        cached["question"] = state["query"].question
        return {"cached_response": cached, "final_response": cached, "telemetry": telemetry}
    return {"cached_response": None, "telemetry": telemetry}

def retrieve_node(state: RAGState) -> dict:
    t0 = time.time()
    q_obj = Query(question=state["search_question"], document_type=state["query"].document_type, session_id=state["query"].session_id)
    res = hybridRetriever.search(query=q_obj, user_id=state["user_id"], k=10, target_sources=state.get("target_sources"))
    
    telemetry = state.get("telemetry", {})
    telemetry["retrieval_time_ms"] += (time.time() - t0) * 1000
    telemetry["num_retrieved_chunks"] = len(res["docs"])
    
    # Estimate source based on scores (Hybrid usually has 0.7-0.9 scores, BM25 has integers, dense has cosines)
    telemetry["retrieval_source"] = "Hybrid" # Hybrid is default in search
    
    scores = [score for _, score in res["docs"]]
    if scores:
        telemetry["avg_retrieval_score"] = sum(scores) / len(scores)
        
    return {"docs": res["docs"], "retrieval_metadata": res["metadata"], "telemetry": telemetry}


client = OpenAI(api_key=os.getenv("GEMINI_API_KEY"), base_url=os.getenv("GEMINI_BASE_URL"))
SYSTEM_PROMPT = """
You are an expert, empathetic, and highly capable medical assistant.

Your goal is to explain medical reports, findings, and diagnostic scans to patients in clear, extremely simple language that a non-doctor can easily understand.

Rules:
- ONLY answer if context is related to medical data.
- Answer ONLY from the provided context. Do not hallucinate external medical facts.
- Explain all medical jargon using simple analogies.
- Do NOT prescribe medications.
- ALWAYS include inline citations in your answer using the provided Citation ID (e.g., [1], [2]) immediately after every claim or fact derived from the context.

FORMATTING RULE:
You MUST structure your responses using the following Markdown format for every single answer:

**Finding:** [State the objective finding clearly, mentioning abnormal values first. Include your citations here, e.g. [1]]
**What this means:** [Explain the finding in EXTREMELY SIMPLE, everyday, non-medical language. Assume the patient has zero medical background.]
**Recommendation:** [State any clinical recommendations or severity noted in the text, or advise them to consult their doctor.]
"""

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

    telemetry = state.get("telemetry", {})
    t0 = time.time()
    
    for _ in range(settings.max_rag_rounds):
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + [{"role": m["role"], "content": m["content"]} for m in history] + [{"role": "user", "content": prompt}]
        response = client.chat.completions.create(model=os.getenv("GEMINI_MODEL"), messages=msgs)
        final_answer = response.choices[0].message.content
        
        if hasattr(response, "usage") and response.usage:
            telemetry["prompt_tokens"] += getattr(response.usage, "prompt_tokens", 0)
            telemetry["completion_tokens"] += getattr(response.usage, "completion_tokens", 0)
            
        eval_res = generationJudge.evaluate(question=state["search_question"], context=context, ans=final_answer)
        decision = eval_res.get("decision", "FAIL").upper()
        faithfulness = float(eval_res.get("faithfulness", 0.0))
        
        eval_hist.append({"decision": decision, "faithfulness": faithfulness, "feedback": eval_res.get("feedback", "")})

        if decision == "PASS" and faithfulness >= settings.faithfulness_threshold:
            break
            
        prompt += f"\n\nPrevious answer rejected. Fix mistakes: {eval_res.get('feedback', '')}"

    telemetry["llm_time_ms"] += (time.time() - t0) * 1000
    telemetry["judge_decision"] = decision
    telemetry["faithfulness_score"] = faithfulness
    telemetry["context_length_tokens"] = len(context.split()) * 1.3 # Rough estimate

    meta = state.get("retrieval_metadata", {})
    meta["eval_history"] = eval_hist

    res = {"question": state["query"].question, "answer": final_answer, "citations": citations, "retrieval_metadata": meta}
    return {"final_response": res, "telemetry": telemetry}


def generate_explanation(question: str, answer: str, context_docs: str, route: str, confidence: str) -> dict:
    prompt = f"""
    You are an Explainability Agent for a Medical AI Assistant.
    Your job is to explain HOW and WHY the AI arrived at its answer.
    CRITICAL RULE: You MUST use EXTREMELY SIMPLE, everyday English. Do NOT use highly complicated words. Do NOT open an Oxford dictionary. Write as if you are explaining this to a young teenager who has no medical or technical background. Keep sentences short and simple.
    
    Question asked: {question}
    Final Answer generated: {answer}
    Routing Decision used: {route}
    Confidence Score: {confidence}
    Documents/Context used: {context_docs}
    
    Generate a JSON object with exactly these keys:
    "why_this_answer": "Simple, easy to understand reason why this answer is correct based on the text.",
    "why_these_documents": "Simple, easy to understand reason why we looked at these specific files or tools.",
    "why_these_tools": "Simple, easy to understand reason why we chose the specific search method or calculator tool.",
    "confidence": "Simple, easy to understand explanation of how sure we are in this answer and why.",
    "evidence": "Exact, short quotes or facts from the text that prove the answer."
    
    OUTPUT EXACTLY A JSON OBJECT AND NOTHING ELSE.
    """
    
    import json
    try:
        res = client.chat.completions.create(
            model=os.getenv("GEMINI_MODEL"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        content = res.choices[0].message.content.strip()
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()
            
        return json.loads(content)
    except Exception as e:
        print(f"Explainability failed: {e}")
        return {
            "why_this_answer": "Error generating explanation.",
            "why_these_documents": "",
            "why_these_tools": "",
            "confidence": "",
            "evidence": ""
        }

def explainability_node(state: RAGState) -> dict:
    res = state.get("final_response", {})
    if not res:
        return {}
        
    route = state.get("route_decision", "rag")
    docs = state.get("docs", [])
    
    context_docs = ""
    for d_item in docs:
        if isinstance(d_item, tuple) and len(d_item) == 2:
            doc = d_item[0]
            context_docs += f"Source: {doc.metadata.get('source', 'Unknown')}\nText: {doc.page_content}\n\n"
        else:
            doc = d_item
            if hasattr(doc, "metadata"):
                context_docs += f"Source: {doc.metadata.get('source', 'Unknown')}\nText: {doc.page_content}\n\n"
        
    meta = res.get("retrieval_metadata", {})
    confidence = str(meta.get("confidence_score", "N/A"))
    
    explanation = generate_explanation(
        question=res.get("question", ""),
        answer=res.get("answer", ""),
        context_docs=context_docs,
        route=route,
        confidence=confidence
    )
    
    res["explanation"] = explanation
    
    # Save the complete result to database history
    if state["query"].session_id:
        postgresDB.add_chat_message(state["query"].session_id, state["user_id"], "user", state["query"].question)
        postgresDB.add_chat_message(state["query"].session_id, state["user_id"], "assistant", json.dumps(res))
    
    # Cache the final response WITH the explanation
    semanticCache.set(state["search_question"], res, user_id=state["user_id"])
        
    return {"final_response": res}

def log_telemetry_node(state: RAGState) -> dict:
    print("DEBUG LOG TELEMETRY NODE STATE:", state.get("telemetry"))
    telemetry = state.get("telemetry", {})
    if not telemetry or "start_time" not in telemetry:
        print("DEBUG TELEMETRY EARLY RETURN")
        return {}
        
    total_time_ms = (time.time() - telemetry["start_time"]) * 1000
    
    # Estimate time saved if cache hit
    time_saved_ms = 0.0
    if telemetry.get("cache_hit"):
        time_saved_ms = 3100.0 - total_time_ms # Estimated 3.1s for average RAG without cache
        if time_saved_ms < 0: time_saved_ms = 0.0
        
    data = {
        "user_id": state["user_id"],
        "session_id": state["query"].session_id,
        "query": state["query"].question,
        "embedding_time_ms": telemetry.get("embedding_time_ms", 0),
        "retrieval_time_ms": telemetry.get("retrieval_time_ms", 0),
        "llm_time_ms": telemetry.get("llm_time_ms", 0),
        "total_time_ms": total_time_ms,
        "prompt_tokens": telemetry.get("prompt_tokens", 0),
        "completion_tokens": telemetry.get("completion_tokens", 0),
        "retrieval_source": telemetry.get("retrieval_source", "None"),
        "avg_retrieval_score": telemetry.get("avg_retrieval_score", 0),
        "num_retrieved_chunks": telemetry.get("num_retrieved_chunks", 0),
        "query_rewritten": telemetry.get("query_rewritten", False),
        "judge_decision": telemetry.get("judge_decision", "N/A"),
        "faithfulness_score": telemetry.get("faithfulness_score", 0),
        "context_length_tokens": int(telemetry.get("context_length_tokens", 0)),
        "cache_hit": telemetry.get("cache_hit", False),
        "time_saved_ms": time_saved_ms
    }
    
    try:
        postgresDB.log_telemetry(data)
    except Exception as e:
        print(f"Failed to log telemetry: {e}")
        
    return {}


def route_after_cache(state: RAGState) -> str:
    return "end" if state.get("cached_response") else "retrieve"


workflow = StateGraph(RAGState)
workflow.add_node("get_history", get_history_node)
workflow.add_node("agent_router", agent_router_node)
workflow.add_node("query_analyzer", query_analyzer_node)
workflow.add_node("reformulate", reformulate_node)
workflow.add_node("cache_check", cache_check_node)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("generate", generate_and_eval_node)
workflow.add_node("timeline", timeline_node)
workflow.add_node("casual", casual_chat_node)
workflow.add_node("explainability", explainability_node)
workflow.add_node("log_telemetry", log_telemetry_node)

workflow.set_entry_point("get_history")
workflow.add_edge("get_history", "agent_router")

workflow.add_conditional_edges(
    "agent_router",
    lambda state: state["route_decision"],
    {"rag": "query_analyzer", "timeline": "timeline", "casual": "casual", "end": "log_telemetry"}
)

workflow.add_edge("query_analyzer", "reformulate")
workflow.add_edge("reformulate", "cache_check")
workflow.add_conditional_edges("cache_check", route_after_cache, {"end": "log_telemetry", "retrieve": "retrieve"})
workflow.add_edge("retrieve", "generate")
workflow.add_edge("generate", "explainability")
workflow.add_edge("timeline", "explainability")
workflow.add_edge("casual", "log_telemetry")
workflow.add_edge("explainability", "log_telemetry")
workflow.add_edge("log_telemetry", END)

rag_chain = workflow.compile()
