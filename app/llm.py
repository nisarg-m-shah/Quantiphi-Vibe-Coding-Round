from openai import OpenAI, RateLimitError, AuthenticationError, NotFoundError
from . import config
from .tones import TONES

client = OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL)


def stream_reply(history, tone):
    # Tone becomes the system message, built on the server.
    messages = [{"role": "system", "content": TONES[tone]}] + history
    stream = client.chat.completions.create(model=config.LLM_MODEL, messages=messages, stream=True)
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content  # reasoning models may send empty chunks first
        if delta:
            yield delta


def friendly_error(e):
    if isinstance(e, RateLimitError):
        return "Rate limited by the AI provider. Wait a moment and retry."
    if isinstance(e, AuthenticationError):
        return "AI provider rejected the API key."
    if isinstance(e, NotFoundError):
        return "Model not found. Check LLM_MODEL in .env."
    return "The AI provider returned an error. Please try again."