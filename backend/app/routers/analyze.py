import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..models import AnalyzeResponse, SummarizeRequest, TranslateRequest
from ..services.ai_service import AIService
from ..services.extractors import (
    extract_text_from_image,
    extract_text_from_pdf,
    get_available_ocr_languages,
)

router = APIRouter()
ai_service = AIService()

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".md"}
TEXT_EXTENSIONS = {".txt", ".md"}


@router.get("/languages")
async def get_ocr_languages():
    """
    Return installed Tesseract OCR language codes.
    """
    languages = sorted(get_available_ocr_languages())
    return {"languages": languages}


def _save_upload_to_temp(file: UploadFile) -> Path:
    """
    Save uploaded file to a temporary folder and return path.
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Use PDF, PNG, JPG, JPEG, TXT, or MD.",
        )

    temp_dir = Path(tempfile.mkdtemp(prefix="smart_doc_"))
    file_path = temp_dir / (file.filename or f"upload{suffix}")
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return file_path


def _cleanup_temp(file_path: Path) -> None:
    if file_path.exists():
        shutil.rmtree(file_path.parent, ignore_errors=True)


@router.post("/upload", response_model=AnalyzeResponse)
async def upload_and_analyze(file: UploadFile = File(...), language: str = "eng"):
    """
    Upload a file, extract text, generate summary and key insights.
    If image file is uploaded, also generate image description when AI API is configured.
    """
    file_path = _save_upload_to_temp(file)
    try:
        suffix = file_path.suffix.lower()
        is_image = suffix in {".png", ".jpg", ".jpeg"}

        if suffix in TEXT_EXTENSIONS:
            extracted_text = file_path.read_text(encoding="utf-8", errors="replace")
            image_description = None
        elif suffix == ".pdf":
            extracted_text = extract_text_from_pdf(file_path)
            image_description = None
        else:
            # Prefer OpenAI vision OCR when configured — Tesseract often fails on
            # handwriting/stylized text; do not gate on noisy Tesseract length.
            if ai_service.openai_client:
                try:
                    openai_text = ai_service.extract_text_from_image_with_openai(
                        file_path, language_hint=language
                    )
                    if openai_text and len(openai_text.strip()) >= 10:
                        extracted_text = openai_text.strip()
                    else:
                        extracted_text = extract_text_from_image(
                            file_path, language=language
                        )
                except Exception:
                    extracted_text = extract_text_from_image(
                        file_path, language=language
                    )
            else:
                extracted_text = extract_text_from_image(
                    file_path, language=language
                )
            image_description = ai_service.describe_image(file_path)

        if not extracted_text.strip():
            raise HTTPException(status_code=422, detail="Could not extract meaningful text from file.")

        summary, key_points = ai_service.summarize_text(extracted_text)

        # In case OCR image had no visual description available (for example no API key)
        if not is_image:
            image_description = None

        return AnalyzeResponse(
            extracted_text=extracted_text,
            summary=summary,
            key_points=key_points,
            image_description=image_description,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc
    finally:
        _cleanup_temp(file_path)


@router.post("/summarize")
async def summarize_text_only(payload: SummarizeRequest):
    """
    Summarize raw text passed directly by client.
    """
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Text must not be empty.")
    try:
        summary, key_points = ai_service.summarize_text(payload.text)
        return {"summary": summary, "key_points": key_points}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Summarization failed: {exc}") from exc


@router.post("/translate")
async def translate_text(payload: TranslateRequest):
    """
    Translate plain text into a target language.
    """
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Text must not be empty.")
    if not payload.target_language.strip():
        raise HTTPException(status_code=400, detail="Target language must not be empty.")
    try:
        translated_text = ai_service.translate_text(
            text=payload.text,
            target_language=payload.target_language,
            source_language=payload.source_language or "auto",
        )
        return {"translated_text": translated_text}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Translation failed: {exc}") from exc
