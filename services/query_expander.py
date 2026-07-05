from openai import OpenAI
from dotenv import load_dotenv
import os
load_dotenv()

class QueryExpander:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("GEMINI_API_KEY"),
            base_url=os.getenv("GEMINI_BASE_URL"),
        )

    def expand(self,question:str):
        prompt = f"""
                Generate 3 alternative search queries for the following medical question.

                Rules:
                - Preserve the meaning.
                - Use medical terminology.
                - Keep each query short.
                - Return ONLY one query per line.

                Question:
                {question}
                """

        response = self.client.chat.completions.create(
            model=os.getenv("GEMINI_MODEL"),
            messages=[
                {"role":"user","content":prompt},
            ],
        )

        queries = [
            line.strip()
            for line in response.choices[0].message.content.splitlines()
            if line.strip()
        ]


        return [question] + queries[:3]

queryExpander = QueryExpander()


