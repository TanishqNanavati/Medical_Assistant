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
                user_id INTEGER REFERENCES users(id),
                document_type TEXT,
                tsv tsvector
            );
            """)

            cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunks_tsv
            ON chunks
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
        """Delete all chunks,user from Postgres and reset identity."""
        with self.conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE chunks,users RESTART IDENTITY CASCADE;")
            self.conn.commit()

    def bm25_search(
        self,
        query:Query,
        user_id:int,
        limit=5,
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
            AND document_type=%s
            AND tsv @@ to_tsquery('english', %s)
        ORDER BY score DESC
        LIMIT %s
        """

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:

            cur.execute(
                sql,
                (
                    or_query,
                    user_id,
                    query.document_type.value,
                    or_query,
                    limit,
                ),
            )

            return cur.fetchall()

postgresDB = PostgresDB()