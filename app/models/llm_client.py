import os
import json
import re
import time
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

# We import these inside helper methods or conditionally so the app doesn't fail to load if only one SDK is used.
class LLMClient:
    """Client wrapper for Google Gemini and Groq API services."""
    
    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.groq_key = os.getenv("GROQ_API_KEY")
        
        # Initialize Gemini SDK if key is present
        if self.gemini_key:
            import google.generativeai as genai
            genai.configure(api_key=self.gemini_key)
            
        # Initialize Groq client if key is present
        self.groq_client = None
        if self.groq_key:
            try:
                from groq import Groq
                self.groq_client = Groq(api_key=self.groq_key)
            except ImportError:
                pass

    def get_active_provider(self) -> str:
        """Return the active provider ('gemini', 'groq', or 'none')."""
        if self.gemini_key:
            return "gemini"
        elif self.groq_client:
            return "groq"
        return "none"

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for a text block (rough rule of thumb: ~4 characters per token)."""
        if not text:
            return 0
        return max(1, len(text) // 4)

    def generate(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.7, max_tokens: int = 1000) -> Dict[str, Any]:
        """Generate a response using the available LLM API (Gemini by default, falling back to Groq)."""
        provider = self.get_active_provider()
        
        if provider == "none":
            raise ValueError("No LLM API keys found. Please set GEMINI_API_KEY or GROQ_API_KEY in your .env file.")
            
        start_time = time.time()
        response_text = ""
        actual_provider = provider
        
        try:
            if provider == "gemini":
                import google.generativeai as genai
                # Use gemini-2.5-flash as default fast model for free tier
                model_name = "gemini-2.5-flash"
                
                # Combine system prompt with main prompt if provided
                full_prompt = prompt
                if system_prompt:
                    # In Gemini 1.5 we can pass system_instruction to GenerativeModel
                    model = genai.GenerativeModel(
                        model_name=model_name,
                        system_instruction=system_prompt,
                        generation_config=genai.types.GenerationConfig(
                            temperature=temperature,
                            max_output_tokens=max_tokens
                        )
                    )
                else:
                    model = genai.GenerativeModel(
                        model_name=model_name,
                        generation_config=genai.types.GenerationConfig(
                            temperature=temperature,
                            max_output_tokens=max_tokens
                        )
                    )
                
                response = model.generate_content(full_prompt)
                response_text = response.text
                
            elif provider == "groq":
                # Use llama-3.3-70b-versatile as the standard fast conversational model
                model_name = "llama-3.3-70b-versatile"
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})
                
                chat_completion = self.groq_client.chat.completions.create(
                    messages=messages,
                    model=model_name,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                response_text = chat_completion.choices[0].message.content
                
        except Exception as primary_error:
            # If Gemini fails and Groq is available, fall back automatically
            if provider == "gemini" and self.groq_client:
                print(f"Primary LLM (Gemini) failed: {str(primary_error)}. Falling back to Groq...")
                try:
                    actual_provider = "groq"
                    model_name = "llama-3.3-70b-versatile"
                    messages = []
                    if system_prompt:
                        messages.append({"role": "system", "content": system_prompt})
                    messages.append({"role": "user", "content": prompt})
                    chat_completion = self.groq_client.chat.completions.create(
                        messages=messages,
                        model=model_name,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    response_text = chat_completion.choices[0].message.content
                except Exception as secondary_error:
                    raise RuntimeError(f"Both primary and fallback LLM providers failed. Gemini: {str(primary_error)}. Groq: {str(secondary_error)}")
            else:
                raise primary_error

        latency = time.time() - start_time
        prompt_tokens = self.estimate_tokens(prompt) + (self.estimate_tokens(system_prompt) if system_prompt else 0)
        completion_tokens = self.estimate_tokens(response_text)
        total_tokens = prompt_tokens + completion_tokens
        
        return {
            "text": response_text,
            "provider": actual_provider,
            "latency": latency,
            "tokens": total_tokens
        }

    def generate_json(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.2, max_tokens: int = 1500) -> Dict[str, Any]:
        """Generate structured JSON output and parse it safely, retrying if malformed."""
        json_instruction = "\nIMPORTANT: Your output MUST be valid JSON only. Do not wrap the JSON in markdown code blocks like ```json ... ```, and do not add any conversational text before or after the JSON."
        
        full_system = (system_prompt or "") + json_instruction
        
        # Try up to 3 times to get valid JSON
        for attempt in range(3):
            try:
                res = self.generate(
                    prompt=prompt,
                    system_prompt=full_system,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                text = res["text"].strip()
                
                # Attempt to clean the output of markdown formatting if the model still outputs code blocks
                if text.startswith("```"):
                    # Strip ```json ... ``` or ``` ... ```
                    text = re.sub(r"^```(?:json)?\n", "", text)
                    text = re.sub(r"\n```$", "", text)
                    text = text.strip()
                
                # Strip potential leading/trailing markdown backticks that aren't multiline
                if text.startswith("`") and text.endswith("`"):
                    text = text.strip("`").strip()
                
                # Parse JSON
                try:
                    parsed_data = json.loads(text)
                except json.JSONDecodeError:
                    # Fallback: isolate JSON by finding outermost curly braces
                    start_idx = text.find('{')
                    end_idx = text.rfind('}')
                    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                        cleaned_json = text[start_idx:end_idx+1]
                        parsed_data = json.loads(cleaned_json)
                    else:
                        raise
                
                return {
                    "data": parsed_data,
                    "provider": res["provider"],
                    "latency": res["latency"],
                    "tokens": res["tokens"]
                }
            except (json.JSONDecodeError, Exception) as e:
                if attempt == 2:
                    # Final attempt failed, raise exception
                    raw_text_info = res["text"] if 'res' in locals() and isinstance(res, dict) and "text" in res else "N/A"
                    raise ValueError(f"Failed to generate valid JSON after 3 attempts. Raw text: {raw_text_info}. Error: {str(e)}")
                # Modify prompt slightly to reinforce format on retry
                prompt += "\n\nRetrying: The previous output was invalid JSON. Please ensure your response contains ONLY the raw JSON object matching the requested schema."
                time.sleep(0.5)
        
        raise ValueError("Unknown error in JSON generation.")
