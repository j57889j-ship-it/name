"""Optional live web research using Tavily; requires a separate API key."""
from __future__ import annotations
import aiohttp
from bot.config import settings


class ResearchService:
    async def search(self, query: str, max_results: int = 6) -> list[dict[str, str]]:
        if not settings.tavily_api_key:
            raise RuntimeError("Jonli research uchun TAVILY_API_KEY sozlanmagan.")
        timeout = aiohttp.ClientTimeout(total=25)
        payload = {"api_key": settings.tavily_api_key, "query": query, "search_depth": "advanced", "max_results": max_results}
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post("https://api.tavily.com/search", json=payload) as response:
                response.raise_for_status()
                data = await response.json()
        return [{"title": item.get("title", ""), "url": item.get("url", ""), "content": item.get("content", "")}
                for item in data.get("results", [])]
