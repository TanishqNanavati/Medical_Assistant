# from langchain_huggingface import HuggingFaceEmbeddings

# from config import settings

# class Embedder:
#     def __init__(self):
#         print(f"Loading embedding model: {settings.embedding_model}")

#         self.model = HuggingFaceEmbeddings(
#             model_name=settings.embedding_model,
#             model_kwargs={"device": "cpu"},
#             encode_kwargs={"normalize_embeddings": True},
#         )


# embedder = Embedder()


from langchain_google_genai import GoogleGenerativeAIEmbeddings
from config import settings
from sentence_transformers import util

class Embedder:
    def __init__(self):
        print(f"Loading embedding model: {settings.embedding_model}")

        self.model = GoogleGenerativeAIEmbeddings(
            model=settings.embedding_model,
            google_api_key=settings.gemini_api_key,
        )


embedder = Embedder()

emb1 = embedder.model.embed_query("What was the final diagnosis for the patient?")
emb2 = embedder.model.embed_query("Can you list all the medical conditions the patient was diagnosed with at discharge?")
cos_sim = util.cos_sim(emb1, emb2)
print(f"Similarity with Google Embeddings: {cos_sim.item()}")

