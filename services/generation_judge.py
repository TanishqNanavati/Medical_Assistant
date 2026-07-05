import json
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

class GenerationJudge:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("GEMINI_API_KEY"),
            base_url=os.getenv("GEMINI_BASE_URL")
        )

    def evaluate(self,question:str,context:str,ans:str) -> dict:
        prompt = f"""
        
        You are a strict medical evaluator grading an AI assistant's answer.

        Question:{question}

        Provided Context : {context}

        Generated Answer : {ans}

        Task:
        1. Ensure the Generated Answer relies STRICTLY on the Provided Context.
        2. Ensure there are no hallucinations (facts not present in the context).
        3. Ensure the answer addresses the Question.
        4. Give a faithfulness score based on how well the answer is supported by the context on a scale of 0.0 to 1.0.
        5. If the answer is irrelevant or not supported by the context, return faithfulness as 0.0.

        Return only valid JSON.

        {{
            "decision": "PASS",
            "faithfulness": 0.95,
            "feedback": "The answer is perfectly grounded in the context."
        }}
        
        Example Fail:
        {{
            "decision": "FAIL",
            "faithfulness": 0.3,
            "feedback": "The answer mentions asthma, which is not in the context."
        }}
        
        """

        response = self.client.chat.completions.create(
            model=os.getenv("GEMINI_MODEL"),
            messages=[
                {
                    "role":"user",
                    "content":prompt,
                },
            ],
            temperature=0,
        )

        eval_answer = response.choices[0].message.content.strip()

        if eval_answer.startswith("```json"):
            eval_answer = eval_answer[7:]
        elif eval_answer.startswith("```"):
            eval_answer = eval_answer[3:]
        
        if eval_answer.endswith("```"):
            eval_answer = eval_answer[:-3]
            
        eval_answer = eval_answer.strip()

        return json.loads(eval_answer)

generationJudge = GenerationJudge()