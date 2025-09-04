import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
import pandas as pd
# Load API Key from .env
load_dotenv()
API_KEY = os.environ.get("API_KEY")

# Initialize Gemini client
client = genai.Client(api_key=API_KEY)

# System Prompt
SYSTEM_PROMPT = """
You are movie and series expert and are capable of converting date to day
"""



def ask_gemini(user_message: str) -> str:
    """
    Stateless Gemini call using a merged prompt (system + user).
    Session ID is used only for structural compatibility.
    """
    try:
        
        full_prompt = SYSTEM_PROMPT.strip() + "\n\nUser query: " + user_message.strip()

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[{"parts": [{"text": full_prompt}]}],
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                max_output_tokens=2000
            )
        )

        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            # print(f"Response: {response.candidates[0].content.parts[0].text}")
            return "".join(part.text for part in response.candidates[0].content.parts if part.text)
        else:
            return "No response generated."

    except Exception as e:
        return f"An error occurred: {e}"

# Example usage
def main():
    session_id = "retail_user_1"
    questions = [
        "Is Hamilton Really as Good as Everyone Says? First Time Watching a Musical!! What is the title of the movie here ? Just give me the title of the movie.",
        "FIRST TIME WATCHING K-POP DEMON HUNTERS AND IT LIVED UP TO THE HYPE!! | Movie Reaction What is the title of the movie here ? Just give me the title of the movie.",
        "*FULL METAL JACKET* full on BROKE me.. What is the title of the movie here ? Just give me the title of the movie.",
    ]

    for i, q in enumerate(questions, 1):
        print(f"\nQ{i}: {q}")
        print(f"A{i}: {ask_gemini(q)}")