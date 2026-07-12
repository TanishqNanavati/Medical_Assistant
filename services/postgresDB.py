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

postgresDB = PostgresDB()