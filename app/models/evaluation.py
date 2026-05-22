import os
import json
import matplotlib.pyplot as plt
import numpy as np
from fpdf import FPDF
from typing import Dict, Any, List, Optional
from app.models.database import (
    get_interview_session,
    get_chat_history,
    save_evaluation_report
)
from app.models.llm_client import LLMClient

# Directories for PDF and chart generation
REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

class InterviewReportPDF(FPDF):
    """Custom FPDF layout for professional feedback reports."""
    
    def header(self):
        self.set_fill_color(99, 102, 241) # Indigo primary
        self.rect(0, 0, 210, 15, "F")
        self.set_y(2)
        self.set_font('Helvetica', 'B', 12)
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, 'AI MOCK INTERVIEW FEEDBACK REPORT', align='C', ln=True)
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}} | Confidential AI Assessment', align='C')

class EvaluationEngine:
    """Evaluation Engine to analyze candidate transcripts and generate feedback reports."""
    
    def __init__(self):
        self.llm = LLMClient()
        
    def generate_evaluation(self, session_id: str) -> Dict[str, Any]:
        """Run the evaluation prompt to score and grade the completed interview."""
        session = get_interview_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found.")
            
        history = get_chat_history(session_id)
        
        # Build clean transcript
        transcript_text = ""
        questions_answers = []
        last_question = ""
        
        for turn in history:
            if turn["sender"] == "assistant":
                last_question = turn["message"]
            elif turn["sender"] == "user":
                transcript_text += f"Interviewer: {last_question}\n"
                transcript_text += f"Candidate: {turn['message']}\n\n"
                questions_answers.append({
                    "question": last_question,
                    "answer": turn["message"]
                })

        prompt = f"""You are an elite Lead Engineering Recruiter and Technical Assessor.
Please analyze the following transcript of a mock interview for the position of **{session['role']}** (Difficulty: **{session['difficulty']}**).

Interview Transcript:
{transcript_text}

Evaluate the candidate based on these specific criteria:
1. **Technical Accuracy**: Did the candidate understand the technical concepts? Were their answers correct?
2. **Communication**: Did they explain concepts clearly? Was their tone professional?
3. **Role Relevance**: Did they demonstrate the practical skills needed for the {session['role']} role?

Provide a strict, professional evaluation in JSON format containing:
- `technical_score`: Integer (1-100)
- `communication_score`: Integer (1-100)
- `relevance_score`: Integer (1-100)
- `strengths`: List of 3 strings (specific positive points about their responses)
- `improvements`: List of 3 strings (specific constructive feedback points)
- `ideal_answers`: Object mapping each of the Interviewer's questions to the "Ideal Answer" that the candidate should have given.
- `study_topics`: List of 3 key topics/skills the candidate should study based on their gaps.

Example JSON output structure:
{{
  "technical_score": 85,
  "communication_score": 80,
  "relevance_score": 75,
  "strengths": ["Strengths 1", "Strengths 2", "Strengths 3"],
  "improvements": ["Improvement 1", "Improvement 2", "Improvement 3"],
  "ideal_answers": {{
     "Question 1 text?": "Ideal answer to question 1...",
     "Question 2 text?": "Ideal answer to question 2..."
  }},
  "study_topics": ["Topic A", "Topic B", "Topic C"]
}}
"""

        res = self.llm.generate_json(
            prompt=prompt,
            system_prompt="You are a JSON evaluator. Rate candidates honestly and keep temperature low (0.2).",
            temperature=0.1
        )
        
        eval_data = res["data"]
        
        # Calculate overall score out of 100
        tech = eval_data.get("technical_score", 50)
        comm = eval_data.get("communication_score", 50)
        rel = eval_data.get("relevance_score", 50)
        overall = int((tech * 0.5) + (comm * 0.25) + (rel * 0.25))
        
        # Save evaluation to SQLite
        pdf_filename = f"report_{session_id}.pdf"
        pdf_path = os.path.join(REPORTS_DIR, pdf_filename)
        
        save_evaluation_report(
            session_id=session_id,
            tech_score=tech,
            comm_score=comm,
            rel_score=rel,
            overall_score=overall,
            strengths=eval_data.get("strengths", []),
            improvements=eval_data.get("improvements", []),
            ideal_answers=eval_data.get("ideal_answers", {}),
            study_topics=eval_data.get("study_topics", []),
            pdf_path=pdf_path
        )
        
        # Generate the PDF report
        self.compile_pdf_report(session_id, {
            "role": session["role"],
            "difficulty": session["difficulty"],
            "technical_score": tech,
            "communication_score": comm,
            "relevance_score": rel,
            "overall_score": overall,
            "strengths": eval_data.get("strengths", []),
            "improvements": eval_data.get("improvements", []),
            "ideal_answers": eval_data.get("ideal_answers", {}),
            "study_topics": eval_data.get("study_topics", []),
            "questions_answers": questions_answers
        }, pdf_path)
        
        return {
            "session_id": session_id,
            "technical_score": tech,
            "communication_score": comm,
            "relevance_score": rel,
            "overall_score": overall,
            "strengths": eval_data.get("strengths", []),
            "improvements": eval_data.get("improvements", []),
            "ideal_answers": eval_data.get("ideal_answers", {}),
            "study_topics": eval_data.get("study_topics", []),
            "pdf_path": pdf_path
        }

    def compile_pdf_report(self, session_id: str, data: Dict[str, Any], output_path: str):
        """Compile a styled PDF evaluation report incorporating a matplotlib score chart."""
        # 1. Generate a score chart using matplotlib
        chart_path = os.path.join(REPORTS_DIR, f"chart_{session_id}.png")
        self.generate_bar_chart(
            scores=[data["technical_score"], data["communication_score"], data["relevance_score"], data["overall_score"]],
            labels=["Technical Accuracy", "Communication", "Role Relevance", "Overall Rating"],
            output_path=chart_path
        )
        
        # 2. Build PDF structure
        pdf = InterviewReportPDF()
        pdf.alias_nb_pages()
        pdf.add_page()
        
        # Set fonts and metadata
        pdf.set_text_color(51, 65, 85) # Slate 700
        
        # Meta Card
        pdf.set_fill_color(241, 245, 249) # Slate 100
        pdf.rect(10, 20, 190, 25, "F")
        pdf.set_xy(12, 22)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 6, f"Role Name: {data['role']}", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, f"Session ID: {session_id}", ln=True)
        pdf.cell(0, 6, f"Difficulty: {data['difficulty']}", ln=True)
        pdf.ln(10)
        
        # Embed Score Chart
        if os.path.exists(chart_path):
            pdf.image(chart_path, x=15, y=50, w=180, h=70)
            pdf.ln(75)
            
        # Strengths & Improvements Columns
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(99, 102, 241) # Indigo primary
        pdf.cell(0, 8, "Key Strengths", ln=True)
        pdf.set_text_color(51, 65, 85)
        pdf.set_font("Helvetica", "", 10)
        for s in data["strengths"]:
            pdf.cell(5)
            pdf.cell(0, 6, f"- {s}", ln=True)
        pdf.ln(4)
        
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(225, 29, 72) # Red 600
        pdf.cell(0, 8, "Areas for Improvement", ln=True)
        pdf.set_text_color(51, 65, 85)
        pdf.set_font("Helvetica", "", 10)
        for imp in data["improvements"]:
            pdf.cell(5)
            pdf.cell(0, 6, f"- {imp}", ln=True)
        pdf.ln(4)
        
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(99, 102, 241)
        pdf.cell(0, 8, "Recommended Study Topics", ln=True)
        pdf.set_text_color(51, 65, 85)
        pdf.set_font("Helvetica", "", 10)
        for topic in data["study_topics"]:
            pdf.cell(5)
            pdf.cell(0, 6, f"- {topic}", ln=True)
        pdf.ln(10)
            
        # Ideal Answers Page
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(15, 23, 42) # Slate 900
        pdf.cell(0, 10, "Question & Answer Breakdown", ln=True)
        pdf.ln(5)
        
        idx = 1
        for qa in data["questions_answers"]:
            q_text = qa["question"]
            a_text = qa["answer"]
            
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(99, 102, 241)
            pdf.multi_cell(0, 6, f"Q{idx}: {q_text}")
            pdf.ln(2)
            
            pdf.set_font("Helvetica", "I", 10)
            pdf.set_text_color(100, 116, 139) # Slate 500
            pdf.multi_cell(0, 5, f"Your Answer: {a_text}")
            pdf.ln(2)
            
            # Retrieve ideal answer matching the question
            ideal = data["ideal_answers"].get(q_text)
            if not ideal:
                # Fallback search inside keys
                for key, val in data["ideal_answers"].items():
                    if q_text[:30] in key:
                        ideal = val
                        break
            if not ideal:
                ideal = "Refer to the recommended study topics for guidance on this question."
                
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(22, 101, 52) # Green 800
            pdf.multi_cell(0, 5, f"Ideal Answer: {ideal}")
            pdf.ln(8)
            idx += 1
            
        # Save PDF
        pdf.output(output_path)
        
        # Clean up temporary chart image
        if os.path.exists(chart_path):
            try:
                os.remove(chart_path)
            except Exception:
                pass

    def generate_bar_chart(self, scores: List[int], labels: List[str], output_path: str):
        """Helper to output score charts utilizing matplotlib."""
        plt.style.use('ggplot')
        fig, ax = plt.subplots(figsize=(8, 3.5))
        
        # Indigo, Purple, Teal, Sky-Blue tones
        colors = ['#818CF8', '#A78BFA', '#2DD4BF', '#6366F1']
        
        bars = ax.barh(labels, scores, color=colors, height=0.5)
        ax.set_xlim(0, 100)
        ax.set_xlabel('Score (out of 100)')
        ax.set_title('Performance Category Breakdown', fontsize=12, fontweight='bold', pad=15)
        
        # Add labels to the ends of the bars
        for bar in bars:
            width = bar.get_width()
            ax.text(width + 2, bar.get_y() + bar.get_height()/2, f'{int(width)}%', 
                    ha='left', va='center', fontweight='bold', color='#1E293B')
            
        plt.tight_layout()
        plt.savefig(output_path, dpi=200)
        plt.close()
