import os
import uuid
import shutil
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List

from app.models.database import (
    save_resume_profile,
    save_interview_session,
    get_resume_profile,
    get_interview_session,
    get_chat_history
)
from app.models.rag_core import RAGCore
from app.models.llm_client import LLMClient
from app.models.interview_manager import InterviewManager
from app.models.audio_utils import WhisperManager, text_to_speech
from app.models.evaluation import EvaluationEngine

app = FastAPI(title="AI Mock Interview Platform API", version="1.0.0")

# Enable CORS for frontend connectivity
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories setup
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
AUDIO_DIR = os.path.join(DATA_DIR, "audio")
REPORTS_DIR = os.path.join(DATA_DIR, "reports")

for d in [UPLOAD_DIR, AUDIO_DIR, REPORTS_DIR]:
    os.makedirs(d, exist_ok=True)

# Mount static files to serve generated audio files and PDF reports
app.mount("/static", StaticFiles(directory=DATA_DIR), name="static")

# Initialise core engine objects
rag = RAGCore()
llm = LLMClient()
interviewer = InterviewManager()
evaluator = EvaluationEngine()

# Pydantic schemas for request validation
class ExtractSkillsRequest(BaseModel):
    session_id: str
    raw_text: str
    filename: str

class StartInterviewRequest(BaseModel):
    session_id: str
    profile_id: int
    role: str
    difficulty: str
    duration: int

class GenerateQuestionRequest(BaseModel):
    session_id: str
    user_answer: str

class EndInterviewRequest(BaseModel):
    session_id: str

@app.get("/health")
def health_check():
    """Health check endpoint to verify backend status."""
    return {"status": "healthy", "service": "AI Mock Interview API"}

@app.post("/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    """Upload a resume (PDF, DOCX, TXT), extract text, split it, and index it into ChromaDB."""
    filename_lower = file.filename.lower()
    if not (filename_lower.endswith('.pdf') or filename_lower.endswith('.docx') or filename_lower.endswith('.txt') or filename_lower.endswith('.md')):
        raise HTTPException(status_code=400, detail="Only PDF, DOCX, and TXT files are supported.")
        
    session_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{session_id}_{file.filename}")
    
    # Save file locally
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {str(e)}")
        
    # Extract, clean and index text
    try:
        raw_text = rag.extract_text(file_path)
        chunks = rag.split_text(raw_text, chunk_size=500, chunk_overlap=50)
        rag.store_in_chroma(session_id=session_id, chunks=chunks)
    except ValueError as ve:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Error processing resume: {str(e)}")
        
    return {
        "session_id": session_id,
        "filename": file.filename,
        "raw_text": raw_text
    }

@app.post("/extract-skills")
async def extract_skills(request: ExtractSkillsRequest):
    """Use the LLM to extract key skills/projects and classify the job role."""
    try:
        prompt = f"""You are a skilled resume parsing algorithm.
Extract all key technical skills and key project names from the candidate's resume text below.
Produce a JSON output containing ONLY:
1. `skills`: List of strings representing core technologies, languages, tools, or methodologies.
2. `projects`: List of strings representing name/title of significant projects described.

Resume Text:
{request.raw_text}
"""
        res = llm.generate_json(
            prompt=prompt,
            system_prompt="You are a JSON resume parser.",
            temperature=0.1
        )
        data = res["data"]
        skills = []
        projects = []
        if isinstance(data, dict):
            skills = data.get("skills", [])
            projects = data.get("projects", [])
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    if "skills" in item and isinstance(item["skills"], list):
                        skills.extend(item["skills"])
                    elif "skill" in item:
                        skills.append(item["skill"])
                    if "projects" in item and isinstance(item["projects"], list):
                        projects.extend(item["projects"])
                    elif "project" in item:
                        projects.append(item["project"])
        
        # Classify the engineering role
        role = interviewer.classify_role(skills, projects)
        
        # Save to database
        profile_id = save_resume_profile(
            filename=request.filename,
            raw_text=request.raw_text,
            skills=skills,
            projects=projects,
            classified_role=role
        )
        
        return {
            "profile_id": profile_id,
            "skills": skills,
            "projects": projects,
            "classified_role": role
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract resume profile: {str(e)}")

@app.post("/start-interview")
async def start_interview(request: StartInterviewRequest):
    """Initialise an interview session and generate the first question."""
    try:
        save_interview_session(
            session_id=request.session_id,
            candidate_id=request.profile_id,
            role=request.role,
            difficulty=request.difficulty,
            duration=request.duration
        )
        
        first_q = interviewer.generate_first_question(
            session_id=request.session_id,
            profile_id=request.profile_id,
            difficulty=request.difficulty
        )
        
        # Convert first question to speech
        audio_filename = f"{request.session_id}_turn_0.mp3"
        audio_path = await text_to_speech(first_q, audio_filename)
        audio_url = f"/static/audio/{audio_filename}"
        
        return {
            "question": first_q,
            "audio_url": audio_url,
            "completed": False
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start interview: {str(e)}")

@app.post("/generate-question")
async def generate_question(request: GenerateQuestionRequest):
    """Accept the candidate's latest text response and return the next question + audio file."""
    try:
        session = get_interview_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Interview session not found.")
            
        # Check if interview is already complete
        if interviewer.is_interview_complete(request.session_id):
            return {
                "question": "The interview is now complete. Please select Complete & View Feedback.",
                "audio_url": None,
                "completed": True
            }
            
        next_q = interviewer.generate_next_question(
            session_id=request.session_id,
            user_answer=request.user_answer
        )
        
        history = get_chat_history(request.session_id)
        # Turn index is basically length of history - 1
        turn_idx = len(history) - 1
        
        audio_url = None
        completed = interviewer.is_interview_complete(request.session_id)
        
        # Don't speak the completion message
        if not completed or "complete" not in next_q.lower():
            audio_filename = f"{request.session_id}_turn_{turn_idx}.mp3"
            await text_to_speech(next_q, audio_filename)
            audio_url = f"/static/audio/{audio_filename}"
            
        return {
            "question": next_q,
            "audio_url": audio_url,
            "completed": completed
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate next question: {str(e)}")

@app.post("/process-audio")
async def process_audio(file: UploadFile = File(...)):
    """Accept an audio recording, transcribe it locally using Whisper, and return the text."""
    temp_audio_path = os.path.join(AUDIO_DIR, f"temp_{uuid.uuid4()}_{file.filename}")
    
    try:
        with open(temp_audio_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save temp audio: {str(e)}")
        
    try:
        # Transcribe audio using cached Whisper model
        transcription = WhisperManager.transcribe(temp_audio_path)
        
        if not transcription:
            return {"text": "", "warning": "Audio was silent or empty."}
            
        return {"text": transcription}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error transcribing audio: {str(e)}")
    finally:
        # Clean up temp file
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

@app.post("/end-interview")
async def end_interview(request: EndInterviewRequest):
    """End the interview session, trigger the LLM evaluation, and compile the final PDF report."""
    try:
        eval_report = evaluator.generate_evaluation(request.session_id)
        # Convert path to accessible web URL
        pdf_url = f"/static/reports/{os.path.basename(eval_report['pdf_path'])}"
        eval_report["pdf_url"] = pdf_url
        return eval_report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to complete interview evaluation: {str(e)}")
