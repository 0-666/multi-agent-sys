# utils/llm_client.py (or initialize in each agent that needs it)
import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env file or environment variables.")

genai.configure(api_key=GEMINI_API_KEY)

# Using a specific model, e.g., gemini-1.5-flash
# Using gemini-pro as it's generally available and good for text tasks.
# You might want to use gemini-1.5-flash for multimodal if you pass PDF bytes directly.
# For pure text classification/extraction, gemini-pro or gemini-1.0-pro is fine.
# Let's use gemini-1.5-flash as it's versatile.
llm_model_name = "gemini-1.5-flash-latest" # or "gemini-pro"

def get_gemini_model():
    # For more complex scenarios, you might want a Chat session
    # For one-off classification/extraction, generate_content is fine
    return genai.GenerativeModel(llm_model_name)

def generate_text_gemini(prompt: str, model=None) -> str:
    if model is None:
        model = get_gemini_model()
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"Gemini API Error Details: {e.response}")
        # Check for blocked content
        if response and response.prompt_feedback and response.prompt_feedback.block_reason:
            print(f"Prompt blocked: {response.prompt_feedback.block_reason_message}")
            return f"Error: Content blocked by API - {response.prompt_feedback.block_reason_message}"
        return "Error: Could not get response from LLM."


# Example of how Gemini can take PDF bytes (from your provided example)
def summarize_pdf_bytes_gemini(pdf_bytes: bytes, prompt: str = "Summarize this document", model=None) -> str:
    if model is None:
        model = get_gemini_model() # Ensure this model supports multimodal input if you use it.
                                   # gemini-1.5-flash-latest should work.
    try:
        pdf_part = {"mime_type": "application/pdf", "data": pdf_bytes}
        response = model.generate_content([pdf_part, prompt])
        return response.text
    except Exception as e:
        print(f"Error calling Gemini API with PDF: {e}")
        return "Error: Could not get PDF summary from LLM."