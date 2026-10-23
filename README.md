cat > README.md <<'EOF'
# AI Chat Assistant
FastAPI + MongoDB chat app with streamed responses, a history sidebar and a tone toggle.

## Features
- Chat bubbles with character-by-character streamed responses
- Conversation history sidebar stored in MongoDB
- Tone toggle (Professional / Casual / Concise), applied on the backend as the system instruction
- Extras: sanitised Markdown rendering, Regenerate last response

## Stack
Python, FastAPI, PyMongo, OpenAI SDK, plain HTML/CSS/JS

## LLM provider
Uses the OpenAI SDK against Groq's OpenAI-compatible endpoint with the open-weight
`openai/gpt-oss-120b` model, because no paid OpenAI/Claude credits were available.
Switch providers by changing LLM_API_KEY, LLM_BASE_URL and LLM_MODEL in .env.

## Setup
1. pip install -r requirements.txt
2. Copy .env.example to .env and fill in your values (needs a running MongoDB)
3. python3 -m uvicorn app.main:app --reload
4. Open http://127.0.0.1:8000

## Known limitations
No authentication (all visitors share one history), free-tier rate limits apply,
responses are saved only after a stream completes.
EOF