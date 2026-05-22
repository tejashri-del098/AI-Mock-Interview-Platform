import os
import streamlit as st
import requests
import json
import base64
import streamlit.components.v1 as components

# API Server Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

# Page configuration with premium title and layout
st.set_page_config(
    page_title="AI Mock Interview Platform",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium styling rules
st.markdown("""
<style>
    /* Gradient headers and custom font styles */
    .title-text {
        font-size: 3rem !important;
        font-weight: 800 !important;
        background: linear-gradient(135deg, #6366F1 0%, #A78BFA 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .subtitle-text {
        font-size: 1.2rem;
        color: #94A3B8;
        margin-bottom: 2rem;
    }
    /* Metric styling */
    .metric-card {
        background-color: #1E293B;
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #334155;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .metric-value {
        font-size: 2.5rem;
        font-weight: 800;
        color: #6366F1;
        margin-top: 5px;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    /* Center align spinners */
    .stSpinner {
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# Helper function to autoplay audio in the browser
def autoplay_audio(audio_url: str):
    """Embed an HTML audio element to automatically play question text-to-speech."""
    full_url = f"{BACKEND_URL}{audio_url}"
    audio_html = f"""
    <audio autoplay style="display:none;">
        <source src="{full_url}" type="audio/mp3">
    </audio>
    """
    st.markdown(audio_html, unsafe_allow_html=True)

# Custom HTML5 Voice Recorder component using Streamlit components.html
def voice_recorder_component():
    """Renders a browser-based audio recorder that uploads recorded clips directly to FastAPI and returns transcribed text."""
    
    recorder_html = f"""
    <div style="font-family: sans-serif; background-color: #1E293B; border: 1px solid #334155; border-radius: 8px; padding: 15px; text-align: center; color: #F8FAFC;">
        <div style="font-size: 0.95rem; font-weight: bold; margin-bottom: 10px;">🎤 Record Your Answer</div>
        <div style="margin-bottom: 12px;">
            <button id="recordBtn" style="background-color: #EF4444; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold; cursor: pointer; margin-right: 8px; transition: background-color 0.2s;">
                🔴 Record
            </button>
            <button id="stopBtn" disabled style="background-color: #64748B; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold; cursor: not-allowed; transition: background-color 0.2s;">
                ⏹️ Stop
            </button>
        </div>
        <div id="status" style="font-size: 0.85rem; color: #94A3B8;">Click 'Record' and speak into your microphone.</div>
    </div>

    <script>
        let mediaRecorder;
        let audioChunks = [];
        const recordBtn = document.getElementById('recordBtn');
        const stopBtn = document.getElementById('stopBtn');
        const statusDiv = document.getElementById('status');

        recordBtn.addEventListener('click', async () => {{
            audioChunks = [];
            try {{
                const stream = await navigator.mediaDevices.getUserMedia({{ audio: true }});
                mediaRecorder = new MediaRecorder(stream, {{ mimeType: 'audio/webm' }});
                
                mediaRecorder.ondataavailable = (event) => {{
                    audioChunks.push(event.data);
                }};

                mediaRecorder.onstop = async () => {{
                    const audioBlob = new Blob(audioChunks, {{ type: 'audio/webm' }});
                    statusDiv.innerText = "Processing speech... transcribing audio...";
                    
                    // Upload to FastAPI process-audio endpoint
                    const formData = new FormData();
                    formData.append("file", audioBlob, "recording.webm");

                    try {{
                        const response = await fetch('{BACKEND_URL}/process-audio', {{
                            method: 'POST',
                            body: formData
                        }});
                        
                        const result = await response.json();
                        if (result.text) {{
                            statusDiv.innerText = "Transcribed successfully!";
                            // Send transcribed text back to Streamlit
                            window.parent.postMessage({{
                                type: 'streamlit:setComponentValue',
                                value: result.text
                            }}, '*');
                        }} else {{
                            statusDiv.innerText = result.warning || "Could not transcribe audio. Please try again or type your answer.";
                        }}
                    }} catch (err) {{
                        console.error("Upload error:", err);
                        statusDiv.innerText = "Error contacting transcription server. Try typing your response.";
                    }}
                }};

                mediaRecorder.start();
                recordBtn.disabled = true;
                recordBtn.style.backgroundColor = '#991B1B';
                recordBtn.style.cursor = 'not-allowed';
                stopBtn.disabled = false;
                stopBtn.style.backgroundColor = '#475569';
                stopBtn.style.cursor = 'pointer';
                statusDiv.innerHTML = "🔴 Recording... Speak now. Click 'Stop' when finished.";
                statusDiv.style.color = '#EF4444';
            }} catch (err) {{
                console.error("Mic permissions error:", err);
                statusDiv.innerText = "Microphone access denied or not supported in this browser. Please type your response.";
                statusDiv.style.color = '#EF4444';
            }}
        }});

        stopBtn.addEventListener('click', () => {{
            if (mediaRecorder && mediaRecorder.state !== 'inactive') {{
                mediaRecorder.stop();
                // Stop all tracks to release microphone
                mediaRecorder.stream.getTracks().forEach(track => track.stop());
                
                recordBtn.disabled = false;
                recordBtn.style.backgroundColor = '#EF4444';
                recordBtn.style.cursor = 'pointer';
                stopBtn.disabled = true;
                stopBtn.style.backgroundColor = '#64748B';
                stopBtn.style.cursor = 'not-allowed';
            }}
        }});
    </script>
    """
    return components.html(recorder_html, height=140)

# Initialize Streamlit session states
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "profile_id" not in st.session_state:
    st.session_state.profile_id = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "skills" not in st.session_state:
    st.session_state.skills = []
if "projects" not in st.session_state:
    st.session_state.projects = []
if "classified_role" not in st.session_state:
    st.session_state.classified_role = "Software Engineer"
if "interview_started" not in st.session_state:
    st.session_state.interview_started = False
if "interview_completed" not in st.session_state:
    st.session_state.interview_completed = False
if "current_question" not in st.session_state:
    st.session_state.current_question = ""
if "current_audio_url" not in st.session_state:
    st.session_state.current_audio_url = None
if "evaluation" not in st.session_state:
    st.session_state.evaluation = None

# Sidebar Content
with st.sidebar:
    st.markdown("### 💼 AI Mock Interview Panel")
    st.markdown("---")
    
    # 1. Resume Uploader Widget
    uploaded_file = st.file_uploader("Upload your resume (PDF)", type=["pdf"])
    
    if uploaded_file is not None and st.session_state.session_id is None:
        with st.spinner("Uploading and indexing resume text..."):
            try:
                # Post to /upload-resume
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                res = requests.post(f"{BACKEND_URL}/upload-resume", files=files)
                
                if res.status_code == 200:
                    data = res.json()
                    session_id = data["session_id"]
                    raw_text = data["raw_text"]
                    
                    st.session_state.session_id = session_id
                    
                    # Post to /extract-skills
                    with st.spinner("Extracting profile skills & projects..."):
                        extract_res = requests.post(
                            f"{BACKEND_URL}/extract-skills",
                            json={"session_id": session_id, "raw_text": raw_text, "filename": uploaded_file.name}
                        )
                        
                        if extract_res.status_code == 200:
                            profile = extract_res.json()
                            st.session_state.profile_id = profile["profile_id"]
                            st.session_state.skills = profile["skills"]
                            st.session_state.projects = profile["projects"]
                            st.session_state.classified_role = profile["classified_role"]
                            st.success("Resume processed successfully!")
                        else:
                            st.error("Failed to extract resume details.")
                else:
                    st.error(f"Error parsing PDF: {res.json().get('detail', 'Unknown error')}")
            except Exception as e:
                st.error(f"Failed to connect to backend server: {str(e)}")

    # Display Extracted Resume Metrics in Sidebar
    if st.session_state.session_id is not None:
        st.markdown("#### 🔍 Detected Candidate Profile")
        st.info(f"**Target Role:** {st.session_state.classified_role}")
        
        with st.expander("Extracted Skills"):
            st.write(", ".join(st.session_state.skills) if st.session_state.skills else "None detected")
            
        with st.expander("Detected Projects"):
            if st.session_state.projects:
                for p in st.session_state.projects:
                    st.markdown(f"- {p}")
            else:
                st.write("None detected")
                
        st.markdown("---")
        
        # 2. Config parameters
        st.markdown("#### ⚙️ Session Settings")
        selected_role = st.text_input("Confirm/Edit Job Role", value=st.session_state.classified_role)
        difficulty = st.selectbox("Select Difficulty", ["Junior", "Mid-Level", "Senior"], index=1)
        duration = st.slider("Number of Questions", min_value=3, max_value=8, value=5)
        
        # 3. Start Interview Button
        if not st.session_state.interview_started:
            if st.button("🚀 Start Interview", use_container_width=True):
                with st.spinner("Generating first question..."):
                    try:
                        start_payload = {
                            "session_id": st.session_state.session_id,
                            "profile_id": st.session_state.profile_id,
                            "role": selected_role,
                            "difficulty": difficulty,
                            "duration": duration
                        }
                        res = requests.post(f"{BACKEND_URL}/start-interview", json=start_payload)
                        if res.status_code == 200:
                            data = res.json()
                            st.session_state.current_question = data["question"]
                            st.session_state.current_audio_url = data["audio_url"]
                            st.session_state.chat_history.append({
                                "sender": "assistant",
                                "message": data["question"]
                            })
                            st.session_state.interview_started = True
                            st.rerun()
                        else:
                            st.error("Failed to start session.")
                    except Exception as e:
                        st.error(f"Error starting interview: {str(e)}")
                        
        else:
            # Active interview progress tracker
            num_asked = sum(1 for turn in st.session_state.chat_history if turn["sender"] == "assistant")
            st.markdown("#### 📊 Progress Tracker")
            st.progress(num_asked / duration)
            st.write(f"Question **{num_asked}** of **{duration}**")
            
            # Restart Session option
            if st.button("🔄 Reset Interview", use_container_width=True):
                for key in ["session_id", "profile_id", "chat_history", "skills", "projects", "interview_started", "interview_completed", "current_question", "current_audio_url", "evaluation"]:
                    st.session_state[key] = None if key != "chat_history" and key != "skills" and key != "projects" else []
                st.rerun()


# Main Column Content
st.markdown("<div class='title-text'>AI Mock Interview Platform</div>", unsafe_allow_html=True)

# State 1: Landing Page (Not started, no file uploaded)
if not st.session_state.interview_started and not st.session_state.interview_completed:
    st.markdown("<div class='subtitle-text'>A fully automated, local RAG-powered, speech-enabled technical mock recruiter to prep for your dream engineering role.</div>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### How it works:
        1. 📄 **Upload Resume**: Drag and drop your PDF resume into the sidebar file uploader. We index the text in a local ChromaDB collection.
        2. ⚙️ **Configure Job Details**: Confirm the auto-detected job title, configure difficulty levels, and set interview duration.
        3. 💬 **Speak / Type Answers**: The AI speaks each question using Edge TTS. You record answers from the web-mic or type fallback answers.
        4. 📈 **Get Detailed Feedback**: Receive technical competence gradings, strengths, improvements, and download a professional PDF summary report!
        """)
        
    with col2:
        st.info("💡 **Ready to practice?** Upload your PDF resume in the sidebar to load the recruiter interface!")
        # Quick summary card styling
        st.markdown("""
        <div style="background-color: #1E293B; border-radius: 12px; padding: 25px; border: 1px solid #334155; margin-top: 15px;">
            <h4 style="color: #6366F1; margin-top:0;">🤖 Tech Stack Specs</h4>
            <ul style="color: #94A3B8; margin-bottom: 0; padding-left: 20px;">
                <li><b>RAG Database:</b> ChromaDB (local instance)</li>
                <li><b>Text Embeddings:</b> HuggingFace all-MiniLM-L6-v2</li>
                <li><b>Voice Generation:</b> Edge Text-to-Speech</li>
                <li><b>Speech Recognition:</b> OpenAI Whisper (local tiny model)</li>
                <li><b>AI LLM Recruiter:</b> Google Gemini API (Recommended) or Groq</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

# State 2: Active Chat/Recruiting Room
elif st.session_state.interview_started and not st.session_state.interview_completed:
    st.markdown("💬 **Technical Recruiting Room**")
    st.markdown("---")
    
    # Renders chat messages history
    for chat in st.session_state.chat_history:
        with st.chat_message(chat["sender"]):
            st.write(chat["message"])
            
    # Autoplay the latest question audio
    if st.session_state.current_audio_url:
        autoplay_audio(st.session_state.current_audio_url)
        # Clear out current url so it doesn't autoplay again on streamlit refresh
        st.session_state.current_audio_url = None

    # Audio recorder input
    transcribed_text = voice_recorder_component()
    
    # Form for text submission and fallback review
    with st.form("response_form", clear_on_submit=True):
        st.write("✏️ **Review or Type Your Answer Below:**")
        
        # If voice_recorder returned transcribed text, use it as default value in text area!
        default_text_val = ""
        if transcribed_text:
            default_text_val = transcribed_text
            
        user_response = st.text_area("Your response:", value=default_text_val, placeholder="Start typing or use the recorder button above to dictate your answer...")
        submit_btn = st.form_submit_button("Submit Answer", use_container_width=True)
        
        if submit_btn:
            if not user_response.strip():
                st.warning("Please provide a response before submitting.")
            else:
                # Add response to UI chat feed
                st.session_state.chat_history.append({
                    "sender": "user",
                    "message": user_response
                })
                
                with st.spinner("AI Recruiter is processing and formulating next question..."):
                    try:
                        payload = {
                            "session_id": st.session_state.session_id,
                            "user_answer": user_response
                        }
                        res = requests.post(f"{BACKEND_URL}/generate-question", json=payload)
                        if res.status_code == 200:
                            data = res.json()
                            
                            st.session_state.current_question = data["question"]
                            st.session_state.current_audio_url = data["audio_url"]
                            
                            # Append next question to history
                            st.session_state.chat_history.append({
                                "sender": "assistant",
                                "message": data["question"]
                            })
                            
                            # If interview finished, toggle completed state
                            if data["completed"]:
                                st.session_state.interview_completed = True
                                st.session_state.interview_started = False
                                
                            st.rerun()
                        else:
                            st.error("Failed to generate next question.")
                    except Exception as e:
                        st.error(f"Error communicating with backend: {str(e)}")

# State 3: Assessment/Evaluation Dashboard
elif st.session_state.interview_completed:
    st.markdown("🏆 **Interview Assessment Dashboard**")
    st.markdown("---")
    
    # Fetch evaluation results if not already loaded
    if st.session_state.evaluation is None:
        with st.spinner("Analyzing transcript, grading performance, and compiling report PDF..."):
            try:
                res = requests.post(
                    f"{BACKEND_URL}/end-interview",
                    json={"session_id": st.session_state.session_id}
                )
                if res.status_code == 200:
                    st.session_state.evaluation = res.json()
                else:
                    st.error("Failed to fetch evaluation report from backend.")
            except Exception as e:
                st.error(f"Error fetching evaluation: {str(e)}")
                
    if st.session_state.evaluation is not None:
        report = st.session_state.evaluation
        
        # Display overall scores in 4 cards
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-label'>Overall Score</div>
                <div class='metric-value'>{report['overall_score']}/100</div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-label'>Technical Accuracy</div>
                <div class='metric-value' style='color:#A78BFA;'>{report['technical_score']}/100</div>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-label'>Communication Style</div>
                <div class='metric-value' style='color:#2DD4BF;'>{report['communication_score']}/100</div>
            </div>
            """, unsafe_allow_html=True)
        with col4:
            st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-label'>Role Relevance</div>
                <div class='metric-value' style='color:#60A5FA;'>{report['relevance_score']}/100</div>
            </div>
            """, unsafe_allow_html=True)
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Layout columns for strengths, weaknesses, and charts
        left_col, right_col = st.columns([2, 1])
        
        with left_col:
            st.markdown("### 🌟 In-Depth Assessment")
            
            st.success("✅ **Key Strengths Identified:**")
            for strength in report["strengths"]:
                st.markdown(f"- {strength}")
                
            st.warning("⚠️ **Areas for Improvement:**")
            for improvement in report["improvements"]:
                st.markdown(f"- {improvement}")
                
            st.info("📖 **Recommended Study Topics:**")
            for topic in report["study_topics"]:
                st.markdown(f"- {topic}")
                
        with right_col:
            st.markdown("### 📄 Export Results")
            # PDF Report download
            pdf_url = f"{BACKEND_URL}{report['pdf_url']}"
            st.markdown(f"""
            <a href="{pdf_url}" target="_blank" style="text-decoration:none;">
                <button style="width:100%; padding:12px; background-color:#6366F1; color:white; font-weight:bold; border:none; border-radius:6px; cursor:pointer;">
                    📥 Download Feedback Report (PDF)
                </button>
            </a>
            """, unsafe_allow_html=True)
            
            # Simple instructions
            st.markdown("""
            <div style="background-color: #1E293B; border-radius: 8px; padding: 15px; border: 1px solid #334155; margin-top:15px; font-size:0.9rem; color:#94A3B8;">
                Your report includes a detailed score breakdown, strengths assessment, study resources, and ideal responses compiled into a structured PDF.
            </div>
            """, unsafe_allow_html=True)
            
        # Detailed Question by Question breakdown
        st.markdown("---")
        st.markdown("### 📝 Turn-by-Turn Question Breakdown")
        
        # We can construct the QA display from the transcripts
        # Let's read transcripts from the evaluation response or reconstruct it
        # The evaluation contains "ideal_answers" mapping. We show this in an expander.
        for idx, (question, ideal) in enumerate(report["ideal_answers"].items(), 1):
            with st.expander(f"Question {idx}: {question}"):
                st.markdown(f"**Ideal Response:**")
                st.write(ideal)
                
        # Restart mock button
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Restart Interview (Start Over)", use_container_width=True):
            for key in ["session_id", "profile_id", "chat_history", "skills", "projects", "interview_started", "interview_completed", "current_question", "current_audio_url", "evaluation"]:
                st.session_state[key] = None if key != "chat_history" and key != "skills" and key != "projects" else []
            st.rerun()
