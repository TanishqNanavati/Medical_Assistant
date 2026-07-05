import os
from copy import deepcopy
from dotenv import load_dotenv
from langchain_core.documents import Document
from sentence_transformers import CrossEncoder
from services.qdrantDB import qdrantDB
from services.postgresDB import postgresDB
from services.query_expander import queryExpander
load_dotenv()

class HybridRetriever:
    def __init__(self):
        model_name = os.getenv("RERANK_MODEL")
        self.cross_encoder = CrossEncoder(model_name)


    def reciprocal_rank_fusion(self,dense,sparse,k=20):
        scores={}
        documents={}
        for rank,(doc,_) in enumerate(dense):
            key=(
                doc.page_content,
                doc.metadata["page"]
            )
            
            doc.metadata["retrieved_from"] = "Dense (Qdrant)"
            documents[key] = doc
            scores[key] = scores.get(key,0) + 1/(k+rank+1)

        for rank,row in enumerate(sparse):
            doc = Document(
                page_content=row["content"],
                metadata={
                    "page": row["page"],
                    "source": row["source"],
                    "patient_id": row["patient_id"],
                    "report_id": row["report_id"],
                    "document_type": row["document_type"],
                },
            )

            key = (
                doc.page_content,
                doc.metadata["page"],
            )

            if key in documents:
                documents[key].metadata["retrieved_from"] = "Both (Dense & BM25)"
            else:
                doc.metadata["retrieved_from"] = "Sparse (BM25)"
                documents[key] = doc

            scores[key] = scores.get(key, 0) + 1 / (k + rank + 1)

        ranked = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        result = []

        for key,score in ranked:
            result.append((documents[key],score)) # inserting tuple

        return result

    def search(self,query,k=5,rrf_k=20):
        # We must pass the string (query.question), not the entire Pydantic Query object!
        expanded_queries = queryExpander.expand(query.question)

        print("Expanded queries : \n")
        for q in expanded_queries:
            print("-",q)
        print("\n" + "="*50)

        dense_all = []
        sparse_all = []

        for q in expanded_queries:

            new_query = deepcopy(query)
            new_query.question = q

            dense = qdrantDB.similarity_search(
                query=new_query,
                k=rrf_k
            )

            sparse = postgresDB.bm25_search(
                query=new_query,
                limit=rrf_k
            )

            dense_all.extend(dense)
            sparse_all.extend(sparse)

        rrf = self.reciprocal_rank_fusion(  #reciprocal rank fusion
            dense_all,
            sparse_all,
        )

        if not rrf:
            return []

        unique_docs = []
        seen = set()

        for doc,score in rrf:
            key = (
                doc.page_content,
                doc.metadata.get("page"),
            )

            if key not in seen:
                seen.add(key)
                unique_docs.append((doc,score))

        top_k = unique_docs[:rrf_k]

        pairs = [[query.question,doc.page_content] for doc,_ in top_k]

        cross_encoder_scores = self.cross_encoder.predict(pairs)
        

        reranked_results = []

        for i,score in enumerate(cross_encoder_scores):
            doc = top_k[i][0]
            reranked_results.append((doc,float(score)))

        reranked_results = sorted(reranked_results, key=lambda x: x[1], reverse=True)

        return reranked_results[:k]

hybridRetriever = HybridRetriever()