import os
import shutil
import unittest
import uuid
import sqlite3
from fpdf import FPDF
from app.models.rag_core import RAGCore
from app.models.database import save_resume_profile, get_resume_profile

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "test_data")

class TestResumePipeline(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        os.makedirs(TEST_DATA_DIR, exist_ok=True)
        cls.pdf_path = os.path.join(TEST_DATA_DIR, "test_resume.pdf")
        
        # 1. Create a mock PDF resume using FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(40, 10, "John Doe Resume")
        pdf.ln(10)
        
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(40, 10, "Skills:")
        pdf.ln(5)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5, "Python programming, Machine Learning, Computer Vision, FastAPI web development.")
        pdf.ln(5)
        
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(40, 10, "Projects:")
        pdf.ln(5)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5, "1. DeepVision: Built a computer vision system using convolutional neural networks.\n"
                             "2. QuickAPI: Created a FastAPI microservice structure for real-time model serving.")
        pdf.output(cls.pdf_path)
        
        cls.rag = RAGCore()
        cls.session_id = f"test_{uuid.uuid4().hex}"

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEST_DATA_DIR):
            shutil.rmtree(TEST_DATA_DIR)
            
        # Clean up ChromaDB for test session
        test_chroma = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "chromadb", cls.session_id)
        if os.path.exists(test_chroma):
            shutil.rmtree(test_chroma)

    def test_1_extraction(self):
        """Test that PyMuPDF (fitz) successfully extracts text from the generated PDF."""
        extracted_text = self.rag.extract_text_from_pdf(self.pdf_path)
        self.assertIn("John Doe Resume", extracted_text)
        self.assertIn("FastAPI", extracted_text)
        self.assertIn("DeepVision", extracted_text)

    def test_2_splitting(self):
        """Test text splitting logic."""
        extracted_text = self.rag.extract_text_from_pdf(self.pdf_path)
        chunks = self.rag.split_text(extracted_text, chunk_size=100, chunk_overlap=10)
        self.assertTrue(len(chunks) > 0)
        # Ensure chunks contain text
        self.assertTrue(any("FastAPI" in chunk for chunk in chunks))

    def test_3_chroma_storage_and_retrieval(self):
        """Test storing chunks in ChromaDB and querying them."""
        extracted_text = self.rag.extract_text_from_pdf(self.pdf_path)
        chunks = self.rag.split_text(extracted_text, chunk_size=200, chunk_overlap=20)
        
        # Store in test-specific Chroma collection
        self.rag.store_in_chroma(self.session_id, chunks)
        
        # Query for a skill
        results = self.rag.retrieve_similar_chunks(self.session_id, "FastAPI", k=1)
        self.assertTrue(len(results) > 0)
        self.assertIn("FastAPI", results[0]["content"])
        
        # Query for CV
        results_cv = self.rag.retrieve_similar_chunks(self.session_id, "Computer Vision", k=1)
        self.assertTrue(len(results_cv) > 0)
        self.assertIn("Vision", results_cv[0]["content"])

    def test_4_database_profile_storage(self):
        """Test database insertion and retrieval of parsed profiles."""
        skills = ["Python", "FastAPI", "Computer Vision"]
        projects = ["DeepVision", "QuickAPI"]
        role = "AI/ML Engineer"
        
        # Insert
        profile_id = save_resume_profile("test_resume.pdf", "Raw text data", skills, projects, role)
        self.assertTrue(profile_id > 0)
        
        # Retrieve
        profile = get_resume_profile(profile_id)
        self.assertIsNotNone(profile)
        self.assertEqual(profile["classified_role"], role)
        self.assertIn("Python", profile["skills"])
        self.assertIn("DeepVision", profile["projects"])

if __name__ == "__main__":
    unittest.main()
