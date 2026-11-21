"""Step 1: talk to qwen2.5 through Ollama. Run: python step1_hello.py"""
import requests

URL = "http://localhost:11434/v1/chat/completions"

body = {"model": "qwen2.5:7b",
        "messages": [{"role": "user", "content": "Say hello to a train passenger in Hinglish."}]}
resp = requests.post(URL, json=body, timeout=120)
print(resp.json()["choices"][0]["message"]["content"])
