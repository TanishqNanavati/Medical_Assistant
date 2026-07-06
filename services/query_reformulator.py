from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

class QueryReformulator:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("GEMINI_API_KEY"),
            base_url=os.getenv("GEMINI_BASE_URL")
        )

        self.model = os.getenv("GEMINI_MODEL")

    def reformulate(self,curr_question:str,history:list) -> str:
        if not history:
            return curr_question

        history_str = ""
        for msg in history:
            role = "User" if msg["role"] == "user" else "Assistant"
            history_str += f"{role}: {msg['content']}\n"

        prompt = f"""
            Given the following conversation history and the user's current question, your task is to reformulate the current question into a standalone, highly specific query that can be used for semantic search in a vector database.
            CRITICAL RULES:
            1. FIRST, analyze if the current question is related to the conversation history (e.g., uses pronouns like "it", "they", or asks a direct follow-up question).
            2. If the current question IS related, rewrite it to include all necessary medical context from the history. 
            3. If the current question is NOT related (a completely new medical topic), return the current question exactly as it is, without adding any history context.
            4. Output ONLY the reformulated question. Do not include any explanations, prefixes, or conversational text.
            Conversation History:
            {history_str}
            Current Question: {curr_question}
            Reformulated Question:
            """

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role":"user", "content": prompt}],
            temperature=0.0
        )

        return response.choices[0].message.content.strip()

queryReformulator = QueryReformulator()
    