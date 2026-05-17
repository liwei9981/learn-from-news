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
from app.learning.points import extract_learning_points
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
MAX_LEARNING_POINTS_SELECTED = 2


@dataclass(frozen=True)
class DeliveryItem:
    label: str
    path: Path | None
    kind: str
    caption: str
    title: str | None = None


MAIN_MENU = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("🔍 Search News", callback_data="search")],
        [InlineKeyboardButton("📈 Trending Now", callback_data="trending")],
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

    if data == "trending":
        await _run_trending_search(query.message, context)
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
        await _start_learning_point_selection(query.message, context)
        return

    if data.startswith("lp_toggle:"):
        index = int(data.removeprefix("lp_toggle:"))
        await _toggle_learning_point(query, context, index)
        return

    if data == "lp_confirm":
        await _confirm_learning_points(query.message, context)
        return

    if data == "linkedin":
        await _send_linkedin_post(query.message, context)
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
        return

    if data == "stop":
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("Session ended. Type /start to begin again.")
        return


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.pop("awaiting_search", False):
        await _run_search(update.effective_message, context, update.effective_message.text)
        return
    await update.effective_message.reply_text(
        "Use Search News or Trending Now to begin.", reply_markup=MAIN_MENU
    )


# ── Search ────────────────────────────────────────────────────────────────────

async def _run_search(message, context: ContextTypes.DEFAULT_TYPE, topic: str) -> None:
    await message.reply_text(f"Searching the past 3 days for: {topic}")
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
    await _display_article_list(message, context, bundle, label=f"Top results for \"{topic}\":")


async def _run_trending_search(message, context: ContextTypes.DEFAULT_TYPE) -> None:
    await message.reply_text("Fetching trending news from the past 3 days...")
    bundle = await NewsSearchService().search_trending()
    combined = [*bundle.top_news, *bundle.deep_context]
    if not combined:
        await message.reply_text("No trending results found right now. Try searching by keyword.", reply_markup=MAIN_MENU)
        return
    await _display_article_list(message, context, bundle, label="📈 Trending now — top stories from the past 3 days:")


async def _display_article_list(message, context: ContextTypes.DEFAULT_TYPE, bundle, label: str) -> None:
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
    await message.reply_text(label, reply_markup=InlineKeyboardMarkup(buttons))


# ── Article actions ───────────────────────────────────────────────────────────

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
                [InlineKeyboardButton("🎓 Learning Points", callback_data="learn")],
                [InlineKeyboardButton("Start Over", callback_data="menu")],
            ]
        ),
    )


# ── Learning point selection ──────────────────────────────────────────────────

async def _start_learning_point_selection(message, context: ContextTypes.DEFAULT_TYPE) -> None:
    article = context.user_data.get("selected_article")
    if not article:
        await message.reply_text("Please select an article first.", reply_markup=MAIN_MENU)
        return

    await message.reply_text("Analysing article to identify key learning points...")
    settings = get_settings()
    points = await extract_learning_points(article, settings.gemini_api_key, settings.gemini_model)
    context.user_data["learning_points"] = points
    context.user_data["selected_lp"] = set()
    await message.reply_text(
        _build_lp_text(points, set()),
        reply_markup=_build_lp_keyboard(points, set()),
    )


async def _toggle_learning_point(query, context: ContextTypes.DEFAULT_TYPE, index: int) -> None:
    selected: set[int] = set(context.user_data.get("selected_lp", set()))
    if index in selected:
        selected.discard(index)
    elif len(selected) < MAX_LEARNING_POINTS_SELECTED:
        selected.add(index)
    context.user_data["selected_lp"] = selected

    points = context.user_data.get("learning_points", [])
    try:
        await query.edit_message_text(
            _build_lp_text(points, selected),
            reply_markup=_build_lp_keyboard(points, selected),
        )
    except BadRequest as exc:
        if "Message is not modified" in str(exc):
            pass
        else:
            raise


async def _confirm_learning_points(message, context: ContextTypes.DEFAULT_TYPE) -> None:
    selected_indices: set[int] = context.user_data.get("selected_lp", set())
    all_points: list[str] = context.user_data.get("learning_points", [])
    selected_points = [all_points[i] for i in sorted(selected_indices) if i < len(all_points)]
    if not selected_points:
        await message.reply_text("Please select at least one learning point first.")
        return
    context.user_data["selected_learning_points"] = selected_points
    await _generate_learning_package(message, context)


def _build_lp_text(points: list[str], selected: set[int]) -> str:
    lines = []
    for i, point in enumerate(points):
        icon = "✅" if i in selected else "○"
        lines.append(f"{icon} {i + 1}. {point}")
    text = "What would you like to learn from this news?\nTap to select up to 2 points.\n\n" + "\n".join(lines)
    if selected:
        text += f"\n\nSelected: {len(selected)}/{MAX_LEARNING_POINTS_SELECTED}"
    return text


def _build_lp_keyboard(points: list[str], selected: set[int]) -> InlineKeyboardMarkup:
    number_row = [
        InlineKeyboardButton(
            f"{'✅' if i in selected else '○'} {i + 1}",
            callback_data=f"lp_toggle:{i}",
        )
        for i in range(len(points))
    ]
    buttons = [number_row]
    if selected:
        buttons.append([InlineKeyboardButton("🎓 Generate Learning Pack", callback_data="lp_confirm")])
    buttons.append([InlineKeyboardButton("« Back", callback_data="article_actions")])
    return InlineKeyboardMarkup(buttons)


# ── Learning package generation ───────────────────────────────────────────────

async def _generate_learning_package(message, context: ContextTypes.DEFAULT_TYPE) -> None:
    article = context.user_data.get("selected_article")
    articles = context.user_data.get("articles", [])
    selected_learning_points: list[str] = context.user_data.get("selected_learning_points", [])

    if not article:
        await message.reply_text("Please select an article first.", reply_markup=MAIN_MENU)
        return

    related = [candidate for candidate in articles if str(candidate.url) != str(article.url)][:8]
    package = build_notebook_package(article, related, selected_learning_points)
    settings = get_settings()
    context.user_data.pop("notebooklm_infographic_path", None)

    lp_summary = ", ".join(f'"{lp}"' for lp in selected_learning_points) if selected_learning_points else "general overview"
    await message.reply_text(
        f"NotebookLM generation has started.\n\n"
        f"Learning focus: {lp_summary}\n\n"
        "The infographic often takes 5–10 minutes. "
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
        "NotebookLM learning pack is ready. Sending the infographic now.",
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
                [InlineKeyboardButton("📝 Create LinkedIn Post", callback_data="linkedin")],
                [InlineKeyboardButton("Start Over", callback_data="menu")],
            ]
        ),
    )


# ── LinkedIn post ─────────────────────────────────────────────────────────────

async def _send_linkedin_post(message, context: ContextTypes.DEFAULT_TYPE) -> None:
    article = context.user_data.get("selected_article")
    selected_learning_points: list[str] = context.user_data.get("selected_learning_points", [])
    if not article:
        await message.reply_text("Please select an article first.", reply_markup=MAIN_MENU)
        return

    settings = get_settings()
    post = await generate_linkedin_post(
        article,
        selected_learning_points,
        settings.gemini_api_key,
        settings.gemini_model,
    )
    # Send as a clean, label-free message — ready to copy directly to LinkedIn
    await message.reply_text(
        post,
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Start Over", callback_data="menu")],
                [InlineKeyboardButton("Stop", callback_data="stop")],
            ]
        ),
    )


# ── File delivery ─────────────────────────────────────────────────────────────

def _build_delivery_items(result: NotebookResult) -> list[DeliveryItem]:
    items = []
    if result.infographic_path:
        items.append(DeliveryItem(
            label="infographic",
            path=Path(result.infographic_path).absolute(),
            kind="photo",
            caption="NotebookLM infographic.",
        ))
    return items


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




async def _send_notebooklm_progress(message, interval_seconds: int) -> None:
    elapsed = 0
    try:
        while True:
            await asyncio.sleep(interval_seconds)
            elapsed += interval_seconds
            minutes = elapsed // 60
            await message.reply_text(
                f"Still working in NotebookLM. Elapsed time: about {minutes} minutes. "
                "Infographic generation can take 5–10 minutes, especially with multiple sources."
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
