"""Bubbles response contract: formal, warm, skimmable and consistent."""
from __future__ import annotations
import re

def normalize_response(text:str)->str:
    s=str(text or "").strip()
    s=re.sub(r"\n{3,}","\n\n",s)
    if not s: return "I’m here with you. Tell me what you’d like help with."
    # Preserve intentional markdown while nudging legacy one-paragraph answers into a readable shape.
    if "\n" not in s:
        parts=re.split(r"(?<=[.!?])\s+(?=[A-Z])",s)
        if len(parts)>=3:
            return "\n\n".join([" ".join(parts[:2]), "\n".join(f"• {p}" for p in parts[2:])])
    return s

def response_style_instruction()->str:
    return """BUBBLES RESPONSE STYLE:
- Write like a polished personal health companion: calm, warm, feminine, sober and professional.
- Prefer a short opening followed by clear sections.
- Use markdown headings only when useful: **What I’m noticing**, **What you can do now**, **When to get help**, **A question for you**.
- Use bullets for multiple actions or observations.
- Never use a wall of text.
- Do not overuse emojis; at most one subtle emoji when appropriate.
- Never use diagnosis-like labels unless they are explicitly documented by a clinician and clearly attributed.
- Keep urgent safety guidance direct and prominent."""
