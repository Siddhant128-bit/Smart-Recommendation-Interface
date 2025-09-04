from google import genai
from dotenv import load_dotenv
import os
from google.genai import types
import pandas as pd
import json

# Load API Key from .env
load_dotenv()

API_KEY = os.environ.get("API_KEY_2")

# API_KEY = os.environ.get("API_KEY")

# Initialize Gemini client
client = genai.Client(api_key=API_KEY)

HISTORY_FILE = "conversation_history.json"


def load_data_for_youtuber(username):
    data = pd.read_csv(f'User/{username}/{username}.csv')
    return data 


def initialize_chatbot(username):
    """
    Creates system-like prompt and loads previous conversation history if available.
    """
    user_data = load_data_for_youtuber(username)
    user_data = user_data.drop('embeddings', axis=1)

    SYSTEM_PROMPT = f"""
    You are a friendly chatbot, Your name is Miss Sri. 
    A Friendly, sensitive, Professional and extremely realistic bot who replies like normal humans do, You are a blend of Sarcastic Chandler and Caring Monica
    developed by Mr. Siddhant Sharma. 
    if about developer asked tell them He is an AI Engineer, Lecturer and part time entrepreneur
    They shouldn't be able to differentiate weather you are a bot or human.
    You help people understand their own YouTube reaction channel. 
    Take into consideration that for now the total subscription of youtuber is 250-290K and views > 70k is generally good.
    You have structured access to the channel's dataset (videos, upload dates, trend scores, summaries, genre and views). 
    Do NOT make up answers: always rely on provided data slices when given.
    Your job is to look at title of video, trend score, summaries, genre and based on that there are different views obtained by the channel 
    Analyze that upto your abilities reflect which kind of movies do well which kind of movies does bad and based on that answer queries form user.
    Do analytics as told my users.
    If the question is too specific (like exact future views), give only rough, scaled-down estimates (your estimate/10) and 
    remind user to check the 'view predictor' tab for details.

    Be short, sweet, and personal with {username} Don't give long unrelated answers and don't hellucinate.
    """

    # Load existing history if available
    history_path = f'User/{username}/{HISTORY_FILE}'
    if os.path.exists(history_path):
        with open(history_path, "r") as f:
            history = json.load(f)
    else:
        # Start new history with system prompt as first "user" message
        history = [{"role": "user", "parts": [{"text": SYSTEM_PROMPT}]}]

    return SYSTEM_PROMPT, history, user_data



def save_history(username,history):
    """Save conversation history to JSON file."""
    with open(f'User/{username}/{HISTORY_FILE}', "w") as f:
        json.dump(history, f, indent=2)


def ask_gemini(user_message: str, history: list, username: str, user_data: pd.DataFrame) -> str:
    """
    Stateful Gemini call: appends user input & assistant response to conversation history,
    and saves conversation after each exchange. Injects only relevant CSV slices if needed.
    """
    try:
        # If the user asks about movies/uploads, pass only relevant dataframe slice
        extra_context = ""
        trigger_words = ["movie", "upload", "video", "genre", "audience", "trend"]
        if any(word in user_message.lower() for word in trigger_words):
            # Give only first few rows for context, not full CSV
            preview = user_data.head(10).to_string(index=False)
            extra_context = f"\n\nHere is a sample of the channel data you can use:\n{preview}"

        # Add user message (+ extra context if needed)
        history.append({"role": "user", "parts": [{"text": user_message + extra_context}]})

        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=history,
            config=types.GenerateContentConfig(
                max_output_tokens=2000
            )
        )

        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            bot_reply = "".join(part.text for part in response.candidates[0].content.parts if part.text)
            # Save bot reply
            history.append({"role": "model", "parts": [{"text": bot_reply}]})
            
            # Persist updated history
            save_history(username, history)
            
            return bot_reply
        else:
            return "No response generated."

    except Exception as e:
        return f"An error occurred: {e}"

if __name__ == '__main__':
    username = 'vkunia'
    system_prompt, history, user_data = initialize_chatbot(username)

    print(ask_gemini("How does my channel do in war movies ?", history, username, user_data))

