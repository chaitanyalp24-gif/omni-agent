import os
import google.generativeai as genai
from duckduckgo_search import DDGS
import requests

def web_search(query: str) -> str:
    """Searches the live web for free using DuckDuckGo."""
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=3)]
            if not results:
                return "No search results found."
            
            summary = "Live Web Information Found:\n"
            for r in results:
                summary += f"- Title: {r['title']}\n  Link: {r['href']}\n  Snippet: {r['body']}\n\n"
            return summary
    except Exception as e:
        return f"Web search failed: {str(e)}"

def run_agent_chat(prompt: str, api_key: str) -> str:
    """Processes user chat prompts. Uses live search if requested."""
    if not api_key:
        return "⚠️ Error: Please provide a Gemini API Key in the sidebar to use Chat or Search."
        
    try:
        # Configure the free Gemini cloud engine
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Simple keywords to trigger the web search tool automatically
        search_triggers = ["search", "latest", "news", "weather", "current", "who is", "what is the price"]
        if any(word in prompt.lower() for word in search_triggers):
            search_data = web_search(prompt)
            final_prompt = f"User Question: {prompt}\n\nUse this live web data to answer comprehensively:\n{search_data}"
            response = model.generate_content(final_prompt)
        else:
            response = model.generate_content(prompt)
            
        return response.text
    except Exception as e:
        return f"AI Brain Error: {str(e)}"

def generate_image_url(prompt: str) -> str:
    """Creates a free public URL string to render AI artwork instantly."""
    encoded_prompt = prompt.replace(" ", "%20")
    return f"https://pollinations.ai{encoded_prompt}?width=1024&height=1024&seed=77"

def generate_video_url(prompt: str) -> str:
    """Creates a free video rendering endpoint generation link."""
    encoded_prompt = prompt.replace(" ", "%20")
    # Utilizing free video rendering fallback architecture
    return f"https://pollinations.ai{encoded_prompt}?width=512&height=512&feed=true"
