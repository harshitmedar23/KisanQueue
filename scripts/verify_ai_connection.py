"""Verify the configured server-side AI provider without exposing credentials."""
import os
import sys

import requests
from dotenv import load_dotenv


def main():
    load_dotenv()
    provider = os.environ.get("AI_PROVIDER", "openai").strip().lower()
    if provider == "ollama":
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        model = os.environ.get("OLLAMA_MODEL", "llama3.2")
        print("Local Ollama configuration detected.")
        print("Connecting to Ollama...")
        try:
            response = requests.post(
                f"{base_url}/api/chat",
                json={"model": model, "messages": [{"role": "user", "content": "Reply with OK."}], "stream": False},
                timeout=90,
            )
            response.raise_for_status()
            if not response.json().get("message", {}).get("content"):
                print("Ollama returned an empty response.")
                return 1
        except requests.ConnectionError:
            print("Ollama is not running. Start Ollama and try again.")
            return 1
        except requests.Timeout:
            print("Ollama took too long to respond. Please try again.")
            return 1
        except requests.RequestException:
            print("Ollama connection failed. Check the model and local service.")
            return 1
        print("Connection successful.")
        return 0

    if provider == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key or api_key == "your_api_key_here":
            print("GEMINI_API_KEY is not configured. Add it to the .env file.")
            return 1

        try:
            from google import genai
        except ImportError:
            print("The Google GenAI SDK is not installed. Install the project requirements first.")
            return 1

        model = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
        print("Gemini configuration detected.")
        print("Connecting to Gemini...")
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model,
                contents="Reply with OK.",
            )
            if not getattr(response, "text", None):
                print("Gemini returned an empty response.")
                return 1
        except Exception:
            print("Gemini connection failed. Check the API key, model, and network configuration.")
            return 1

        print("Connection successful.")
        return 0

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or api_key == "YOUR_API_KEY_HERE":
        print("OPENAI_API_KEY is not configured. Add it to the .env file.")
        return 1

    try:
        from openai import APIConnectionError, APIError, AuthenticationError, OpenAI, RateLimitError
    except ImportError:
        print("The OpenAI SDK is not installed. Install the project requirements first.")
        return 1

    print("AI API configuration detected.")
    print("Connecting to OpenAI...")
    try:
        client = OpenAI(api_key=api_key)
        client.models.list()
    except AuthenticationError:
        print("OpenAI rejected the API key. Check that it is active and copied correctly.")
        return 1
    except APIConnectionError:
        print("OpenAI connection failed. Check the network or proxy configuration.")
        return 1
    except RateLimitError:
        print("OpenAI rate limit or account quota was reached.")
        return 1
    except APIError:
        print("OpenAI returned an API error. Check the account and project configuration.")
        return 1
    except Exception:
        print("OpenAI connection failed. Check the key, account, and network configuration.")
        return 1

    print("Connection successful.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
