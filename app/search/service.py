from app.config import get_settings
from app.models import SearchBundle, SearchRequest
from app.search.providers import build_providers, run_providers
from app.search.ranking import score_articles, split_bundle


class NewsSearchService:
    async def search(self, request: SearchRequest) -> SearchBundle:
        settings = get_settings()
        providers = build_providers(settings)
        articles = await run_providers(providers, request)
        scored = score_articles(articles, request.query)
        top_news, deep_context = split_bundle(scored, request.max_results)
        return SearchBundle(query=request.query, top_news=top_news, deep_context=deep_context)

