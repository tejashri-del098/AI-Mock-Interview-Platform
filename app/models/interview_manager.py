import random
from typing import Dict, Any, List, Optional
from app.models.database import (
    get_resume_profile,
    get_interview_session,
    save_chat_turn,
    get_chat_history
)
from app.models.llm_client import LLMClient
from app.models.rag_core import RAGCore

BEHAVIORAL_QUESTIONS = [
    "Tell me about a time you failed on a project, how you handled it, and what you learned.",
    "Describe a situation where you had a strong technical disagreement with a team member. How did you resolve it?",
    "Tell me about a challenging technical problem you solved. What was your approach, and how did you select the solution?",
    "How do you handle tight deadlines or shifting project requirements under pressure?",
    "Describe a time when you had to learn a completely new technology or domain quickly to deliver a project. How did you go about it?"
]

SYSTEM_PERSONA = """You are a strict but fair lead technical interviewer and recruiter at a top-tier technology company.
Your goal is to conduct a highly professional, rigorous mock interview tailored to the candidate's resume, the target job role, and the chosen difficulty level.

Strict but Fair Persona Guidelines:
1. **Maintain Professional Tone**: Be concise, professional, and slightly formal. Do not use overly friendly language or conversational filler.
2. **Follow Up on Answers**: Listen closely to the candidate's response. Probe their technical understanding, challenge assumptions, and ask them to explain "why" they made certain choices.
3. **Reference Resume and Context**: Ground your technical questions in the project details and skills retrieved from their resume.
4. **Behavioral Integration**: If a behavioral question is asked, evaluate their communication, soft skills, and ownership mindset.
5. **No Placeholders**: Never use placeholder text or instructions. Speak directly to the candidate.
6. **Graceful Handling of 'I don't know'**: If the candidate does not know the answer or answers incorrectly, do not immediately lecture them. Gracefully acknowledge it (e.g., "Understood, let's pivot to a different aspect of this topic") and move to the next question, keeping a mental note for the evaluation.
"""

class InterviewManager:
    """Class to manage the flow of the mock interview, tracking turns, state, and prompt generation."""
    
    def __init__(self):
        self.llm = LLMClient()
        self.rag = RAGCore()
        
    def classify_role(self, skills: List[str], projects: List[str]) -> str:
        """Classify candidate's target role based on resume skills and projects using LLM."""
        prompt = f"""Based on the following resume skills and projects, classify the candidate's optimal target engineering role (e.g., 'AI/ML Engineer', 'Fullstack Engineer', 'Data Engineer', 'Backend Developer', 'Frontend Developer', 'DevOps Engineer').
Return ONLY the title of the role as a single plain text string. Do not include any other text.

Skills: {", ".join(skills)}
Projects: {", ".join(projects)}
"""
        try:
            res = self.llm.generate(prompt=prompt, system_prompt="You are a classifier.", temperature=0.1, max_tokens=20)
            role = res["text"].strip().strip('"').strip("'")
            return role if role else "Software Engineer"
        except Exception:
            return "Software Engineer"

    def generate_first_question(self, session_id: str, profile_id: int, difficulty: str) -> str:
        """Generate the first technical interview question based on the resume profile."""
        profile = get_resume_profile(profile_id)
        if not profile:
            raise ValueError(f"Resume profile not found for ID: {profile_id}")
            
        role = profile["classified_role"]
        skills = profile["skills"]
        projects = profile["projects"]
        
        # Pull initial context card from ChromaDB related to the main skills/role
        rag_context = ""
        try:
            search_query = f"{role} {' '.join(skills[:3])}"
            chunks = self.rag.retrieve_similar_chunks(session_id=session_id, query=search_query, k=2)
            rag_context = "\n---\n".join([c["content"] for c in chunks])
        except Exception as e:
            # Fallback if ChromaDB query fails
            rag_context = f"Skills: {', '.join(skills)}\nProjects: {', '.join(projects)}"

        prompt = f"""The candidate has uploaded a resume for the position of **{role}**.
The difficulty level is **{difficulty}**.

Resume Summary (from RAG index cards):
{rag_context}

Please generate the first technical question of the interview.
- It should target a key technical project or primary skill mentioned in their resume.
- It must match the difficulty level ({difficulty}).
- Introduce yourself briefly as the lead interviewer, welcome the candidate to the interview for the {role} position, and state the first question directly.
"""
        
        res = self.llm.generate(prompt=prompt, system_prompt=SYSTEM_PERSONA, temperature=0.6)
        
        # Save to database
        save_chat_turn(
            session_id=session_id,
            turn_index=0,
            sender="assistant",
            message=res["text"],
            tokens=res["tokens"],
            latency=res["latency"]
        )
        
        return res["text"]

    def generate_next_question(self, session_id: str, user_answer: str) -> str:
        """Process user answer, update history, and generate the next interview question."""
        session = get_interview_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found.")
            
        role = session["role"]
        difficulty = session["difficulty"]
        max_questions = session["duration"] # duration acts as target number of questions (e.g. 5)
        
        # Get chat history
        history = get_chat_history(session_id)
        current_turn = len(history) # history has [Q0, A0, Q1, A1...]
        
        # Save user answer first
        save_chat_turn(
            session_id=session_id,
            turn_index=current_turn,
            sender="user",
            message=user_answer
        )
        
        # Check if we have reached the max number of questions
        # Note: 1 turn = 1 assistant Q + 1 user A. 
        # If duration = 5, we ask Q0, Q1, Q2, Q3, Q4. When candidate answers A4, we are done.
        num_questions_asked = sum(1 for turn in history if turn["sender"] == "assistant")
        
        if num_questions_asked >= max_questions:
            return "Thank you for your responses. The interview portion is now complete. I will analyze your answers and generate a comprehensive evaluation report. Please click 'Complete & View Feedback'."

        # Query ChromaDB for context relevant to the user's latest response or target skills
        rag_context = ""
        try:
            # Query based on user answer to fetch specific resume details matching the discussion
            chunks = self.rag.retrieve_similar_chunks(session_id=session_id, query=user_answer, k=2)
            rag_context = "\n---\n".join([c["content"] for c in chunks])
        except Exception:
            pass

        # Build chat transcript for LLM context
        transcript = ""
        for turn in history:
            role_label = "Interviewer" if turn["sender"] == "assistant" else "Candidate"
            transcript += f"{role_label}: {turn['message']}\n\n"
        # Append the latest user answer as well
        transcript += f"Candidate: {user_answer}\n\n"

        # Determine if we should inject a behavioral question.
        # Let's inject exactly one behavioral question. We'll do it around the middle of the interview.
        # E.g., if max_questions = 5, middle is question index 2 (the 3rd question, Q2).
        behavioral_index = max_questions // 2
        
        is_behavioral_turn = (num_questions_asked == behavioral_index)
        
        if is_behavioral_turn:
            # Select a random behavioral question, ensuring it fits the context or is generic
            # Let's see if we've already asked one (just in case)
            behavioral_q = random.choice(BEHAVIORAL_QUESTIONS)
            prompt = f"""You are in the middle of a {difficulty}-level mock interview with the candidate for the {role} position.
Here is the conversation history:
{transcript}

It is now time to inject a behavioral question. Select this question:
"{behavioral_q}"

Acknowledge the candidate's last answer briefly and professionally, and then transition smoothly into asking this behavioral question.
"""
        else:
            # Technical follow-up or new technical question
            prompt = f"""You are conducting a {difficulty}-level technical mock interview with the candidate for the {role} position.
Here is the conversation history so far:
{transcript}

Relevant context from the candidate's resume (RAG index cards):
{rag_context}

Please generate the next technical question.
- If the candidate's previous answer was brief, vague, or had technical gaps, ask a targeted follow-up question probing that gap.
- If the candidate answered "I don't know" or struggled completely, acknowledge it gracefully (without lecturing them) and pivot to a different technical skill or project from their resume.
- Make sure the question matches the {difficulty} level.
- Do not repeat questions already asked.
- Ask the question directly.
"""
            
        res = self.llm.generate(prompt=prompt, system_prompt=SYSTEM_PERSONA, temperature=0.7)
        
        # Save assistant question
        save_chat_turn(
            session_id=session_id,
            turn_index=current_turn + 1,
            sender="assistant",
            message=res["text"],
            tokens=res["tokens"],
            latency=res["latency"]
        )
        
        return res["text"]
        
    def is_interview_complete(self, session_id: str) -> bool:
        """Check if the target number of questions has been answered."""
        session = get_interview_session(session_id)
        if not session:
            return True
        max_questions = session["duration"]
        history = get_chat_history(session_id)
        num_questions_asked = sum(1 for turn in history if turn["sender"] == "assistant")
        num_answers_given = sum(1 for turn in history if turn["sender"] == "user")
        
        return num_answers_given >= max_questions
