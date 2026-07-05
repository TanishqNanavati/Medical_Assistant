from langchain_qdrant import QdrantVectorStore

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams,Filter,FieldCondition,MatchValue

from config import settings
from services.embedder import embedder
from models.query import Query

class QdrantDB:
    MIN_SCORE = 0.25

    def __init__(self):
        self.client = QdrantClient(
            url=settings.qdrant_url
        )

        self.collection_name = settings.qdrant_collection

        self.create_collection()

        self.vector_store = QdrantVectorStore(
            client = self.client,
            collection_name=self.collection_name,
            embedding=embedder.model,
        )

    def create_collection(self):
        """
        Create a new collection if it doesn't exist.
        """

        collections = self.client.get_collections().collections

        collection_names = [c.name for c in collections]
        dimension = len(embedder.model.embed_query("hello"))

        if settings.qdrant_collection not in collection_names:
            self.client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=VectorParams(
                    size=dimension,
                    distance=Distance.COSINE,
                ),
            )
            print(f"Collection '{self.collection_name}' created.")

        # Semantic cache collection
        if settings.qdrant_cache_collection not in collection_names:
            self.client.create_collection(
                collection_name=settings.qdrant_cache_collection,
                vectors_config=VectorParams(
                    size=dimension,
                    distance=Distance.COSINE,
                ),
            )
            print(f"Cache Collection '{settings.qdrant_cache_collection}' created.")

    def add_documents(self, docs):
        self.vector_store.add_documents(documents=docs)

    def clear_data(self):
        """Delete collections and recreate them to apply new dimensions if needed."""
        self.client.delete_collection(collection_name=self.collection_name)
        self.client.delete_collection(collection_name=settings.qdrant_cache_collection)
        self.create_collection()

    def similarity_search(
        self, 
        query: Query, 
        k: int = 5,
        ):
        conditions = []
        

        if query.document_type :
            conditions.append(
                FieldCondition(
                    key="metadata.document_type",
                    match=MatchValue(value=query.document_type.value),
                )
            )

        if query.patient_id :
            conditions.append(
                FieldCondition(
                    key="metadata.patient_id",
                    match=MatchValue(value=query.patient_id),
                )
            )

        search_filter = None

        if conditions :
            search_filter = Filter(
                must=conditions,
            )


        return self.vector_store.similarity_search_with_score(
            query=query.question,
            k=k,
            filter=search_filter
        )
    

qdrantDB = QdrantDB()