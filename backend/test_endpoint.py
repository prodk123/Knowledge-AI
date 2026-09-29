import requests
import uuid

conversation_id = "34535164-e4d1-4e80-8f8c-6d5a4b30f6f3"
url = f"http://localhost:8000/conversations/{conversation_id}/messages"
# We need to bypass auth or use a token.
# Let's check auth.py to see if we can get a token easily.
