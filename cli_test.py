import os
import sys
import uuid
from app.models.database import init_db, save_interview_session
from app.models.rag_core import RAGCore
from app.models.interview_manager import InterviewManager
from app.models.evaluation import EvaluationEngine

def main():
    print("=" * 60)
    print(" AI MOCK INTERVIEW CLI TEST ENVIRONMENT")
    print("=" * 60)
    
    # 1. Initialize Database
    init_db()
    
    # 2. Get PDF Resume Path
    pdf_path = input("Enter the absolute path to your PDF resume (or press Enter for a default check): ").strip()
    if not pdf_path:
        # Create a dummy file or use a placeholder if they hit enter
        print("Please provide a valid PDF path to test.")
        sys.exit(1)
        
    if not os.path.exists(pdf_path):
        print(f"Error: File not found at '{pdf_path}'")
        sys.exit(1)
        
    print("\n[Step 1] Ingesting & indexing resume PDF...")
    rag = RAGCore()
    try:
        raw_text = rag.extract_text_from_pdf(pdf_path)
        print(f"Extracted {len(raw_text)} characters of text from PDF.")
    except Exception as e:
        print(f"Failed to parse PDF: {str(e)}")
        sys.exit(1)
        
    session_id = str(uuid.uuid4())
    print(f"Generated Session ID: {session_id}")
    
    # Split and index
    chunks = rag.split_text(raw_text)
    print(f"Split text into {len(chunks)} chunks.")
    rag.store_in_chroma(session_id=session_id, chunks=chunks)
    print("Indexed resume chunks successfully in local ChromaDB.")
    
    # 3. Extract profile details
    print("\n[Step 2] Classifying target engineering role...")
    interviewer = InterviewManager()
    
    # Simple extraction for CLI test
    from app.models.llm_client import LLMClient
    llm = LLMClient()
    
    # Extract skills
    try:
        prompt = f"Extract all technical skills from this resume text as a comma-separated list: {raw_text[:2000]}"
        res = llm.generate(prompt=prompt)
        skills = [s.strip() for s in res["text"].split(",") if s.strip()]
        print(f"Skills extracted: {', '.join(skills[:8])}...")
    except Exception as e:
        print(f"Failed to connect to LLM API. Please ensure your GEMINI_API_KEY or GROQ_API_KEY is set in your .env file. Error: {str(e)}")
        sys.exit(1)
        
    role = interviewer.classify_role(skills, [])
    print(f"Classified Target Role: {role}")
    
    difficulty = input("\nEnter difficulty level (Junior, Mid, Senior) [default: Mid]: ").strip() or "Mid"
    duration = 3 # 3 turns for quick CLI testing
    print(f"Interview duration configured: {duration} turns.")
    
    # 4. Save session
    from app.models.database import save_resume_profile
    profile_id = save_resume_profile(
        filename=os.path.basename(pdf_path),
        raw_text=raw_text,
        skills=skills,
        projects=[],
        classified_role=role
    )
    save_interview_session(session_id, profile_id, role, difficulty, duration)
    
    # 5. Start Interview
    print("\n" + "=" * 60)
    print(" STARTING MOCK INTERVIEW")
    print("=" * 60)
    
    # Welcome & First Question
    current_q = interviewer.generate_first_question(session_id, profile_id, difficulty)
    print(f"\nAI Interviewer:\n{current_q}\n")
    
    for turn in range(duration):
        user_ans = input("Your Answer: ").strip()
        while not user_ans:
            user_ans = input("Your Answer (cannot be blank): ").strip()
            
        print("\nAI Interviewer is thinking...")
        current_q = interviewer.generate_next_question(session_id, user_ans)
        print(f"\nAI Interviewer:\n{current_q}\n")
        
    print("\nInterview concluded! Generating evaluation report...")
    eval_engine = EvaluationEngine()
    eval_report = eval_engine.generate_evaluation(session_id)
    
    print("\n" + "=" * 60)
    print(" EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Overall Score: {eval_report['overall_score']}/100")
    print(f"Technical: {eval_report['technical_score']}/100")
    print(f"Communication: {eval_report['communication_score']}/100")
    print(f"Role Relevance: {eval_report['relevance_score']}/100")
    
    print("\nStrengths:")
    for s in eval_report["strengths"]:
        print(f" + {s}")
        
    print("\nAreas for Improvement:")
    for imp in eval_report["improvements"]:
        print(f" - {imp}")
        
    print("\nRecommended Study Topics:")
    for topic in eval_report["study_topics"]:
        print(f" * {topic}")
        
    print(f"\nFeedback Report PDF generated: {eval_report['pdf_path']}")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
