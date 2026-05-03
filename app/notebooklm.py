from __future__ import annotations

import re
import logging
import asyncio
import os
import shutil
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.models import NotebookPackage, NotebookResult

logger = logging.getLogger(__name__)


class NotebookLMService:
    """Server-first NotebookLM adapter using notebooklm-py when enabled.

    The chosen integration route is the same one described in the existing
    NotebookLM bot guide: the unofficial notebooklm-py client reads a stored
    browser session and exposes NotebookLM operations as async Python methods.
    """

    async def create_learning_notebook(self, package: NotebookPackage) -> NotebookResult:
        settings = get_settings()
        if not settings.notebooklm_enabled:
            return NotebookResult(
                status="notebooklm_disabled",
                notebook_url=settings.notebooklm_base_url,
                notes=(
                    "NotebookLM connector is disabled. Set NOTEBOOKLM_ENABLED=true after "
                    "the stored Google/NotebookLM session is prepared on the server."
                ),
                podcast_target_minutes=settings.podcast_target_minutes,
            )

        try:
            return await self._create_with_notebooklm_py(package)
        except ImportError as exc:
            return NotebookResult(
                status="notebooklm_library_missing",
                notebook_url=settings.notebooklm_base_url,
                notes=f"Install notebooklm-py[browser] to enable NotebookLM integration: {exc}",
                podcast_target_minutes=settings.podcast_target_minutes,
            )
        except Exception as exc:  # pragma: no cover - depends on external NotebookLM session
            return NotebookResult(
                status="notebooklm_failed",
                notebook_url=settings.notebooklm_base_url,
                notes=f"NotebookLM task failed: {type(exc).__name__}: {exc}",
                podcast_target_minutes=settings.podcast_target_minutes,
            )

    async def _create_with_notebooklm_py(self, package: NotebookPackage) -> NotebookResult:
        from notebooklm import (
            AudioFormat,
            AudioLength,
            InfographicDetail,
            InfographicOrientation,
            InfographicStyle,
            NotebookLMClient,
        )

        settings = get_settings()
        _configure_notebooklm_download_auth(settings.notebooklm_storage_path)
        output_dir = Path(settings.notebooklm_output_dir).expanduser()
        if not output_dir.is_absolute():
            output_dir = Path.cwd() / output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            client_context = await NotebookLMClient.from_storage(settings.notebooklm_storage_path)
            async with client_context as client:
                logger.info("NotebookLM creating notebook for article: %s", package.title)
                notebook = await client.notebooks.create(_notebook_title(package.title))
                notebook_id = str(notebook.id)
                logger.info("NotebookLM notebook created: %s", notebook_id)

                guide_source_id = await self._try_add_text_source(client, notebook_id, package)
                logger.info("NotebookLM text source added: %s", "yes" if guide_source_id else "no")

                primary_url_source_id, primary_url_error = await self._try_add_primary_url_source(
                    client,
                    notebook_id,
                    package,
                )
                logger.info(
                    "NotebookLM primary URL source added: %s error=%s",
                    "yes" if primary_url_source_id else "no",
                    primary_url_error or "none",
                )

                research_result = await self._run_deep_research(client, notebook_id, package)
                imported_research_sources = research_result.get("imported_count", 0)
                logger.info("NotebookLM research result: %s", research_result)

                if not (guide_source_id or primary_url_source_id or imported_research_sources):
                    return NotebookResult(
                        notebook_id=notebook_id,
                        notebook_url=_notebook_url(settings.notebooklm_base_url, notebook_id),
                        status="no_sources_added",
                        notes=(
                            "NotebookLM notebook was created, but no usable source could be added. "
                            f"Primary URL error: {primary_url_error or 'none'}. "
                            f"Deep Research status: {research_result.get('status')}."
                        ),
                        podcast_target_minutes=settings.podcast_target_minutes,
                    )

                artifacts = await self._generate_artifacts_in_parallel(
                    client=client,
                    notebook_id=notebook_id,
                    package=package,
                    output_dir=output_dir,
                    enums={
                        "AudioFormat": AudioFormat,
                        "AudioLength": AudioLength,
                        "InfographicDetail": InfographicDetail,
                        "InfographicOrientation": InfographicOrientation,
                        "InfographicStyle": InfographicStyle,
                    },
                )
                logger.info("NotebookLM artifact result: %s", artifacts)

                notebook_url = _notebook_url(settings.notebooklm_base_url, notebook_id)
                return NotebookResult(
                    notebook_id=notebook_id,
                    notebook_url=notebook_url,
                    audio_path=artifacts.get("podcast_path"),
                    audio_url=artifacts.get("podcast_path"),
                    audio_brief_path=artifacts.get("audio_brief_path"),
                    audio_brief_url=artifacts.get("audio_brief_path"),
                    infographic_path=artifacts.get("infographic_path"),
                    infographic_url=artifacts.get("infographic_path"),
                    status=_result_status(
                        artifacts.get("podcast_path"),
                        artifacts.get("audio_brief_path"),
                        artifacts.get("infographic_path"),
                    ),
                    notes=(
                        f"Created NotebookLM notebook with selected-news text source. "
                        f"Primary URL source added: {'yes' if primary_url_source_id else 'no'}. "
                        f"Primary URL error: {primary_url_error or 'none'}. "
                        f"Deep Research status: {research_result.get('status')}. "
                        f"Research sources imported: {imported_research_sources}. "
                        f"Podcast target: about {settings.podcast_target_minutes} minutes. "
                        f"Parallel artifacts: {artifacts.get('summary')}."
                    ),
                    podcast_target_minutes=settings.podcast_target_minutes,
                )
        except Exception as exc:
            logger.error("NotebookLM automation failed: %s", exc, exc_info=True)
            raise

    async def _generate_artifacts_in_parallel(
        self,
        client: Any,
        notebook_id: str,
        package: NotebookPackage,
        output_dir: Path,
        enums: dict[str, Any],
    ) -> dict[str, str | None]:
        slug = f"{_slugify(package.title)}-{notebook_id[:8]}"

        podcast_path = output_dir / f"{slug}-podcast.mp3"
        audio_brief_path = output_dir / f"{slug}-audio-brief.mp3"
        infographic_path = output_dir / f"{slug}-infographic.png"

        notes: list[str] = []
        podcast_start, brief_start, infographic_start = await asyncio.gather(
            self._start_artifact(
                "podcast",
                client.artifacts.generate_audio(
                    notebook_id,
                    source_ids=None,
                    language=package.language,
                    audio_format=enums["AudioFormat"].DEEP_DIVE,
                    audio_length=_preferred_audio_length(enums["AudioLength"]),
                    instructions=_audio_instructions(package),
                ),
            ),
            self._start_artifact(
                "audio brief",
                client.artifacts.generate_audio(
                    notebook_id,
                    source_ids=None,
                    language=package.language,
                    audio_format=enums["AudioFormat"].BRIEF,
                    audio_length=_short_audio_length(enums["AudioLength"]),
                    instructions=_audio_brief_instructions(package),
                ),
            ),
            self._start_artifact(
                "infographic",
                client.artifacts.generate_infographic(
                    notebook_id,
                    source_ids=None,
                    language=package.language,
                    instructions=_infographic_instructions(package),
                    orientation=enums["InfographicOrientation"].PORTRAIT,
                    detail_level=enums["InfographicDetail"].CONCISE,
                    style=enums["InfographicStyle"].PROFESSIONAL,
                ),
            ),
        )

        wait_tasks: list[tuple[str, Any]] = []
        if podcast_start and getattr(podcast_start, "task_id", None):
            wait_tasks.append(
                (
                    "podcast",
                    self._wait_and_download_audio(
                        client,
                        notebook_id,
                        podcast_start.task_id,
                        podcast_path,
                        "podcast",
                    ),
                )
            )
        else:
            notes.append("podcast did not start")
        if brief_start and getattr(brief_start, "task_id", None):
            wait_tasks.append(
                (
                    "audio brief",
                    self._wait_and_download_audio(
                        client,
                        notebook_id,
                        brief_start.task_id,
                        audio_brief_path,
                        "audio brief",
                    ),
                )
            )
        else:
            notes.append("audio brief did not start")
        if infographic_start and getattr(infographic_start, "task_id", None):
            wait_tasks.append(
                (
                    "infographic",
                    self._wait_and_download_infographic(
                        client,
                        notebook_id,
                        infographic_start.task_id,
                        infographic_path,
                    ),
                )
            )
        else:
            notes.append("infographic did not start")

        results = await asyncio.gather(
            *(task for _, task in wait_tasks),
            return_exceptions=True,
        )
        downloaded: dict[str, str | None] = {
            "podcast": None,
            "audio brief": None,
            "infographic": None,
        }
        for (label, _), result in zip(wait_tasks, results, strict=False):
            if isinstance(result, Exception):
                logger.warning(
                    "NotebookLM %s wait/download raised: %s: %s",
                    label,
                    type(result).__name__,
                    result,
                    exc_info=True,
                )
                notes.append(f"{label} failed during download")
            else:
                downloaded[label] = result

        podcast_result = downloaded["podcast"]
        brief_result = downloaded["audio brief"]
        infographic_result = downloaded["infographic"]

        completed = [
            name
            for name, path in (
                ("podcast", podcast_result),
                ("audio brief", brief_result),
                ("infographic", infographic_result),
            )
            if path
        ]
        return {
            "podcast_path": podcast_result,
            "audio_brief_path": brief_result,
            "infographic_path": infographic_result,
            "summary": "; ".join(
                [
                    f"completed: {', '.join(completed) if completed else 'none'}",
                    *notes,
                ]
            ),
        }

    async def _start_artifact(self, label: str, start_task: Any) -> Any | None:
        try:
            logger.info("NotebookLM starting %s generation", label)
            started = await start_task
            logger.info(
                "NotebookLM %s generation started: task_id=%s status=%s",
                label,
                getattr(started, "task_id", None),
                getattr(started, "status", None),
            )
            return started
        except Exception as exc:
            logger.warning(
                "NotebookLM failed to start %s generation: %s: %s",
                label,
                type(exc).__name__,
                exc,
                exc_info=True,
            )
            return None

    async def _wait_and_download_audio(
        self,
        client: Any,
        notebook_id: str,
        artifact_id: str,
        output_path: Path,
        label: str,
    ) -> str | None:
        settings = get_settings()
        try:
            final = await client.artifacts.wait_for_completion(
                notebook_id,
                artifact_id,
                timeout=settings.notebooklm_audio_timeout_seconds,
                poll_interval=8,
            )
            if getattr(final, "is_complete", False):
                logger.info("NotebookLM %s generation complete. Downloading to %s", label, output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                download_path = await client.artifacts.download_audio(
                    notebook_id,
                    str(output_path),
                    artifact_id=artifact_id,
                )
                saved_path = _ensure_local_copy(download_path, output_path, label)
                if saved_path:
                    logger.info("Successfully saved %s to %s", label, saved_path)
                    return str(saved_path)
                else:
                    logger.warning("Download returned path %s but file does not exist", download_path)
            else:
                logger.warning("NotebookLM %s generation did not complete within timeout. Status: %s", label, getattr(final, "status", "unknown"))
        except Exception as exc:
            logger.warning(
                "NotebookLM %s generation/download failed: %s: %s",
                label,
                type(exc).__name__,
                exc,
            )
        return None

    async def _wait_and_download_infographic(
        self,
        client: Any,
        notebook_id: str,
        artifact_id: str,
        output_path: Path,
    ) -> str | None:
        settings = get_settings()
        try:
            final = await client.artifacts.wait_for_completion(
                notebook_id,
                artifact_id,
                timeout=settings.notebooklm_infographic_timeout_seconds,
                poll_interval=8,
            )
            if getattr(final, "is_complete", False):
                logger.info("NotebookLM infographic generation complete. Downloading to %s", output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                download_path = await client.artifacts.download_infographic(
                    notebook_id,
                    str(output_path),
                    artifact_id=artifact_id,
                )
                saved_path = _ensure_local_copy(download_path, output_path, "infographic")
                if saved_path:
                    logger.info("Successfully saved infographic to %s", saved_path)
                    return str(saved_path)
                else:
                    logger.warning("Download returned path %s but file does not exist", download_path)
            else:
                logger.warning("NotebookLM infographic generation did not complete within timeout. Status: %s", getattr(final, "status", "unknown"))
        except Exception as exc:
            logger.warning(
                "NotebookLM infographic generation/download failed: %s: %s",
                type(exc).__name__,
                exc,
            )
        return None

    async def _try_add_primary_url_source(
        self,
        client: Any,
        notebook_id: str,
        package: NotebookPackage,
    ) -> tuple[str | None, str | None]:
        settings = get_settings()
        url = str(package.primary_article.url)
        try:
            added_source = await client.sources.add_url(
                notebook_id,
                url,
                wait=True,
                wait_timeout=settings.notebooklm_source_wait_seconds,
            )
            return str(added_source.id), None
        except Exception as exc:
            logger.warning(
                "NotebookLM failed to add primary URL %s: %s: %s",
                url,
                type(exc).__name__,
                exc,
            )
            return None, f"{type(exc).__name__}: {exc}"

    async def _try_add_text_source(
        self,
        client: Any,
        notebook_id: str,
        package: NotebookPackage,
    ) -> str | None:
        settings = get_settings()
        add_text = getattr(client.sources, "add_text", None)
        if callable(add_text):
            try:
                source = await add_text(
                    notebook_id,
                    "Selected News Brief and Learning Guide",
                    package.guide_markdown,
                    wait=True,
                    wait_timeout=settings.notebooklm_source_wait_seconds,
                )
                return str(source.id)
            except Exception as exc:
                logger.warning(
                    "NotebookLM failed to add text source: %s: %s",
                    type(exc).__name__,
                    exc,
                )
                return None

        add_text_source = getattr(client.sources, "add_text_source", None)
        if callable(add_text_source):
            try:
                source = await add_text_source(
                    notebook_id,
                    "Selected News Brief and Learning Guide",
                    package.guide_markdown,
                )
                return str(source.id)
            except Exception as exc:
                logger.warning(
                    "NotebookLM failed to add text source: %s: %s",
                    type(exc).__name__,
                    exc,
                )
                return None

        return None

    async def _run_deep_research(
        self,
        client: Any,
        notebook_id: str,
        package: NotebookPackage,
    ) -> dict[str, Any]:
        settings = get_settings()
        query = _research_query(package)
        try:
            started = await client.research.start(
                notebook_id,
                query=query,
                source="web",
                mode=settings.notebooklm_research_mode,
            )
            if not started or not started.get("task_id"):
                return {"status": "not_started", "imported_count": 0}

            max_iterations = max(
                1,
                settings.notebooklm_research_timeout_seconds
                // settings.notebooklm_research_poll_seconds,
            )
            status: dict[str, Any] = {}
            for _ in range(max_iterations):
                status = await client.research.poll(notebook_id)
                if status.get("status") == "completed":
                    break
                await asyncio.sleep(settings.notebooklm_research_poll_seconds)
            else:
                return {"status": "timeout", "imported_count": 0}

            sources = status.get("sources", [])
            selected_sources = sources[: settings.notebooklm_max_research_sources]
            imported_count = 0
            if (
                settings.notebooklm_import_research_sources
                and selected_sources
                and status.get("task_id")
            ):
                imported = await client.research.import_sources(
                    notebook_id,
                    status["task_id"],
                    selected_sources,
                )
                imported_count = len(imported)

            return {
                "status": "completed",
                "sources_found": len(sources),
                "imported_count": imported_count,
            }
        except Exception as exc:
            logger.warning(
                "NotebookLM Deep Research failed: %s: %s",
                type(exc).__name__,
                exc,
            )
            return {"status": f"failed:{type(exc).__name__}", "imported_count": 0}


def _audio_instructions(package: NotebookPackage) -> str:
    settings = get_settings()
    return (
        f"Create an English Deep Dive podcast of about {settings.podcast_target_minutes} minutes. "
        "Make it conversational, sharp, and suitable for a senior technology and policy audience. "
        "Focus on why the news matters, the key concepts behind it, AI deployment implications, "
        "governance risks, and China-Singapore technology collaboration relevance. "
        "Avoid generic summary; explain the strategic signal behind the article."
    )


def _infographic_instructions(package: NotebookPackage) -> str:
    return (
        "Create a portrait-oriented, concise, clear, executive-friendly infographic in English. "
        "Use no more than six blocks. Explain the news, why it matters, the key concepts, "
        "technology implications, policy/governance implications, and China-Singapore relevance. "
        "Keep the wording simple and easy to understand. Use concise content density."
    )


def _audio_brief_instructions(package: NotebookPackage) -> str:
    return (
        "Create a short English audio brief for a busy senior technology and policy audience. "
        "Keep it concise and practical: what happened, why it matters, the core implication, "
        "and one sharp China-Singapore AI collaboration angle. This should be much shorter "
        "than the Deep Dive podcast."
    )


def _research_query(package: NotebookPackage) -> str:
    article = package.primary_article
    summary = " ".join((article.summary or "").split())
    return (
        "Research this news story efficiently and find the most useful sources for a senior "
        "technology and policy learner based in Singapore, with a focus on AI, governance, "
        "deployment, and China-Singapore technology collaboration. Prioritize concise, high-signal "
        "sources over quantity.\n\n"
        f"Title: {article.title}\n"
        f"Summary: {summary[:1200]}\n"
        f"Original URL, if useful: {article.url}"
    )


def _preferred_audio_length(audio_length_enum: Any) -> Any:
    for name in ("DEFAULT", "MEDIUM", "SHORT"):
        if hasattr(audio_length_enum, name):
            return getattr(audio_length_enum, name)
    return None


def _short_audio_length(audio_length_enum: Any) -> Any:
    for name in ("DEFAULT", "SHORT"):
        if hasattr(audio_length_enum, name):
            return getattr(audio_length_enum, name)
    return None


def _ensure_local_copy(download_path: str | None, output_path: Path, label: str) -> Path | None:
    if output_path.exists():
        return output_path
    if not download_path:
        return None

    source_path = Path(download_path).expanduser()
    if not source_path.exists():
        return None
    if source_path.resolve() == output_path.resolve():
        return output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, output_path)
    logger.info("Copied NotebookLM %s from %s to %s", label, source_path, output_path)
    return output_path


def _configure_notebooklm_download_auth(storage_path: str | None) -> None:
    if not storage_path:
        return

    path = Path(storage_path).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        logger.warning("NotebookLM storage path for downloads does not exist: %s", path)
        return

    os.environ["NOTEBOOKLM_HOME"] = str(path.parent)
    logger.info("NotebookLM download auth configured from %s", path)


def _notebook_title(title: str) -> str:
    clean = " ".join(title.split())
    return clean[:120] or "News Learning Pack"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return slug[:80] or "notebooklm-audio"


def _notebook_url(base_url: str, notebook_id: str) -> str:
    return f"{base_url.rstrip('/')}/notebook/{notebook_id}"


def _result_status(
    audio_path: str | None,
    audio_brief_path: str | None,
    infographic_path: str | None,
) -> str:
    if audio_path and audio_brief_path and infographic_path:
        return "completed"
    if any((audio_path, audio_brief_path, infographic_path)):
        completed = []
        if audio_path:
            completed.append("podcast")
        if audio_brief_path:
            completed.append("audio_brief")
        if infographic_path:
            completed.append("infographic")
        return f"partial_completed:{','.join(completed)}"
    return "artifacts_incomplete"
