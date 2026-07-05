import os
from dotenv import load_dotenv
from openai import OpenAI

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

                Answer only YES or NO.

                YES = context contains enough information.

                NO = retrieve again.
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

        answer = response.choices[0].message.content.strip().upper()

        return answer.startswith("YES")

retrievalJudge = RetrievalJudge()