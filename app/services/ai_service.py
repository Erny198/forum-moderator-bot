from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Optional

from app.config import config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты анализируешь сообщения в закрытой Telegram-группе Форум-группы предпринимателей.

Твоя задача — определить, содержит ли сообщение личное обещание или обязательство участника что-то сделать.

Обещанием считается сообщение, где участник явно или косвенно берёт на себя действие в будущем.

Примеры обещаний:
- Я обещаю до пятницы отправить документ.
- Беру на себя поговорить с партнёром.
- До следующего форума сделаю план.
- На этой неделе схожу к врачу.
- Я подготовлю презентацию.
- К следующей встрече разберусь с этим вопросом.

Не считай обещанием:
- общие рассуждения;
- советы другим участникам;
- вопросы;
- шутки;
- обсуждение чужих задач;
- сообщения без личного обязательства;
- фразы типа "надо бы сделать", если участник не берёт это на себя;
- фразы, где человек говорит о чужом действии, а не о своём.

Верни строго JSON без пояснений, markdown и дополнительного текста.

Формат:
{
  "is_commitment": true или false,
  "commitment_text": "кратко переформулированное обещание или null",
  "deadline_text": "дедлайн из текста или null",
  "confidence": число от 0 до 1
}"""


@dataclass
class AIResult:
    is_commitment: bool
    commitment_text: Optional[str]
    deadline_text: Optional[str]
    confidence: float

    @property
    def should_save(self) -> bool:
        return self.is_commitment and self.confidence >= 0.7


def _parse_response(raw: str) -> AIResult:
    """Parse JSON from AI response."""
    # Strip markdown code blocks if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        text = "\n".join(lines).strip()

    data = json.loads(text)
    return AIResult(
        is_commitment=bool(data.get("is_commitment", False)),
        commitment_text=data.get("commitment_text") or None,
        deadline_text=data.get("deadline_text") or None,
        confidence=float(data.get("confidence", 0.0)),
    )


async def analyze_message_openai(text: str) -> Optional[AIResult]:
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=config.openai_api_key)
        response = await client.chat.completions.create(
            model=config.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0,
            max_tokens=256,
        )
        raw = response.choices[0].message.content or ""
        return _parse_response(raw)
    except Exception as exc:
        logger.error("OpenAI API error: %s", exc, exc_info=True)
        return None


async def analyze_message_anthropic(text: str) -> Optional[AIResult]:
    try:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)
        message = await client.messages.create(
            model=config.anthropic_model,
            max_tokens=256,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
        )
        raw = message.content[0].text if message.content else ""
        return _parse_response(raw)
    except Exception as exc:
        logger.error("Anthropic API error: %s", exc, exc_info=True)
        return None


async def analyze_message(text: str) -> Optional[AIResult]:
    """Analyze a message and return AIResult or None on error."""
    if not text or not text.strip():
        return None

    if config.ai_provider == "anthropic":
        return await analyze_message_anthropic(text)
    else:
        return await analyze_message_openai(text)
