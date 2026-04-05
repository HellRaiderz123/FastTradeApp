import html
import logging
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.services.llm_service import LLM_MODEL, LLM_PROVIDER, call_llm, is_available

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/simple-ai", tags=["Simple AI"])

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful AI assistant similar to ChatGPT. "
    "Answer clearly, directly, and helpfully. "
    "If the user asks for code, provide working examples."
)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(min_length=1, max_length=8000)


class SimpleChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    history: list[ChatMessage] = Field(default_factory=list)
    system_prompt: str | None = None
    temperature: float = Field(default=0.3, ge=0.0, le=1.5)
    max_tokens: int = Field(default=600, ge=50, le=2000)


def _build_prompt(message: str, history: list[ChatMessage]) -> str:
    if not history:
        return message

    lines: list[str] = []
    for item in history[-10:]:
        role = item.role.capitalize()
        lines.append(f"{role}: {item.content.strip()}")
    lines.append(f"User: {message.strip()}")
    lines.append("Assistant:")
    return "\n".join(lines)


@router.get("/health")
def simple_ai_health() -> dict:
    return {
        "ok": True,
        "provider": LLM_PROVIDER,
        "model": LLM_MODEL,
        "configured": is_available(),
        "chat_endpoint": "/simple-ai/chat",
        "playground": "/simple-ai/playground",
    }


@router.post("/chat")
def simple_ai_chat(req: SimpleChatRequest) -> dict:
    if not is_available():
        raise HTTPException(status_code=503, detail="LLM_API_KEY is not configured")

    prompt = _build_prompt(req.message, req.history)
    answer = call_llm(
        prompt=prompt,
        system_prompt=req.system_prompt or DEFAULT_SYSTEM_PROMPT,
        max_tokens=req.max_tokens,
        temperature=req.temperature,
        timeout=30.0,
    )

    if not answer:
        raise HTTPException(status_code=502, detail="The NVIDIA AI service did not return a response")

    return {
        "ok": True,
        "provider": LLM_PROVIDER,
        "model": LLM_MODEL,
        "answer": answer.strip(),
    }


@router.get("/playground", response_class=HTMLResponse)
def simple_ai_playground() -> str:
    title = html.escape("FastTrade NVIDIA AI Chat")
    return f"""
<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{title}</title>
  <style>
    body {{ font-family: Arial, sans-serif; background: #0f172a; color: #e2e8f0; margin: 0; }}
    .wrap {{ max-width: 900px; margin: 0 auto; padding: 24px; }}
    .card {{ background: #111827; border: 1px solid #334155; border-radius: 14px; padding: 16px; }}
    h1 {{ margin-top: 0; }}
    #messages {{ min-height: 360px; white-space: pre-wrap; }}
    .msg {{ padding: 12px; border-radius: 10px; margin-bottom: 12px; }}
    .user {{ background: #1d4ed8; }}
    .assistant {{ background: #1f2937; }}
    textarea {{ width: 100%; min-height: 90px; border-radius: 10px; padding: 12px; border: 1px solid #475569; background: #020617; color: #e2e8f0; }}
    button {{ margin-top: 12px; background: #22c55e; color: #052e16; border: 0; border-radius: 10px; padding: 10px 16px; font-weight: 700; cursor: pointer; }}
    .muted {{ color: #94a3b8; font-size: 14px; }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <div class=\"card\">
      <h1>🤖 FastTrade NVIDIA AI Chat</h1>
      <p class=\"muted\">Ask anything — this uses your configured NVIDIA-compatible LLM key.</p>
      <div id=\"messages\"></div>
      <textarea id=\"prompt\" placeholder=\"Ask me anything...\"></textarea>
      <br />
      <button onclick=\"sendMessage()\">Send</button>
    </div>
  </div>

  <script>
    const messages = [];
    const container = document.getElementById('messages');
    const promptBox = document.getElementById('prompt');

    function render() {{
      container.innerHTML = messages.map(m => `<div class=\"msg ${{m.role}}\"><strong>${{m.role}}:</strong><br>${{m.text}}</div>`).join('');
    }}

    async function sendMessage() {{
      const text = promptBox.value.trim();
      if (!text) return;
      messages.push({{ role: 'user', text }});
      promptBox.value = '';
      render();

      try {{
        const history = messages.slice(0, -1).map(m => ({{ role: m.role, content: m.text }}));
        const res = await fetch('/simple-ai/chat', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ message: text, history }})
        }});
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Request failed');
        messages.push({{ role: 'assistant', text: data.answer }});
      }} catch (err) {{
        messages.push({{ role: 'assistant', text: 'Error: ' + err.message }});
      }}
      render();
    }}

    promptBox.addEventListener('keydown', (e) => {{
      if (e.key === 'Enter' && !e.shiftKey) {{
        e.preventDefault();
        sendMessage();
      }}
    }});
  </script>
</body>
</html>
"""
