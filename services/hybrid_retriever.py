import os
from copy import deepcopy
from dotenv import load_dotenv
import json
from langchain_core.documents import Document
from sentence_transformers import CrossEncoder

from services.qdrantDB import qdrantDB
from services.postgresDB import postgresDB
from services.query_expander import queryExpander
from services.retrieval_judge import retrievalJudge

from config import settings
load_dotenv()


class HybridRetriever:

    def __init__(self):
        self.cross_encoder = CrossEncoder(
            os.getenv("RERANK_MODEL")
        )

    def reciprocal_rank_fusion(self, dense, sparse, k=20):

        scores = {}
        documents = {}

        # Dense
        for rank, (doc, _) in enumerate(dense):

            key = (
                doc.page_content,
                doc.metadata["page"],
            )

            doc.metadata["retrieved_from"] = "Dense (Qdrant)"

            documents[key] = doc

            scores[key] = scores.get(key, 0) + 1 / (k + rank + 1)

        # Sparse
        for rank, row in enumerate(sparse):

            doc = Document(
                page_content=row["content"],
                metadata={
                    "page": row["page"],
                    "source": row["source"],
                    "user_id":row["user_id"],
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

        return [
            (documents[key], score)
            for key, score in ranked
        ]


    def retrieve(self,query,user_id,rrf_k=20,expand=True, target_sources=None):

        if expand:
            expanded_queries = queryExpander.expand(query.question)

            print("\nExpanded Queries")

            for q in expanded_queries:
                print("-", q)

        else:

            expanded_queries = [query.question]

            print("\nUsing rewritten query")
            print("-", query.question)

        print("=" * 60)

        dense_all = []
        sparse_all = []

        for q in expanded_queries:

            new_query = deepcopy(query)
            new_query.question = q

            dense = qdrantDB.similarity_search(
                query=new_query,
                user_id=user_id,
                k=rrf_k,
                target_sources=target_sources
            )

            sparse = postgresDB.bm25_search(
                query=new_query,
                user_id=user_id,
                limit=rrf_k,
                target_sources=target_sources
            )

            dense_all.extend(dense)
            sparse_all.extend(sparse)

        rrf = self.reciprocal_rank_fusion(
            dense_all,
            sparse_all,
        )

        seen = set()
        unique = []

        for doc, score in rrf:

            key = (
                doc.page_content,
                doc.metadata["page"],
            )

            if key not in seen:
                seen.add(key)
                unique.append((doc, score))

        return unique[:rrf_k]


    def rerank(self,query,docs,k):

        if not docs:
            return []

        pairs = [
            [query.question, doc.page_content]
            for doc, _ in docs
        ]

        scores = self.cross_encoder.predict(pairs)

        reranked = []

        for (doc, _), score in zip(docs, scores):

            reranked.append(
                (
                    doc,
                    float(score),
                )
            )

        reranked.sort(
            key=lambda x: x[1],
            reverse=True,
        )

        return reranked[:k]

    def search(self, query,user_id, k=5, target_sources=None):

        retrieval_sizes = [20, 40, 60]
        expand = True
        retrieval_history = []
        max_rounds = min(settings.max_rag_rounds, len(retrieval_sizes))

        for round_idx in range(max_rounds):

            retrieval_size = retrieval_sizes[round_idx]
            print(f"\nRetrieving Top-{retrieval_size}")

            docs = self.retrieve(
                query=query,
                user_id=user_id,
                rrf_k=retrieval_size,
                expand=expand,
                target_sources=target_sources
            )

            if not docs:
                return {
                    "docs": [], 
                    "metadata": {
                        "rounds": round_idx + 1, 
                        "final_query": query.question, 
                        "decision": "FAIL", 
                        "confidence_score": 0.0, 
                        "history": retrieval_history
                    }
                }

            reranked = self.rerank(
                query=query,
                docs=docs,
                k=15,
            )

            print("\nCrossEncoder Scores")

            for _, score in reranked:
                print(score)

            confidence_score = max([score for _, score in reranked]) if reranked else 0.0

            print("\nJudging Retrieval...")

            judge = retrievalJudge.judge(
                question=query.question,
                docs=reranked,
            )

            print("\nDecision :", judge["decision"])
            print("Reason   :", judge["reason"])

            decision = judge["decision"].upper()
            
            retrieval_history.append({
                "query": query.question,
                "decision": decision,
                "reason": judge["reason"],
                "size": retrieval_size
            })

            # accept
            if decision == "YES":

                print("\nJudge accepted retrieval.")

                return {
                    "docs": reranked[:k],
                    "metadata": {
                        "rounds": round_idx + 1,
                        "final_query": query.question,
                        "decision": decision,
                        "confidence_score": float(confidence_score),
                        "history": retrieval_history
                    }
                }

            # fail
            if decision == "FAIL":

                print("\nJudge says answer cannot be found.")

                return {
                    "docs": [],
                    "metadata": {
                        "rounds": round_idx + 1,
                        "final_query": query.question,
                        "decision": decision,
                        "confidence_score": float(confidence_score),
                        "history": retrieval_history
                    }
                }

            # retry
            improved_query = judge.get("improved_query", "").strip()

            if improved_query:

                print("\nImproved Query")

                print(improved_query)

                query = deepcopy(query)
                query.question = improved_query

            expand = True
            print("\nRetrying Retrieval...\n")

        print("\nMax RAG rounds reached. Returning best available documents.")
        return {
            "docs": reranked[:k],
            "metadata": {
                "rounds": max_rounds,
                "final_query": query.question,
                "decision": "MAX_RETRIES",
                "confidence_score": float(confidence_score),
                "history": retrieval_history
            }
        }


hybridRetriever = HybridRetriever()