import base64
import os
import re
from pathlib import Path
from typing import List, Optional, Tuple

from dotenv import load_dotenv

try:
    from deep_translator import GoogleTranslator, MyMemoryTranslator
except Exception:  # pragma: no cover - optional fallback dependency
    GoogleTranslator = None
    MyMemoryTranslator = None

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - safe import fallback
    OpenAI = None

load_dotenv()

# MyMemory (deep-translator) expects full language names, not ISO codes.
_MYMEMORY_LANG = {
    "en": "english",
    "hi": "hindi",
    "es": "spanish",
    "fr": "french",
    "ar": "arabic",
    "ta": "tamil india",
    "te": "telugu",
    "ur": "urdu",
}


class AIService:
    """
    AI helper that prefers OpenAI when API key is available.
    Falls back to HuggingFace summarizer for text summaries.
    """

    def __init__(self) -> None:
        self.openai_key = (os.getenv("OPENAI_API_KEY") or "").strip()
        self.openai_vision_model = (
            os.getenv("OPENAI_VISION_MODEL") or "gpt-4o-mini"
        ).strip()
        self.openai_client = OpenAI(api_key=self.openai_key) if self.openai_key and OpenAI else None
        self._hf_summarizer = None
        # Render / small VMs: BART + PyTorch often OOM or time out — use extractive fallback.
        _flag = (os.getenv("DISABLE_HF_SUMMARIZER") or "").strip().lower()
        self._hf_summarizer_disabled = _flag in ("1", "true", "yes", "on")

    def _get_hf_summarizer(self):
        if self._hf_summarizer_disabled:
            self._hf_summarizer = False
            return self._hf_summarizer
        if self._hf_summarizer is None:
            try:
                from transformers import pipeline

                self._hf_summarizer = pipeline(
                    "summarization", model="facebook/bart-large-cnn"
                )
            except Exception:
                self._hf_summarizer = False
        return self._hf_summarizer

    def _extractive_fallback(self, text: str) -> Tuple[str, List[str]]:
        cleaned = " ".join(text.split())
        if not cleaned:
            return "No summary available.", []

        sentences = re.split(r"(?<=[.!?])\s+", cleaned)
        sentences = [sentence.strip() for sentence in sentences if sentence.strip()]
        if not sentences:
            return "No summary available.", []

        summary = " ".join(sentences[:2]).strip()
        if len(summary) > 450:
            summary = summary[:447].rstrip() + "..."
        key_points = sentences[:5]
        return summary, key_points

    def summarize_text(self, text: str) -> Tuple[str, List[str]]:
        if self.openai_client:
            return self._summarize_with_openai(text)
        return self._summarize_with_huggingface(text)

    def _summarize_with_openai(self, text: str) -> Tuple[str, List[str]]:
        prompt = (
            "You are a helpful document analyst.\n"
            "Return JSON with keys: summary (string), key_points (array of concise bullet strings).\n"
            "Keep summary short and key points practical."
        )

        response = self.openai_client.responses.create(
            model="gpt-4.1-mini",
            input=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text[:12000]},
            ],
            temperature=0.2,
        )
        output_text = response.output_text.strip()

        # Lightweight fallback parser if output is not valid JSON.
        if output_text.startswith("{") and "key_points" in output_text:
            import json

            parsed = json.loads(output_text)
            summary = parsed.get("summary", "").strip()
            key_points = parsed.get("key_points", [])
            if isinstance(key_points, list):
                key_points = [str(point).strip() for point in key_points if str(point).strip()]
            return summary, key_points

        lines = [line.strip("- ").strip() for line in output_text.splitlines() if line.strip()]
        summary = lines[0] if lines else "No summary available."
        key_points = lines[1:6] if len(lines) > 1 else []
        return summary, key_points

    def _summarize_with_huggingface(self, text: str) -> Tuple[str, List[str]]:
        summarizer = self._get_hf_summarizer()
        if summarizer is False:
            return self._extractive_fallback(text)

        clipped = text[:4000]
        try:
            summary_result = summarizer(clipped, max_length=180, min_length=40, do_sample=False)
            first_item = summary_result[0] if summary_result else {}
            summary = (first_item.get("summary_text") or first_item.get("generated_text") or "").strip()
            if not summary:
                return self._extractive_fallback(clipped)
            key_points = [item.strip() for item in summary.split(". ") if item.strip()][:5]
            return summary, key_points
        except Exception:
            return self._extractive_fallback(clipped)

    def describe_image(self, image_path: Path) -> Optional[str]:
        """
        Generate an image description using OpenAI vision model.
        Returns None when OpenAI is not configured.
        """
        if not self.openai_client:
            return None

        encoded_image = base64.b64encode(image_path.read_bytes()).decode("utf-8")
        mime_type = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"

        response = self.openai_client.responses.create(
            model=self.openai_vision_model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "Describe this image in 1-2 concise sentences."},
                        {
                            "type": "input_image",
                            "image_url": f"data:{mime_type};base64,{encoded_image}",
                        },
                    ],
                }
            ],
            temperature=0.2,
        )
        return response.output_text.strip()

    def extract_text_from_image_with_openai(
        self, image_path: Path, language_hint: str = "auto"
    ) -> Optional[str]:
        """
        Perform OCR-style text extraction using OpenAI vision.
        Returns None when OpenAI is not configured.
        """
        if not self.openai_client:
            return None

        encoded_image = base64.b64encode(image_path.read_bytes()).decode("utf-8")
        mime_type = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
        hint = (language_hint or "auto").strip()

        response = self.openai_client.responses.create(
            model=self.openai_vision_model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are an OCR engine. Extract text from the image as accurately as possible. "
                        "Preserve line breaks and ordering. Return only the extracted text, no commentary."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Extract all readable text from this image.\n"
                                f"Language hint: {hint}\n"
                                "If text is unclear, provide your best faithful transcription."
                            ),
                        },
                        {
                            "type": "input_image",
                            "image_url": f"data:{mime_type};base64,{encoded_image}",
                        },
                    ],
                },
            ],
            temperature=0.0,
        )
        extracted = response.output_text.strip()
        return extracted or None

    @staticmethod
    def _chunk_text_for_translation(text: str, max_len: int = 4500) -> List[str]:
        """
        Split long text for Google Translate free tier (long strings often fail or time out).
        """
        text = text.strip()
        if not text:
            return []
        if len(text) <= max_len:
            return [text]
        chunks: List[str] = []
        i = 0
        n = len(text)
        while i < n:
            j = min(i + max_len, n)
            if j < n:
                split_at = text.rfind("\n", i, j)
                if split_at <= i:
                    split_at = text.rfind(" ", i, j)
                if split_at <= i:
                    split_at = j
                j = split_at
            piece = text[i:j]
            if piece.strip():
                chunks.append(piece)
            i = j
        return chunks

    def _translate_openai_chat(self, clean_text: str, source: str, target: str) -> Optional[str]:
        if not self.openai_client:
            return None
        model = (
            os.getenv("OPENAI_TRANSLATION_MODEL")
            or os.getenv("OPENAI_VISION_MODEL")
            or "gpt-4o-mini"
        ).strip()
        clipped = clean_text[:12000]
        try:
            completion = self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a precise translator. Preserve line breaks and meaning. "
                            "Output only the translated text, with no preamble or quotes."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Source language hint: {source}\n"
                            f"Target language (ISO 639-1): {target}\n\n"
                            f"{clipped}"
                        ),
                    },
                ],
                temperature=0.1,
            )
            msg = completion.choices[0].message
            out = (msg.content or "").strip()
            return out or None
        except Exception:
            return None

    def _translate_openai_responses(self, clean_text: str, source: str, target: str) -> Optional[str]:
        if not self.openai_client:
            return None
        model = (os.getenv("OPENAI_RESPONSES_MODEL") or "gpt-4.1-mini").strip()
        prompt = (
            "You are a precise translator. Translate the input text while preserving meaning "
            "and structure. Return only translated text without extra commentary."
        )
        try:
            response = self.openai_client.responses.create(
                model=model,
                input=[
                    {"role": "system", "content": prompt},
                    {
                        "role": "user",
                        "content": (
                            f"Source language: {source}\n"
                            f"Target language: {target}\n\n"
                            f"{clean_text[:12000]}"
                        ),
                    },
                ],
                temperature=0.1,
            )
            translated = response.output_text.strip()
            return translated or None
        except Exception:
            return None

    def _translate_google(self, clean_text: str, source: str, target: str) -> str:
        src = source if source and source != "auto" else "auto"
        chunks = self._chunk_text_for_translation(clean_text)
        if not chunks:
            return ""
        parts: List[str] = []
        for chunk in chunks:
            translator = GoogleTranslator(source=src, target=target)
            parts.append(translator.translate(chunk))
        return "".join(parts)

    def _translate_mymemory(self, clean_text: str, source: str, target: str) -> str:
        """
        Second free tier when Google is blocked or errors (no API keys).
        Source language for 'auto' defaults to English naming (best-effort).
        """
        src_code = source if source != "auto" else "en"
        mem_src = _MYMEMORY_LANG.get(src_code)
        mem_tgt = _MYMEMORY_LANG.get(target)
        if not mem_src or not mem_tgt:
            raise ValueError(f"Unsupported language pair for MyMemory fallback: {source!r} -> {target!r}")
        chunks = self._chunk_text_for_translation(clean_text, max_len=450)
        if not chunks:
            return ""
        parts: List[str] = []
        for chunk in chunks:
            translator = MyMemoryTranslator(source=mem_src, target=mem_tgt)
            parts.append(translator.translate(chunk))
        return "".join(parts)

    def _translate_free_services(self, clean_text: str, source: str, target: str) -> str:
        """
        No OpenAI key: try Google Translate, then MyMemory (both via deep-translator).
        """
        if GoogleTranslator is None and MyMemoryTranslator is None:
            raise RuntimeError(
                "Translation needs deep-translator (pip install deep-translator) "
                "or set OPENAI_API_KEY in the backend .env file."
            )
        errors: List[str] = []
        if GoogleTranslator is not None:
            try:
                return self._translate_google(clean_text, source, target)
            except Exception as exc:
                errors.append(f"Google: {exc}")
        if MyMemoryTranslator is not None:
            try:
                return self._translate_mymemory(clean_text, source, target)
            except Exception as exc:
                errors.append(f"MyMemory: {exc}")
        raise RuntimeError(
            "Translation failed without OpenAI. Check your internet connection or try again later. "
            + " | ".join(errors)
        )

    def translate_text(
        self, text: str, target_language: str, source_language: str = "auto"
    ) -> str:
        """
        With OPENAI_API_KEY: OpenAI chat, then Responses API.
        Without a key: free Google Translate, then MyMemory (deep-translator).
        """
        clean_text = text.strip()
        if not clean_text:
            return ""

        target = (target_language or "en").strip().lower()
        source = (source_language or "auto").strip().lower()

        if self.openai_client:
            translated = self._translate_openai_chat(clean_text, source, target)
            if translated:
                return translated
            translated = self._translate_openai_responses(clean_text, source, target)
            if translated:
                return translated

        return self._translate_free_services(clean_text, source, target)
