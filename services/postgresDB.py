import os
import psycopg2
from psycopg2.extras import RealDictCursor
from models.document_type import DocumentType
from models.query import Query

from dotenv import load_dotenv

load_dotenv()

class PostgresDB:
    def __init__(self):
        self.conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST"),
            port=os.getenv("POSTGRES_PORT"),
            database=os.getenv("POSTGRES_DB"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
        )

        self.create_table()

    def create_table(self):
        with self.conn.cursor() as cur:

            cur.execute("""
            CREATE TABLE IF NOT EXISTS users(
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL
            );
            """)


            cur.execute("""
            CREATE TABLE IF NOT EXISTS chunks(
                id SERIAL PRIMARY KEY,
                content TEXT,
                page INTEGER,
                source TEXT,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                document_type TEXT,
                tsv tsvector
            );
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS documents(
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                filename TEXT NOT NULL,
                document_type TEXT,
                summary TEXT,
                upload_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                tsv tsvector
            );
            """)

            cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunks_tsv
            ON chunks
            USING GIN(tsv);
            """)

            cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_documents_tsv
            ON documents
            USING GIN(tsv);
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS chat_sessions(
                session_id TEXT PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages(
                id SERIAL PRIMARY KEY,
                session_id TEXT REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS telemetry_logs(
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                session_id TEXT,
                query TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                embedding_time_ms FLOAT,
                retrieval_time_ms FLOAT,
                llm_time_ms FLOAT,
                total_time_ms FLOAT,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                retrieval_source TEXT,
                avg_retrieval_score FLOAT,
                num_retrieved_chunks INTEGER,
                query_rewritten BOOLEAN,
                judge_decision TEXT,
                faithfulness_score FLOAT,
                context_length_tokens INTEGER,
                cache_hit BOOLEAN,
                time_saved_ms FLOAT
            );
            """)

            self.conn.commit()

    def get_user_by_username(self,username:str):
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE username=%s",(username,))
            return cur.fetchone()

    def create_user(self,username:str,hashed_password:str):
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("INSERT INTO users (username, hashed_password) VALUES (%s, %s) RETURNING id, username",(username,hashed_password))
            self.conn.commit()
            return cur.fetchone()

    def add_documents(self,docs):
        with self.conn.cursor() as cur:
            for doc in docs:
                cur.execute(
                    """
                    INSERT INTO chunks
                    (
                        content,
                        page,
                        source,
                        user_id,
                        document_type,
                        tsv
                    )

                    VALUES
                    (
                        %s,%s,%s,%s,%s,
                        to_tsvector('english', %s)
                    )
                    """,
                    (
                        doc.page_content,
                        doc.metadata["page"],
                        doc.metadata["source"],
                        doc.metadata["user_id"],
                        doc.metadata["document_type"],
                        doc.page_content,
                    ),
                )

            self.conn.commit()

    def clear_data(self):
        """Delete all chunks, documents, and users from Postgres and reset identity."""
        with self.conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE chunks, documents, users RESTART IDENTITY CASCADE;")
            self.conn.commit()

    def add_document(self, user_id: int, filename: str, document_type: str, summary: str):
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents (user_id, filename, document_type, summary, tsv)
                VALUES (%s, %s, %s, %s, setweight(to_tsvector('english', coalesce(%s, '')), 'A') || setweight(to_tsvector('english', coalesce(%s, '')), 'B'))
                """,
                (user_id, filename, document_type, summary, filename, summary)
            )
            self.conn.commit()

    def get_candidate_documents(self, user_id: int, query: str):
        """Returns the top 10 most recent docs + top 10 BM25 matched docs for the user."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get 10 most recent
            cur.execute(
                """
                SELECT filename, summary, upload_timestamp 
                FROM documents 
                WHERE user_id = %s 
                ORDER BY upload_timestamp DESC 
                LIMIT 10
                """, 
                (user_id,)
            )
            recent_docs = cur.fetchall()

            # Get BM25 matched docs
            import re
            words = re.findall(r'\w+', query)
            matched_docs = []
            if words:
                or_query = " | ".join(words)
                cur.execute(
                    """
                    SELECT filename, summary, upload_timestamp
                    FROM documents
                    WHERE user_id = %s AND tsv @@ to_tsquery('english', %s)
                    ORDER BY ts_rank(tsv, to_tsquery('english', %s)) DESC
                    LIMIT 10
                    """,
                    (user_id, or_query, or_query)
                )
                matched_docs = cur.fetchall()

            # Combine and deduplicate
            all_candidates = {doc["filename"]: doc for doc in recent_docs + matched_docs}
            return list(all_candidates.values())

    def bm25_search(
        self,
        query:Query,
        user_id:int,
        limit=5,
        target_sources: list = None
    ):
        import re
        # Convert "What is condition?" into "What | is | condition" for a BM25 OR search
        words = re.findall(r'\w+', query.question)
        if not words:
            return []
            
        or_query = " | ".join(words)
        
        sql = """
        SELECT *,
               ts_rank(
                    tsv,
                    to_tsquery('english', %s)
               ) AS score
        FROM chunks
        WHERE
            user_id=%s
            AND tsv @@ to_tsquery('english', %s)
        """
        params = [or_query, user_id, or_query]
        
        if query.document_type:
            sql += " AND document_type=%s"
            params.append(query.document_type.value)

        if target_sources:
            sql += " AND source = ANY(%s)"
            params.append(target_sources)

        sql += " ORDER BY score DESC LIMIT %s"
        params.append(limit)

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, tuple(params))
            return cur.fetchall()

    # --- Chat Session Management ---
    
    def enforce_session_limits(self, user_id: int):
        with self.conn.cursor() as cur:
            # 1. Delete sessions older than 30 days
            cur.execute("DELETE FROM chat_sessions WHERE user_id = %s AND created_at < NOW() - INTERVAL '30 days'", (user_id,))
            
            # 2. Enforce max 20 sessions per user
            cur.execute("SELECT session_id FROM chat_sessions WHERE user_id = %s ORDER BY created_at DESC OFFSET 20", (user_id,))
            old_sessions = cur.fetchall()
            if old_sessions:
                old_ids = [row[0] for row in old_sessions]
                cur.execute("DELETE FROM chat_sessions WHERE session_id = ANY(%s)", (old_ids,))
            
            self.conn.commit()

    def create_chat_session(self, user_id: int, session_id: str, title: str):
        self.enforce_session_limits(user_id)
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_sessions (session_id, user_id, title) 
                VALUES (%s, %s, %s)
                ON CONFLICT (session_id) DO NOTHING
                """,
                (session_id, user_id, title)
            )
            self.conn.commit()

    def get_chat_sessions(self, user_id: int):
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT session_id, title, created_at, updated_at FROM chat_sessions WHERE user_id = %s ORDER BY updated_at DESC", (user_id,))
            return cur.fetchall()

    def get_chat_history(self, session_id: str, user_id: int):
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # First verify the session belongs to the user
            cur.execute("SELECT session_id FROM chat_sessions WHERE session_id = %s AND user_id = %s", (session_id, user_id))
            if not cur.fetchone():
                return []
                
            cur.execute(
                "SELECT role, content FROM chat_messages WHERE session_id = %s ORDER BY created_at ASC",
                (session_id,)
            )
            return cur.fetchall()

    def get_user_statistics(self, user_id: int):
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            stats = {}
            
            # Total documents
            cur.execute("SELECT COUNT(*) as count FROM documents WHERE user_id = %s", (user_id,))
            stats["total_documents"] = cur.fetchone()["count"]
            
            # Total chunks
            cur.execute("SELECT COUNT(*) as count FROM chunks WHERE user_id = %s", (user_id,))
            stats["total_chunks"] = cur.fetchone()["count"]
            
            # Total chat sessions
            cur.execute("SELECT COUNT(*) as count FROM chat_sessions WHERE user_id = %s", (user_id,))
            stats["total_sessions"] = cur.fetchone()["count"]
            
            # Total chat messages
            cur.execute("""
                SELECT COUNT(*) as count 
                FROM chat_messages cm 
                JOIN chat_sessions cs ON cm.session_id = cs.session_id 
                WHERE cs.user_id = %s
            """, (user_id,))
            stats["total_messages"] = cur.fetchone()["count"]
            
            # Documents by type
            cur.execute("""
                SELECT document_type, COUNT(*) as count 
                FROM documents 
                WHERE user_id = %s 
                GROUP BY document_type
            """, (user_id,))
            stats["documents_by_type"] = cur.fetchall()
            
            # Most recent activity (from documents or sessions)
            cur.execute("""
                SELECT MAX(updated_at) as last_activity
                FROM (
                    SELECT upload_timestamp as updated_at FROM documents WHERE user_id = %s
                    UNION ALL
                    SELECT updated_at FROM chat_sessions WHERE user_id = %s
                ) as combined
            """, (user_id, user_id))
            last_activity = cur.fetchone()["last_activity"]
            stats["last_activity"] = last_activity.isoformat() if last_activity else None
            
            # --- TELEMETRY / ANALYTICS ---
            # Total queries over time
            cur.execute("SELECT COUNT(*) as count FROM telemetry_logs WHERE user_id = %s", (user_id,))
            stats["total_queries"] = cur.fetchone()["count"]
            
            cur.execute("SELECT COUNT(*) as count FROM telemetry_logs WHERE user_id = %s AND timestamp >= CURRENT_DATE", (user_id,))
            stats["queries_today"] = cur.fetchone()["count"]
            
            cur.execute("SELECT COUNT(*) as count FROM telemetry_logs WHERE user_id = %s AND timestamp >= CURRENT_DATE - INTERVAL '7 days'", (user_id,))
            stats["queries_this_week"] = cur.fetchone()["count"]
            
            # Token Usage (Total)
            cur.execute("""
                SELECT SUM(prompt_tokens) as prompt, SUM(completion_tokens) as completion 
                FROM telemetry_logs WHERE user_id = %s
            """, (user_id,))
            tokens = cur.fetchone()
            stats["tokens_prompt"] = tokens["prompt"] or 0
            stats["tokens_completion"] = tokens["completion"] or 0
            
            # Token Usage (Today)
            cur.execute("""
                SELECT SUM(prompt_tokens) as prompt, SUM(completion_tokens) as completion 
                FROM telemetry_logs WHERE user_id = %s AND timestamp >= CURRENT_DATE
            """, (user_id,))
            tokens_today = cur.fetchone()
            stats["tokens_prompt_today"] = tokens_today["prompt"] or 0
            stats["tokens_completion_today"] = tokens_today["completion"] or 0
            
            # Averages
            cur.execute("""
                SELECT 
                    AVG(embedding_time_ms) as avg_emb,
                    AVG(retrieval_time_ms) as avg_ret,
                    AVG(llm_time_ms) as avg_llm,
                    AVG(total_time_ms) as avg_tot,
                    AVG(avg_retrieval_score) as avg_score,
                    AVG(faithfulness_score) as avg_faith,
                    AVG(context_length_tokens) as avg_ctx,
                    AVG(completion_tokens) as avg_out
                FROM telemetry_logs WHERE user_id = %s
            """, (user_id,))
            avgs = cur.fetchone()
            stats["avg_embedding_ms"] = avgs["avg_emb"] or 0
            stats["avg_retrieval_ms"] = avgs["avg_ret"] or 0
            stats["avg_llm_ms"] = avgs["avg_llm"] or 0
            stats["avg_total_ms"] = avgs["avg_tot"] or 0
            stats["avg_retrieval_score"] = avgs["avg_score"] or 0
            stats["avg_faithfulness"] = avgs["avg_faith"] or 0
            stats["avg_context_length"] = avgs["avg_ctx"] or 0
            stats["avg_output_tokens"] = avgs["avg_out"] or 0
            
            # Distribution of Retrieval Sources
            cur.execute("SELECT retrieval_source, COUNT(*) as count FROM telemetry_logs WHERE user_id = %s AND retrieval_source IS NOT NULL GROUP BY retrieval_source", (user_id,))
            stats["source_distribution"] = cur.fetchall()
            
            # Retrieved Chunks Histogram
            cur.execute("SELECT num_retrieved_chunks, COUNT(*) as count FROM telemetry_logs WHERE user_id = %s AND num_retrieved_chunks IS NOT NULL GROUP BY num_retrieved_chunks", (user_id,))
            stats["chunks_distribution"] = cur.fetchall()
            
            # Rewrite success
            cur.execute("""
                SELECT 
                    COUNT(CASE WHEN query_rewritten = TRUE THEN 1 END) as rewritten,
                    COUNT(CASE WHEN query_rewritten = FALSE THEN 1 END) as original
                FROM telemetry_logs WHERE user_id = %s AND query_rewritten IS NOT NULL
            """, (user_id,))
            rewrite = cur.fetchone()
            stats["rewrite_stats"] = {"rewritten": rewrite["rewritten"] or 0, "original": rewrite["original"] or 0}
            
            # Judge Decisions
            cur.execute("SELECT judge_decision, COUNT(*) as count FROM telemetry_logs WHERE user_id = %s AND judge_decision IS NOT NULL GROUP BY judge_decision", (user_id,))
            stats["judge_distribution"] = cur.fetchall()
            
            # Extremes
            cur.execute("SELECT MAX(completion_tokens) as mx, MIN(completion_tokens) as mn FROM telemetry_logs WHERE user_id = %s AND completion_tokens > 0", (user_id,))
            ext = cur.fetchone()
            stats["max_output_tokens"] = ext["mx"] or 0
            stats["min_output_tokens"] = ext["mn"] or 0
            
            # Semantic Cache
            cur.execute("""
                SELECT 
                    COUNT(CASE WHEN cache_hit = TRUE THEN 1 END) as hits,
                    COUNT(CASE WHEN cache_hit = FALSE THEN 1 END) as misses,
                    SUM(time_saved_ms) as total_time_saved
                FROM telemetry_logs WHERE user_id = %s AND cache_hit IS NOT NULL
            """, (user_id,))
            cache = cur.fetchone()
            stats["cache_hits"] = cache["hits"] or 0
            stats["cache_misses"] = cache["misses"] or 0
            stats["time_saved_ms"] = cache["total_time_saved"] or 0
            
            return stats

    def log_telemetry(self, data: dict):
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO telemetry_logs (
                    user_id, session_id, query, embedding_time_ms, retrieval_time_ms, 
                    llm_time_ms, total_time_ms, prompt_tokens, completion_tokens, 
                    retrieval_source, avg_retrieval_score, num_retrieved_chunks, 
                    query_rewritten, judge_decision, faithfulness_score, 
                    context_length_tokens, cache_hit, time_saved_ms
                ) VALUES (
                    %(user_id)s, %(session_id)s, %(query)s, %(embedding_time_ms)s, %(retrieval_time_ms)s, 
                    %(llm_time_ms)s, %(total_time_ms)s, %(prompt_tokens)s, %(completion_tokens)s, 
                    %(retrieval_source)s, %(avg_retrieval_score)s, %(num_retrieved_chunks)s, 
                    %(query_rewritten)s, %(judge_decision)s, %(faithfulness_score)s, 
                    %(context_length_tokens)s, %(cache_hit)s, %(time_saved_ms)s
                )
            """, data)
            self.conn.commit()

    def add_chat_message(self, session_id: str, user_id: int, role: str, content: str):
        with self.conn.cursor() as cur:
            # Verify ownership
            cur.execute("SELECT 1 FROM chat_sessions WHERE session_id = %s AND user_id = %s", (session_id, user_id))
            if not cur.fetchone():
                return
            
            cur.execute("INSERT INTO chat_messages (session_id, role, content) VALUES (%s, %s, %s)", (session_id, role, content))
            cur.execute("UPDATE chat_sessions SET updated_at = CURRENT_TIMESTAMP WHERE session_id = %s", (session_id,))
            self.conn.commit()

    def rename_chat_session(self, session_id: str, user_id: int, new_title: str):
        with self.conn.cursor() as cur:
            cur.execute("UPDATE chat_sessions SET title = %s, updated_at = CURRENT_TIMESTAMP WHERE session_id = %s AND user_id = %s", (new_title, session_id, user_id))
            self.conn.commit()

postgresDB = PostgresDB()