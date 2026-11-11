"""AI business logic, daily quota enforcement, and usage accounting."""
from __future__ import annotations
from bot.ai.client import ai_client, AIResult, AIError
from bot.config import settings


class AIService:
    def __init__(self, repo) -> None:
        self.repo = repo

    async def generate(self, admin_id: int, purpose: str, system: str, user: str,
                       temperature: float = 0.7, provider: str | None = None,
                       max_tokens: int = 3000) -> AIResult:
        usage = await self.repo.ai_usage_today()
        limit = int(await self.repo.get_setting("ai_daily_limit", str(settings.ai_daily_request_limit)))
        if int(usage["requests"]) >= limit:
            raise AIError(f"Kunlik AI limiti tugadi ({limit} ta so‘rov).")
        selected_provider = provider or await self.repo.get_setting("ai_provider", settings.ai_provider)
        result = await ai_client.generate(system, user, temperature, selected_provider, max_tokens)
        if result.provider == "openai":
            input_rate = settings.openai_input_usd_per_mtok
            output_rate = settings.openai_output_usd_per_mtok
        else:
            input_rate = settings.anthropic_input_usd_per_mtok
            output_rate = settings.anthropic_output_usd_per_mtok
        estimated_cost = (result.input_tokens * input_rate + result.output_tokens * output_rate) / 1_000_000
        await self.repo.save_ai_usage(admin_id, result.provider, result.model, purpose,
                                      result.input_tokens, result.output_tokens, estimated_cost)
        await self.repo.log_event("ai_call", admin_id, {"purpose": purpose, "provider": result.provider, "model": result.model})
        return result
