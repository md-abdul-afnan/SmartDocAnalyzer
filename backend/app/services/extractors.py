from pathlib import Path
import shutil
from typing import Set

import fitz
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from pytesseract import Output


def _ensure_tesseract_available() -> None:
    """
    Ensure pytesseract can resolve the tesseract executable.
    """
    if shutil.which("tesseract"):
        return

    candidate_paths = (
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
        Path(r"D:\Program Files\Tesseract-OCR\tesseract.exe"),
    )
    for candidate in candidate_paths:
        if candidate.exists():
            pytesseract.pytesseract.tesseract_cmd = str(candidate)
            return


def _get_available_ocr_languages() -> Set[str]:
    try:
        _ensure_tesseract_available()
        return set(pytesseract.get_languages(config=""))
    except Exception:
        return {"eng"}


def get_available_ocr_languages() -> Set[str]:
    """
    Public helper for listing installed OCR languages.
    """
    return _get_available_ocr_languages()


def _resolve_ocr_language(requested_language: str) -> str:
    available = _get_available_ocr_languages()
    requested = (requested_language or "eng").strip().lower()

    # Prefer requested language when installed.
    if requested in available:
        # Blend English as a helper for mixed documents when possible.
        if requested != "eng" and "eng" in available:
            return f"{requested}+eng"
        return requested

    # If user explicitly requested a non-English language, surface a clear error
    # instead of silently producing low-quality OCR with wrong language data.
    if requested != "eng":
        available_display = ", ".join(sorted(available)) if available else "none"
        raise ValueError(
            f"OCR language '{requested}' is not installed in Tesseract. "
            f"Installed languages: {available_display}. "
            "Install the requested language pack and try again."
        )

    # Fall back to English when requested language is English but missing.
    if "eng" in available:
        return "eng"

    # Final fallback: first installed language if any.
    if available:
        return sorted(available)[0]
    return "eng"


def extract_text_from_pdf(file_path: Path) -> str:
    """
    Extract text from each page in a PDF using PyMuPDF.
    """
    extracted_chunks = []
    with fitz.open(file_path) as pdf:
        for page in pdf:
            extracted_chunks.append(page.get_text("text"))
    return "\n".join(extracted_chunks).strip()


def extract_text_from_image(file_path: Path, language: str = "eng") -> str:
    """
    OCR text extraction for image files.
    `--oem 3 --psm 6` works reasonably for mixed typed/handwritten text.
    """
    _ensure_tesseract_available()
    resolved_language = _resolve_ocr_language(language)
    image = Image.open(file_path)

    # Try multiple OCR-ready variants and page-segmentation modes, then
    # keep the candidate with best confidence/quality score.
    gray = ImageOps.grayscale(image)
    enhanced_gray = ImageEnhance.Contrast(gray).enhance(1.8)
    enhanced_gray = ImageEnhance.Sharpness(enhanced_gray).enhance(1.6)
    denoised = enhanced_gray.filter(ImageFilter.MedianFilter(size=3))
    thresholded = denoised.point(lambda px: 255 if px > 150 else 0)

    candidates = [
        image,
        gray,
        denoised,
        thresholded,
    ]
    psm_modes = (6, 11)

    best_text = ""
    best_score = -1.0
    best_confident_tokens = 0

    for candidate_image in candidates:
        for psm in psm_modes:
            custom_config = f"--oem 3 --psm {psm}"
            text = pytesseract.image_to_string(
                candidate_image, lang=resolved_language, config=custom_config
            ).strip()
            if not text:
                continue

            try:
                ocr_data = pytesseract.image_to_data(
                    candidate_image,
                    lang=resolved_language,
                    config=custom_config,
                    output_type=Output.DICT,
                )
            except Exception:
                # Fallback scoring when OCR data is unavailable.
                score = float(len(text))
                if score > best_score:
                    best_score = score
                    best_text = text
                continue

            token_score = 0.0
            confident_tokens = 0
            for raw_token, raw_conf in zip(ocr_data.get("text", []), ocr_data.get("conf", [])):
                token = (raw_token or "").strip()
                if not token:
                    continue
                try:
                    conf = float(raw_conf)
                except Exception:
                    conf = -1.0

                has_alnum = any(char.isalnum() for char in token)
                if conf >= 45.0 and has_alnum and len(token) >= 2:
                    confident_tokens += 1
                    token_score += conf

            # Prefer confident OCR, but also reward richer extracted text length.
            score = token_score + min(len(text), 1000) * 0.05
            if score > best_score:
                best_score = score
                best_text = text
                best_confident_tokens = confident_tokens

    # If OCR cannot find enough confident tokens, treat as unreadable text.
    if best_confident_tokens < 5:
        return ""

    return best_text
