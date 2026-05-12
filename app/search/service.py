from app.config import get_settings
from app.models import SearchBundle, SearchRequest
from app.search.providers import build_providers, filter_paywalled, run_providers
from app.search.ranking import score_articles, split_bundle


class NewsSearchService:
    async def search(self, request: SearchRequest) -> SearchBundle:
        settings = get_settings()
        providers = build_providers(settings)
        articles = await run_providers(providers, request)
        articles = filter_paywalled(articles)
        scored = score_articles(articles, request.query)
        top_news, deep_context = split_bundle(scored, request.max_results)
        return SearchBundle(query=request.query, top_news=top_news, deep_context=deep_context)

    async def search_trending(self) -> SearchBundle:
        """Broad 3-day search for trending news, with paywall filtering."""
        settings = get_settings()
        request = SearchRequest(
            query=settings.trending_query,
            language=settings.default_language,
            region=settings.default_region,
            max_results=settings.default_max_news_results,
            lookback_days=settings.trending_lookback_days,
        )
        providers = build_providers(settings)
        articles = await run_providers(providers, request)
        articles = filter_paywalled(articles)
        scored = score_articles(articles, request.query)
        top_news, deep_context = split_bundle(scored, request.max_results)
        return SearchBundle(query=request.query, top_news=top_news, deep_context=deep_context)
