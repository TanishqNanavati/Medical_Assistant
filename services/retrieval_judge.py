import os
from dotenv import load_dotenv
from openai import OpenAI
import json

load_dotenv()

class RetrievalJudge:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("GEMINI_API_KEY"),
            base_url=os.getenv("GEMINI_BASE_URL"),
        )

    def judge(self,question,docs):
        context = "\n\n".join(
            doc.page_content[:400]
            for doc,_ in docs
        )

        prompt = f"""
                You are evaluating retrieval quality.

                Question:
                {question}

                Retrieved Context:
                {context}

               Return ONLY valid JSON.

                Example:

                {{
                "decision":"YES",
                "reason":"The retrieved context answers the question.",
                "improved_query":""
                }}

                or

                {{
                "decision":"RETRY",
                "reason":"Retrieved chunks are about lab values instead of patient history.",
                "improved_query":"Previous medical history and chronic illnesses"
                }}

                If the uploaded documents clearly cannot answer:

                {{
                "decision":"FAIL",
                "reason":"The answer is not present in the uploaded documents.",
                "improved_query":""
                }}
                """

        response = self.client.chat.completions.create(
            model = os.getenv("GEMINI_MODEL"),
            messages=[
                {
                    "role":"user",
                    "content":prompt,
                },
            ],
            temperature=0,
        )

        answer = response.choices[0].message.content.strip()

        if answer.startswith("```json"):
            answer = answer[7:]
        elif answer.startswith("```"):
            answer = answer[3:]
        
        if answer.endswith("```"):
            answer = answer[:-3]
            
        answer = answer.strip()

        return json.loads(answer)

retrievalJudge = RetrievalJudge()