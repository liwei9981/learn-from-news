import asyncio
from app.search.service import NewsSearchService
from app.models import SearchRequest
from app.config import get_settings

async def test():
    settings = get_settings()
    service = NewsSearchService()
    request = SearchRequest(
        query="AI technology Singapore China",
        language="en",
        region="US",
        max_results=5,
        lookback_days=7
    )
    print(f"Testing search for: {request.query}")
    bundle = await service.search(request)
    print(f"Found {len(bundle.top_news)} top news and {len(bundle.deep_context)} deep context articles.")
    for idx, item in enumerate(bundle.top_news):
        print(f"{idx+1}. {item.article.title} ({item.article.source})")

if __name__ == "__main__":
    asyncio.run(test())
