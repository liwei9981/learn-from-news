from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path

from telegram import BotCommand, CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, TelegramError, TimedOut
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from app.config import get_settings
from app.learning.package import build_notebook_package
from app.linkedin import generate_linkedin_post
from app.models import NotebookResult, SearchRequest
from app.notebooklm import NotebookLMService
from app.profile import summarize_article_for_telegram
from app.search.service import NewsSearchService

LOG_DIR = Path(".local/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
file_handler = RotatingFileHandler(LOG_DIR / "bot.log", maxBytes=1_000_000, backupCount=3)
file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s:%(name)s:%(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(), file_handler])
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

UPLOAD_TIMEOUTS = {
    "connect_timeout": 30,
    "read_timeout": 600,
    "write_timeout": 600,
    "pool_timeout": 30,
}
DELIVERY_RETRIES = 3


@dataclass(frozen=True)
class DeliveryItem:
    label: str
    path: Path | None
    kind: str
    caption: str
    title: str | None = None


MAIN_MENU = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("Search News", callback_data="search")],
        [InlineKeyboardButton("Personalized 7-Day Brief", callback_data="topic:AI technology Singapore China")],
    ]
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "What would you like to learn from today?",
        reply_markup=MAIN_MENU,
    )


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["awaiting_search"] = True
    await update.effective_message.reply_text("Type a keyword or topic in English. Example: AI chips")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    try:
        await query.answer()
    except BadRequest as exc:
        if "Query is too old" in str(exc) or "query id is invalid" in str(exc):
            logger.info("Ignoring stale Telegram callback query: %s", exc)
        else:
            raise
    data = query.data or ""
    if data == "search":
        context.user_data["awaiting_search"] = True
        await query.edit_message_text("Type a keyword or topic in English. Example: AI chips")
        return
    if data.startswith("topic:"):
        await _run_search(query.message, context, data.removeprefix("topic:"))
        return
    if data.startswith("select:"):
        index = int(data.removeprefix("select:"))
        articles = context.user_data.get("articles", [])
        if index >= len(articles):
            await query.edit_message_text("That article is no longer available. Please search again.", reply_markup=MAIN_MENU)
            return
        context.user_data["selected_article"] = articles[index]
        await _show_article_actions(query.message, articles[index])
        return
    if data == "learn":
        await _generate_learning_package(query.message, context)
        return
    if data.startswith("linkedin:"):
        angle = data.removeprefix("linkedin:")
        article = context.user_data.get("selected_article")
        if not article:
            await query.edit_message_text("Please select an article first.", reply_markup=MAIN_MENU)
            return
        infographic_path = context.user_data.get("notebooklm_infographic_path")
        post = generate_linkedin_post(article, angle=angle, infographic_available=bool(infographic_path))
        await query.message.reply_text(
            post.text,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Copy Post Text",
                            copy_text=CopyTextButton(text=post.text),
                        )
                    ],
                    [InlineKeyboardButton("Open LinkedIn", url=post.share_url)],
                    [
                        InlineKeyboardButton("More Policy-Oriented", callback_data="linkedin:policy"),
                        InlineKeyboardButton("More Technical", callback_data="linkedin:technical"),
                    ],
                    [InlineKeyboardButton("Start Over", callback_data="menu")],
                ]
            ),
        )
        if infographic_path and Path(infographic_path).exists():
            path = Path(infographic_path)
            await query.message.reply_document(
                document=path,
                filename=path.name,
                caption="Attach this NotebookLM infographic to the LinkedIn post.",
                **UPLOAD_TIMEOUTS,
            )
        return
    if data == "article_actions":
        article = context.user_data.get("selected_article")
        if not article:
            await query.edit_message_text("Please select an article first.", reply_markup=MAIN_MENU)
            return
        await _show_article_actions(query.message, article)
        return
    if data == "menu":
        await query.edit_message_text("What would you like to learn from today?", reply_markup=MAIN_MENU)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.pop("awaiting_search", False):
        await _run_search(update.effective_message, context, update.effective_message.text)
        return
    await update.effective_message.reply_text("Use Search News or Personalized 7-Day Brief to begin.", reply_markup=MAIN_MENU)


async def _run_search(message, context: ContextTypes.DEFAULT_TYPE, topic: str) -> None:
    await message.reply_text(f"Searching the past 7 days for: {topic}")
    settings = get_settings()
    bundle = await NewsSearchService().search(
        SearchRequest(
            query=topic,
            language=settings.default_language,
            region=settings.default_region,
            max_results=settings.default_max_news_results,
            lookback_days=settings.default_lookback_days,
        )
    )
    combined = [*bundle.top_news, *bundle.deep_context]
    articles = [item.article for item in combined]
    context.user_data["articles"] = articles
    if not articles:
        await message.reply_text("No results found. Try another keyword.", reply_markup=MAIN_MENU)
        return
    buttons = [
        [InlineKeyboardButton(f"{idx + 1}. {article.title[:54]}", callback_data=f"select:{idx}")]
        for idx, article in enumerate(articles[:10])
    ]
    buttons.append([InlineKeyboardButton("Start Over", callback_data="menu")])
    await message.reply_text(
        "Top 7-day results, ranked for your AI, technology, public-sector, and China-Singapore interests:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def _show_article_actions(message, article) -> None:
    summary = summarize_article_for_telegram(article.title, article.summary)
    text = (
        f"{article.title}\n\n"
        f"Source: {article.source}\n\n"
        f"Summary: {summary}\n\n"
        f"Link: {article.url}"
    )
    await message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Generate NotebookLM Learning Pack", callback_data="learn")],
                [InlineKeyboardButton("Start Over", callback_data="menu")],
            ]
        ),
    )


async def _generate_learning_package(message, context: ContextTypes.DEFAULT_TYPE) -> None:
    article = context.user_data.get("selected_article")
    articles = context.user_data.get("articles", [])
    if not article:
        await message.reply_text("Please select an article first.", reply_markup=MAIN_MENU)
        return
    related = [candidate for candidate in articles if str(candidate.url) != str(article.url)][:8]
    package = build_notebook_package(article, related)
    settings = get_settings()
    context.user_data.pop("notebooklm_infographic_path", None)
    await message.reply_text(
        "NotebookLM generation has started. The podcast, audio brief, and infographic often take 10-15 minutes. "
        "I will send a progress update every 5 minutes while this is running."
    )
    progress_task = asyncio.create_task(
        _send_notebooklm_progress(message, settings.notebooklm_progress_interval_seconds)
    )
    try:
        result = await NotebookLMService().create_learning_notebook(package)
    finally:
        progress_task.cancel()
    await message.reply_text(
        "NotebookLM learning pack is ready. Sending the infographic, audio brief, and podcast now.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Open NotebookLM", url=result.notebook_url or "https://notebooklm.google.com")]]
        ),
    )

    if result.infographic_path and Path(result.infographic_path).exists():
        context.user_data["notebooklm_infographic_path"] = str(Path(result.infographic_path).absolute())

    sent, failed = await _deliver_learning_package(context, message.chat_id, result)
    status = f"Done. Sent: {', '.join(sent) if sent else 'none'}."
    if failed:
        status += f"\nNot sent to Telegram: {', '.join(failed)}. The files are still saved in Output files."
    await message.reply_text(
        status,
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Open NotebookLM", url=result.notebook_url or "https://notebooklm.google.com")],
                [InlineKeyboardButton("Create LinkedIn Post", callback_data="linkedin:balanced")],
                [InlineKeyboardButton("Start Over", callback_data="menu")],
            ]
        ),
    )


def _build_delivery_items(result: NotebookResult) -> list[DeliveryItem]:
    return [
        DeliveryItem(
            label="infographic",
            path=Path(result.infographic_path).absolute() if result.infographic_path else None,
            kind="photo",
            caption="NotebookLM infographic.",
        ),
        DeliveryItem(
            label="audio brief",
            path=Path(result.audio_brief_path).absolute() if result.audio_brief_path else None,
            kind="audio",
            caption="NotebookLM audio brief.",
            title="NotebookLM audio brief",
        ),
        DeliveryItem(
            label="podcast",
            path=Path(result.audio_path).absolute() if result.audio_path else None,
            kind="audio",
            caption="NotebookLM podcast / Audio Overview.",
            title="NotebookLM podcast",
        ),
    ]


async def _deliver_learning_package(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    result: NotebookResult,
) -> tuple[list[str], list[str]]:
    sent: list[str] = []
    missing: list[str] = []
    pending: list[DeliveryItem] = []

    for item in _build_delivery_items(result):
        if not item.path or not item.path.exists():
            logger.warning("Delivery file for %s is missing: %s", item.label, item.path)
            missing.append(item.label)
            continue
        pending.append(item)

    failed: list[str] = []
    for attempt in range(1, DELIVERY_RETRIES + 1):
        retry: list[DeliveryItem] = []
        for item in pending:
            if await _send_delivery_item(context, chat_id, item):
                sent.append(item.label)
            else:
                retry.append(item)

        if not retry:
            failed = []
            break

        failed = [item.label for item in retry]
        if attempt < DELIVERY_RETRIES:
            logger.warning("Delivery attempt %d/%d failed for: %s", attempt, DELIVERY_RETRIES, ", ".join(failed))
            await asyncio.sleep(5)
        pending = retry

    return sent, [*missing, *failed]


async def _send_delivery_item(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    item: DeliveryItem,
) -> bool:
    if not item.path:
        return False

    if item.kind == "photo":
        return await _send_infographic(context, chat_id, item.path, item.caption)
    if item.kind == "audio":
        return await _send_audio_file(context, chat_id, item.path, item.caption, item.title)
    logger.warning("Unsupported delivery item type for %s: %s", item.label, item.kind)
    return False


async def _send_infographic(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    path: Path,
    caption: str,
) -> bool:
    try:
        logger.info("Sending NotebookLM infographic from %s", path)
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=path,
            filename=path.name,
            caption=caption,
            **UPLOAD_TIMEOUTS,
        )
        return True
    except (TelegramError, OSError) as exc:
        logger.warning("Failed to send infographic as photo: %s: %s", type(exc).__name__, exc)

    try:
        await context.bot.send_document(
            chat_id=chat_id,
            document=path,
            filename=path.name,
            caption=caption,
            **UPLOAD_TIMEOUTS,
        )
        return True
    except (TelegramError, OSError) as exc:
        logger.warning("Failed to send infographic as document: %s: %s", type(exc).__name__, exc)
        return False


async def _send_audio_file(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    path: Path,
    caption: str,
    title: str | None,
) -> bool:
    try:
        logger.info("Sending audio file from %s", path)
        await context.bot.send_audio(
            chat_id=chat_id,
            audio=path,
            filename=path.name,
            title=title,
            caption=caption,
            **UPLOAD_TIMEOUTS,
        )
        return True
    except TimedOut as exc:
        logger.warning("Timed out sending audio %s, retrying as document: %s", path, exc)
    except (TelegramError, OSError) as exc:
        logger.warning("Failed to send audio %s, retrying as document: %s: %s", path, type(exc).__name__, exc)

    try:
        await context.bot.send_document(
            chat_id=chat_id,
            document=path,
            filename=path.name,
            caption=caption,
            **UPLOAD_TIMEOUTS,
        )
        return True
    except (TelegramError, OSError) as exc:
        logger.warning("Failed to send audio document %s: %s: %s", path, type(exc).__name__, exc)
        return False


async def _send_notebooklm_progress(message, interval_seconds: int) -> None:
    elapsed = 0
    try:
        while True:
            await asyncio.sleep(interval_seconds)
            elapsed += interval_seconds
            minutes = elapsed // 60
            await message.reply_text(
                f"Still working in NotebookLM. Elapsed time: about {minutes} minutes. "
                "Podcast, audio brief, and infographic generation can take 10-15 minutes, especially with multiple sources."
            )
    except asyncio.CancelledError:
        return


async def _set_bot_commands(application: Application) -> None:
    await application.bot.set_my_commands(
        [
            BotCommand("start", "Open the learning menu"),
            BotCommand("search", "Search news by keyword"),
        ]
    )


def main() -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required. Add it to .env.")
    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .connect_timeout(15)
        .read_timeout(120)
        .write_timeout(300)
        .pool_timeout(30)
        .post_init(_set_bot_commands)
        .build()
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.run_polling()


if __name__ == "__main__":
    main()
