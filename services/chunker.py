from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents.base import Document

class Chunker:
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
             chunk_overlap=200
        )

    def chunk(self,docs:list[Document]) -> list[Document]:
        return self.text_splitter.split_documents(docs)


chunker = Chunker()



