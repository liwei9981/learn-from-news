from fastapi import FastAPI

from app.linkedin import generate_linkedin_post
from app.models import Article, SearchBundle, SearchRequest
from app.search.service import NewsSearchService

app = FastAPI(title="Learn from News")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/search", response_model=SearchBundle)
async def search_news(request: SearchRequest) -> SearchBundle:
    return await NewsSearchService().search(request)


@app.post("/linkedin")
async def linkedin_post(article: Article, angle: str = "balanced"):
    return generate_linkedin_post(article, angle)

