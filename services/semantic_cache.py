import redis
import json
import uuid
from qdrant_client.models import PointStruct,Filter,FieldCondition,MatchValue
from config import settings
from services.qdrantDB import qdrantDB
from services.embedder import embedder

class SemanticCache:
    def __init__(self):
        self.redis_client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True
        )

    def get(self,question:str,user_id:int):
        print("Checking semantic cache ...\n")

        # creating embeddings of incoming collection
        query_vector = embedder.model.embed_query(question)

        search_filter = Filter(
            must=[FieldCondition(key="user_id",match=MatchValue(value=user_id))]
        )

        # searching through qdrant collection for past similar question (similar embeddings)
        query_response = qdrantDB.client.query_points(
            collection_name=settings.qdrant_cache_collection,
            query=query_vector,
            query_filter=search_filter,
            limit=1
        )
        results = query_response.points

        if not results:
            return None

        best_match = results[0]

        if best_match.score >= settings.semantic_cache_threshold:
            print(f"Cache Hit! Similarity: {best_match.score:.4f}")
            cache_id = best_match.payload.get("cache_id")

            # fetching cached response from redis

            cached_data = self.redis_client.get(cache_id)
            if cached_data:
                parsed_data = json.loads(cached_data)
                if "retrieval_metadata" not in parsed_data:
                    parsed_data["retrieval_metadata"] = {}
                parsed_data["retrieval_metadata"]["cached"] = True
                parsed_data["retrieval_metadata"]["similarity_score"] = best_match.score
                return parsed_data

            else:
                print("Cache ID expired in Redis.")

        print("Cache Miss!")
        return None

    def set(self,question:str,payload:dict,user_id:int):
        cache_id = str(uuid.uuid4()) # For generating unique id

        query_vector = embedder.model.embed_query(question)

        point = PointStruct(
            id=cache_id,
            vector=query_vector,
            payload={"cache_id":cache_id,"original_question":question,"user_id":user_id}
        )
        qdrantDB.client.upsert(
            collection_name=settings.qdrant_cache_collection,
            points=[point]
        )

        self.redis_client.setex(
            name=cache_id,
            time=settings.cache_ttl_seconds,
            value=json.dumps(payload)
        )

        print(f"Cache stored with ID : {cache_id}\n")

    def clear(self):
        """Clear all semantic cache entries from Redis."""
        self.redis_client.flushdb()


semanticCache = SemanticCache()