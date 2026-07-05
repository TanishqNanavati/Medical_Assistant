from langchain_huggingface import HuggingFaceEmbeddings

from config import settings

class Embedder:
    def __init__(self):
        print(f"Loading embedding model: {settings.embedding_model}")

        self.model = HuggingFaceEmbeddings(
            model_name=settings.embedding_model,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )


embedder = Embedder()