"""Provider-agnostic async AI client for OpenAI and Anthropic."""
from __future__ import annotations
import asyncio
from dataclasses import dataclass
from typing import Literal
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
from bot.config import settings


@dataclass(slots=True)
class AIResult:
    text: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int


class AIError(RuntimeError):
    """A user-safe provider error."""


class AIClient:
    def __init__(self) -> None:
        self.openai = AsyncOpenAI(api_key=settings.openai_api_key, timeout=settings.ai_timeout_seconds) if settings.openai_api_key else None
        self.anthropic = AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=settings.ai_timeout_seconds) if settings.anthropic_api_key else None

    async def generate(self, system: str, user: str, temperature: float = 0.7,
                       provider: Literal["openai", "anthropic"] | None = None,
                       max_tokens: int = 3000) -> AIResult:
        selected = provider or settings.ai_provider
        if selected not in {"openai", "anthropic"}:
            raise AIError("AI provayderi noto‘g‘ri tanlangan.")
        for attempt in range(3):
            try:
                return await asyncio.wait_for(
                    self._request(selected, system, user, temperature, max_tokens),
                    timeout=settings.ai_timeout_seconds + 5,
                )
            except Exception as exc:
                if attempt == 2:
                    raise AIError("AI hozir javob bera olmadi. API kaliti, balans va model sozlamalarini tekshiring.") from exc
                await asyncio.sleep(0.8 * (2 ** attempt))
        raise AIError("AI so‘rovi bajarilmadi.")


    async def close(self) -> None:
        """Close provider HTTP clients during graceful shutdown."""
        if self.openai is not None:
            await self.openai.close()
        if self.anthropic is not None:
            await self.anthropic.close()

    async def _request(self, provider: str, system: str, user: str, temperature: float, max_tokens: int) -> AIResult:
        if provider == "openai":
            if not self.openai:
                raise AIError("OPENAI_API_KEY sozlanmagan.")
            model = settings.openai_model
            request_args = {
                "model": model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            }
            if model.startswith(("gpt-5", "gpt-6")):
                # Newer reasoning-capable Chat Completions models use max_completion_tokens.
                request_args["max_completion_tokens"] = max_tokens
            else:
                request_args["max_tokens"] = max_tokens
                request_args["temperature"] = temperature
            response = await self.openai.chat.completions.create(**request_args)
            text = response.choices[0].message.content or ""
            usage = response.usage
            return AIResult(text, provider, model, usage.prompt_tokens if usage else 0, usage.completion_tokens if usage else 0)
        if not self.anthropic:
            raise AIError("ANTHROPIC_API_KEY sozlanmagan.")
        model = settings.anthropic_model
        response = await self.anthropic.messages.create(
            model=model, max_tokens=max_tokens, temperature=temperature,
            system=system, messages=[{"role": "user", "content": user}],
        )
        text = "\n".join(block.text for block in response.content if getattr(block, "type", "") == "text")
        return AIResult(text, provider, model, response.usage.input_tokens, response.usage.output_tokens)


ai_client = AIClient()
