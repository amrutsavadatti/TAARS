"""
Image parser — converts an image file into a text caption using a vision LLM.

Supports: PNG, JPG, JPEG, WEBP, GIF (first frame).

Strategy:
- Encode image as base64.
- Send to the configured LLM provider's vision endpoint.
- Return the caption as a single-page ParsedDocument so the chunker
  treats it as one atomic chunk with image metadata.

Falls back gracefully: if the vision call fails, returns a placeholder
so ingestion doesn't crash and the failure is logged.
"""

import base64
import logging
from pathlib import Path

from backend.config import settings
from backend.ingestion.models import ParsedDocument

logger = logging.getLogger(__name__)

# Vision-capable model per provider
_VISION_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-opus-4-6",
}

_CAPTION_PROMPT = (
    "This image is from a professional portfolio or resume. "
    "Describe what it shows in detail, focusing on any text, credentials, "
    "certificates, project screenshots, charts, or professional information visible. "
    "Be thorough — your description will be used to answer career-related questions."
)


def _encode_image(file_path: Path) -> tuple[str, str]:
    """Returns (base64_data, media_type)."""
    suffix = file_path.suffix.lower()
    media_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    media_type = media_types.get(suffix, "image/jpeg")
    with open(file_path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")
    return data, media_type


def _caption_openai(file_path: Path) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=settings.llm_api_key)
    model = _VISION_MODELS["openai"]
    b64, media_type = _encode_image(file_path)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{media_type};base64,{b64}"},
                    },
                    {"type": "text", "text": _CAPTION_PROMPT},
                ],
            }
        ],
        max_tokens=1024,
    )
    return response.choices[0].message.content.strip()


def _caption_anthropic(file_path: Path) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.llm_api_key)
    model = _VISION_MODELS["anthropic"]
    b64, media_type = _encode_image(file_path)

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": _CAPTION_PROMPT},
                ],
            }
        ],
    )
    return response.content[0].text.strip()


def parse_image(file_path: str | Path, owner_id: str) -> ParsedDocument:
    file_path = Path(file_path)

    try:
        if settings.llm_provider == "anthropic":
            caption = _caption_anthropic(file_path)
        else:
            caption = _caption_openai(file_path)
    except Exception as e:
        logger.error("Vision captioning failed for %s: %s", file_path.name, e)
        caption = f"[Image: {file_path.name} — captioning failed, please add description manually]"

    # Wrap caption with context so retrieval knows this came from an image
    page_text = f"[Image: {file_path.name}]\n{caption}"

    return ParsedDocument(
        pages=[page_text],
        full_text=page_text,
        source_file=file_path.name,
        source_type="image",
        owner_id=owner_id,
        page_count=1,
        extra={"original_filename": file_path.name},
    )
