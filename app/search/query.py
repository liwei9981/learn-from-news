TRUSTED_MEDIA_DOMAINS = [
    "reuters.com",
    "apnews.com",
    "bbc.com",
    "cnn.com",
    "ft.com",
    "economist.com",
    "bloomberg.com",
    "cnbc.com",
    "techcrunch.com",
    "theverge.com",
    "wired.com",
    "technologyreview.com",
]

DEEP_CONTEXT_DOMAINS = [
    "brookings.edu",
    "rand.org",
    "csis.org",
    "oecd.org",
    "imf.org",
    "worldbank.org",
    "arxiv.org",
    "ssrn.com",
    "semianalysis.com",
    "stratechery.com",
    "substack.com",
    "medium.com",
]


def expand_query(topic: str) -> list[str]:
    cleaned = " ".join(topic.strip().split())
    if not cleaned:
        return []
    return [
        cleaned,
        f"{cleaned} latest news",
        f"{cleaned} analysis",
        f"{cleaned} explainer",
        f"{cleaned} policy regulation",
        f"{cleaned} market impact",
    ]


def trusted_site_queries(topic: str) -> list[str]:
    return [f"{topic} site:{domain}" for domain in TRUSTED_MEDIA_DOMAINS]


def deep_context_queries(topic: str) -> list[str]:
    return [f"{topic} site:{domain}" for domain in DEEP_CONTEXT_DOMAINS]

