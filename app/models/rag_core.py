import os
import re
import fitz  # PyMuPDF
from typing import List, Dict, Any, Optional
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

CHROMA_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "chromadb")

class RAGCore:
    """Class to handle PDF parsing, text splitting, embedding creation, and semantic retrieval."""
    
    def __init__(self):
        # Initialize the embedding model. This will download the model locally on first run.
        # Use CPU by default. We can specify device="cpu" or "mps" if on mac (sentence-transformers handles it).
        self.embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'}
        )
        
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract raw text from a PDF resume. Includes basic error handling for empty/unreadable PDFs."""
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found at {pdf_path}")
            
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
            
        doc.close()
        
        # Clean text
        cleaned_text = self.clean_text(text)
        
        if not cleaned_text or len(cleaned_text.strip()) < 50:
            raise ValueError(
                "Extracted text is empty or too short. The PDF might be scanned, image-heavy, "
                "or corrupted. Please upload a machine-readable text PDF."
            )
            
        return cleaned_text

    def extract_text(self, file_path: str) -> str:
        """Route parsing based on file extension (PDF, DOCX, TXT)."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found at {file_path}")
            
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            return self.extract_text_from_pdf(file_path)
        elif ext == ".docx":
            return self.extract_text_from_docx(file_path)
        elif ext in [".txt", ".md"]:
            return self.extract_text_from_txt(file_path)
        else:
            raise ValueError(f"Unsupported file format: {ext}. Only PDF, DOCX, and TXT are supported.")

    def extract_text_from_docx(self, docx_path: str) -> str:
        """Extract text from a DOCX file using built-in zipfile parser to avoid external dependencies."""
        import zipfile
        import xml.etree.ElementTree as ET
        
        try:
            with zipfile.ZipFile(docx_path) as docx:
                tree = ET.fromstring(docx.read('word/document.xml'))
                paragraphs = []
                for paragraph in tree.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
                    texts = [node.text for node in paragraph.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t') if node.text]
                    if texts:
                        paragraphs.append(''.join(texts))
                text = '\n'.join(paragraphs)
        except Exception as e:
            raise ValueError(f"Failed to read DOCX file: {str(e)}")
            
        cleaned_text = self.clean_text(text)
        if not cleaned_text or len(cleaned_text.strip()) < 50:
            raise ValueError("Extracted DOCX text is empty or too short. Please upload a valid document.")
            
        return cleaned_text

    def extract_text_from_txt(self, txt_path: str) -> str:
        """Extract text from a plain text file."""
        try:
            with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except Exception as e:
            raise ValueError(f"Failed to read TXT file: {str(e)}")
            
        cleaned_text = self.clean_text(text)
        if not cleaned_text or len(cleaned_text.strip()) < 50:
            raise ValueError("Extracted TXT text is empty or too short. Please upload a valid document.")
            
        return cleaned_text

    def clean_text(self, text: str) -> str:
        """Remove special characters, multiple newlines, and excess whitespace."""
        # Replace non-printable characters or weird symbols
        text = re.sub(r'[^\x00-\x7F\u00C0-\u00FF\u0100-\u017F]+', ' ', text)
        # Normalize spaces and tabs
        text = re.sub(r'[ \t]+', ' ', text)
        # Clean up line endings
        text = re.sub(r'\n+', '\n', text)
        return text.strip()

    def split_text(self, text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[str]:
        """Split text into overlapping chunks using RecursiveCharacterTextSplitter."""
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        return splitter.split_text(text)

    def store_in_chroma(self, session_id: str, chunks: List[str]) -> Chroma:
        """Embed and store text chunks in a session-specific collection in ChromaDB."""
        persist_dir = os.path.join(CHROMA_DB_DIR, session_id)
        
        # Create metadata for each chunk
        metadatas = [{"session_id": session_id, "chunk_index": i} for i in range(len(chunks))]
        
        # Initialize and persist Chroma vector store
        vector_store = Chroma.from_texts(
            texts=chunks,
            embedding=self.embeddings,
            metadatas=metadatas,
            persist_directory=persist_dir
        )
        return vector_store

    def retrieve_similar_chunks(self, session_id: str, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """Retrieve top-K matching chunks from the Chroma DB for the given session."""
        persist_dir = os.path.join(CHROMA_DB_DIR, session_id)
        
        if not os.path.exists(persist_dir):
            return []
            
        vector_store = Chroma(
            persist_directory=persist_dir,
            embedding_function=self.embeddings
        )
        
        # Query ChromaDB
        results = vector_store.similarity_search_with_relevance_scores(query, k=k)
        
        retrieved_data = []
        for doc, score in results:
            retrieved_data.append({
                "content": doc.page_content,
                "metadata": doc.metadata,
                "score": score
            })
            
        return retrieved_data
