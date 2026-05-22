The 100% Free Tech Stack
Frontend: Streamlit (Python-native, rapid UI development).

Backend: FastAPI (Lightning-fast API routing).

Vector Database: ChromaDB (Local, free, perfect for document intelligence).

LLM Engine: Groq API (Llama 3) or Google Gemini API (Free tier for blazing-fast inference).

Embeddings: HuggingFace all-MiniLM-L6-v2 (Local, zero cost).

Audio Processing: OpenAI Whisper (Local Speech-to-Text) & Edge TTS (Text-to-Speech).

Phase 1: Project Setup & Environment (Tasks 1-10)
Initialize a Git repository for the hackathon project.

Create a Python virtual environment (python -m venv env).

Create a requirements.txt file.

Install FastAPI, Uvicorn, and Streamlit.

Install LangChain, ChromaDB, and sentence-transformers.

Install PyMuPDF (for PDF resume parsing) and python-dotenv.

Install Whisper and Edge TTS for audio handling.

Set up a .env file to securely store your free LLM API keys.

Create the fundamental folder structure (/app, /api, /models, /ui).

Write a basic FastAPI main.py health-check endpoint.

Phase 2: Resume Intelligence & RAG Core (Tasks 11-30)
Concept Check: Think of the RAG system like an open-book test for the AI. Instead of making the language model read the entire resume every single time it speaks, ChromaDB chops the resume into bite-sized "index cards." When the AI interviewer needs to ask about a specific skill, it just pulls the exact index card it needs.

Build a utility function to upload and accept a PDF resume.

Implement PyMuPDF to extract raw text from the uploaded document.

Write a text cleaning function to strip special characters and excess whitespace.

Configure LangChain's RecursiveCharacterTextSplitter.

Define a chunk size (e.g., 500 tokens) and overlap (e.g., 50 tokens) for splitting.

Split the cleaned resume text into chunks.

Initialize the HuggingFace all-MiniLM-L6-v2 embedding model.

Initialize a local ChromaDB instance to store the chunks.

Embed the resume text chunks into vectors.

Store the vector embeddings in ChromaDB.

Write a query function to retrieve the top-K similar chunks from ChromaDB.

Test the retrieval by querying specific skills (e.g., "Python", "Computer Vision").

Create a FastAPI endpoint /upload-resume that handles the file processing.

Create an endpoint /extract-skills to summarize the resume.

Craft a system prompt instructing the LLM to extract key skills and projects.

Connect the LLM to the ChromaDB retriever to form the RAG chain.

Parse the LLM output into a structured JSON format ({"skills": [...], "projects": [...]}).

Add error handling for unreadable or image-heavy PDFs.

Save the extracted JSON profile to a local SQLite database or temporary file.

Write a unit test for the complete resume extraction pipeline.

Phase 3: Conversational AI & Interview Generation (Tasks 31-50)
Define the parameters for the mock interview (e.g., role, difficulty, duration).

Craft the core "System Persona" prompt for the LLM to act as a strict but fair technical recruiter.

Design the prompt to generate the first interview question based on the resume JSON.

Create a state manager to track conversation history (the context window).

Write a function to append user answers and AI questions to the chat history.

Craft the prompt for follow-up questions, ensuring the AI references previous answers.

Implement logic to classify the role (e.g., AI/ML Engineer) based on the resume.

Create a pool of generic behavioral questions (e.g., "Tell me about a time you failed...").

Write a function to randomly inject one behavioral question per interview.

Build a FastAPI endpoint /generate-question that takes the chat history and returns the next prompt.

Add logic to ensure the AI doesn't repeat the exact same questions.

Implement a token counter to prevent exceeding the LLM API's free tier limits.

Set up a mechanism to dynamically switch between technical depth and behavioral breadth.

Create a specific prompt rule to handle "I don't know" answers gracefully.

Implement timeout handling in case the free LLM API experiences high latency.

Write a function to detect when the target number of questions (e.g., 5) is reached.

Create a FastAPI endpoint /end-interview to trigger the evaluation phase.

Test the multi-turn conversation locally using a simple CLI script.

Refine the AI persona to ensure the tone remains professional and realistic.

Add logging to track generated questions and API latency.

Phase 4: Audio Processing Pipeline (Tasks 51-65)
Create a utility module for audio handling (audio_utils.py).

Set up Edge TTS to convert the AI's generated text questions into spoken audio.

Write a function to save the generated TTS audio to a temporary .mp3 file.

Test the TTS output for natural pacing and clarity.

Create a Streamlit audio player component to auto-play the TTS file to the user.

Integrate a browser-based audio recorder in Streamlit (using a community component like st-audiorec).

Write a function to save the user's recorded audio securely to the server.

Initialize the local Whisper model (use the tiny or base model for speed).

Write a function to transcribe the user's audio file into text using Whisper.

Add basic error handling for empty or silent audio files.

Create a FastAPI endpoint /process-audio that accepts audio, transcribes it, and returns text.

Connect the Whisper transcription directly to the chat history as the user's response.

Optimize Whisper loading time by keeping the model loaded in memory during the session.

Add a fallback text input in the UI in case the user's microphone fails or they prefer typing.

Test the full audio loop: AI speaks -> User records -> Whisper transcribes -> AI processes.

Phase 5: Evaluation & Feedback System (Tasks 66-80)
Craft a comprehensive evaluation prompt for the LLM to grade the entire interview.

Design the evaluation criteria: Technical Accuracy, Communication, and Role Relevance.

Instruct the LLM to output feedback strictly in JSON format (Scores + Actionable Advice).

Build a function to parse the evaluation JSON safely without breaking.

Write logic to calculate an overall out-of-100 readiness score.

Create a sub-prompt to generate "Ideal Answers" for the questions the user struggled with.

Connect the evaluation module to the /end-interview backend endpoint.

Structure the feedback object to explicitly list strengths and areas for improvement.

Add a feature to recommend specific topics to study based on weak technical answers.

Save the final evaluation report to SQLite/JSON for the user to review later.

Create a function to generate a downloadable PDF summary of the feedback.

Format the PDF using an automated library (like FPDF).

Test the evaluation logic with intentionally terrible and exceptionally good answers to calibrate it.

Refine the LLM temperature (set to 0.2 or lower) to ensure grading is consistent and factual.

Verify that the evaluation explicitly references the original RAG context (the resume).

Phase 6: Streamlit UI Integration (Tasks 81-90)
Design the Streamlit dashboard layout (Sidebar for controls, main column for the interview).

Create a clean landing page introducing the "AI Mock Interview Platform".

Build the File Uploader widget in the sidebar for the PDF resume.

Add status spinners (st.spinner) to show progress during the backend resume parsing.

Initialize Streamlit st.session_state to hold chat history and prevent the app from refreshing the interview.

Build the chat interface using st.chat_message to display the ongoing conversation.

Integrate the audio recorder widget directly below the chat interface.

Link the UI buttons to the FastAPI backend endpoints using the requests library.

Build the post-interview Feedback Dashboard with metrics and charts (e.g., radar chart for skills).

Add a "Download Report" button that triggers the PDF generation.

Phase 7: Optimization, Testing & Hackathon Deliverables (Tasks 91-100)
Perform a full end-to-end test run: Upload -> Interview -> Audio -> Evaluation.

Debug any state mismatches in Streamlit (ensuring a page refresh doesn't wipe the interview data).

Optimize the ChromaDB retrieval latency to keep the UI snappy.

Add error boundaries in the UI to prevent crashes if the LLM API hits a rate limit.

Style the Streamlit app using a custom theme config (dark mode, custom primary colors).

Write a comprehensive README.md documenting the architecture, tech stack, and setup steps.

Record a high-quality 2-3 minute demonstration video of the working prototype.

Clean up all source code, adding docstrings and removing terminal print statements.

Push the finalized code to a public GitHub repository.

Prepare your final presentation deck detailing your problem-solving approach, scalability, and RAG architecture.