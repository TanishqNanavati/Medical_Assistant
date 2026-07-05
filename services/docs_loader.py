from pathlib import Path
from langchain_community.document_loaders import PyPDFLoader


class DocumentLoader:
    def load(self, file_path: str | Path):
        """
        Load a PDF and return a list of LangChain Documents.
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"{file_path} does not exist.")

        loader = PyPDFLoader(str(file_path))
        return loader.load()


doc_loader = DocumentLoader()


