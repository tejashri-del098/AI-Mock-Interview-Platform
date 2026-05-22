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
