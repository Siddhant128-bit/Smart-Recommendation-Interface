from google import genai
from dotenv import load_dotenv
import os
from google.genai import types
import pandas as pd
import json

# Load API Key from .env
load_dotenv()
API_KEY = os.environ.get("API_KEY_2")

# Initialize Gemini client
client = genai.Client(api_key=API_KEY)

HISTORY_FILE = "conversation_history.json"


def load_data_for_youtuber(username):
    """Load the user's dataset."""
    data = pd.read_csv(f'User/{username}/{username}.csv')
    return data 


def initialize_chatbot(username):
    """
    Creates system-like prompt and loads previous conversation history if available.
    """
    user_data = load_data_for_youtuber(username)
    if "embeddings" in user_data.columns:
        user_data = user_data.drop('embeddings', axis=1)

    SYSTEM_PROMPT = f"""
    You are a friendly chatbot, Your name is Miss Sri. 
    A Friendly, sensitive, Professional and extremely realistic bot who replies like normal humans do, 
    You are a blend of Sarcastic Chandler and Caring Monica developed by Mr. Siddhant Sharma. 
    If asked about developer, say: He is an AI Engineer, Lecturer and part-time entrepreneur.
    
    They shouldn't be able to differentiate whether you are a bot or human.
    You help people understand their own YouTube reaction channel. 
    Total subs: ~250-290K, and views >70k is generally good.
    
    You have structured access to the channel's dataset (videos, upload dates, trend scores, summaries, genre, views). 
    Do NOT make up answers: always rely on provided data slices or summaries.
    Your job: analyze which types of movies/videos do well or badly based on trends, views, and genre.
    
    If the question is too specific (like exact future views), give only rough, scaled-down estimates (estimate/10) 
    and remind user to check the 'view predictor' tab for details.

    Be short, sweet, and personal with {username}. 
    Don't give long unrelated answers and don't hallucinate.
    """

    # Load existing history if available
    history_path = f'User/{username}/{HISTORY_FILE}'
    if os.path.exists(history_path):
        with open(history_path, "r") as f:
            history = json.load(f)
    else:
        history = [{"role": "user", "parts": [{"text": SYSTEM_PROMPT}]}]

    return SYSTEM_PROMPT, history, user_data


def save_history(username, history):
    """Save conversation history to JSON file."""
    with open(f'User/{username}/{HISTORY_FILE}', "w") as f:
        json.dump(history, f, indent=2)


def summarize_user_data(user_data: pd.DataFrame) -> dict:
    """Create a compact summary of the channel dataset."""
    summary = {
        "total_videos": len(user_data),
        "avg_views": round(user_data["Views"].mean(), 2),
        "median_views": round(user_data["Views"].median(), 2),
        "avg_trend": round(user_data["trend_score"].mean(), 2),
        "top_genres": user_data["genre"].value_counts().head(5).to_dict(),
        "best_videos": user_data.nlargest(3, "Views")[["Video title", "Views", "genre"]].to_dict(orient="records"),
        "worst_videos": user_data.nsmallest(3, "Views")[["Video title", "Views", "genre"]].to_dict(orient="records"),
    }
    return summary


def ask_gemini(user_message: str, history: list, username: str, user_data: pd.DataFrame) -> str:
    """
    Hybrid approach:
    - Always provide a global summary (aggregates, top/bottom videos, genre trends).
    - If user mentions specific genres/topics, also provide a filtered slice of relevant rows.
    """
    try:
        # Build global summary
        summary_context = json.dumps(summarize_user_data(user_data), indent=2)

        # Detect intent for slicing
        trigger_words = ["movie", "upload", "video", "genre", "audience", "trend"]
        relevant_context = ""
        if any(word in user_message.lower() for word in trigger_words):
            filtered = user_data

            # Try filtering for keywords in title or genre
            keywords = user_message.lower().split()
            for kw in keywords:
                matches = user_data[
                    user_data["Video title"].str.contains(kw, case=False, na=False) |
                    user_data["genre"].str.contains(kw, case=False, na=False)
                ]
                if not matches.empty:
                    filtered = matches
                    break

            # Safety check: don’t blow tokens
            preview = filtered.head(10).to_dict(orient="records")
            relevant_context = f"\n\nRelevant video samples:\n{json.dumps(preview, indent=2)}"

        # Inject into conversation
        extra_context = f"\n\nHere is your channel summary:\n{summary_context}{relevant_context}"
        history.append({"role": "user", "parts": [{"text": user_message + extra_context}]})

        # Call Gemini
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=history,
            config=types.GenerateContentConfig(max_output_tokens=2000)
        )

        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            bot_reply = "".join(
                part.text for part in response.candidates[0].content.parts if part.text
            )
            # Save reply in history
            history.append({"role": "model", "parts": [{"text": bot_reply}]})
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
