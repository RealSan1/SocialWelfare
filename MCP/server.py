import os
import requests
from dotenv import load_dotenv
from fastmcp import FastMCP
from google import genai
from google.genai import types

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36'
}

load_dotenv('api.env')
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

mcp = FastMCP(name="MCPServer") 

# Ollama GPT-OSS (로컬)
@mcp.tool
def chat_ollama(prompt: str) -> str:
    try:
        resp = requests.post(
            "http://localhost:11434/api/generate",
            json={"model":"gpt-oss:20b","prompt":prompt,"stream":False},
            headers=headers,
            timeout=30
        )
        return resp.json().get("response", "No response")
    except Exception as e:
        return f"Ollama request failed: {e}"

# Google Gemini API
@mcp.tool
def chat_gemini(prompt: str) -> str:
    try:
        client = genai.Client(api_key=GEMINI_KEY)

        grounding_tool = types.Tool(google_search=types.GoogleSearch())
        config = types.GenerateContentConfig(tools=[grounding_tool])

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=config
        )

        text = response.text if response.text else ""
        return text.strip() if text else "(No response)"
    except Exception as e:
        return f"[ERROR] Gemini: {e}"


# 서버 실행
if __name__ == "__main__":
    import sys
    import logging
    logging.basicConfig(level=logging.DEBUG)
    if sys.platform.startswith("win"):
        import asyncio
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    print("=== MCP Server started (stdio mode) ===")
    mcp.run()
