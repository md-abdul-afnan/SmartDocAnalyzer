from typing import List, Optional

from pydantic import BaseModel


class AnalyzeResponse(BaseModel):
    extracted_text: str
    summary: str
    key_points: List[str]
    image_description: Optional[str] = None


class SummarizeRequest(BaseModel):
    text: str


class TranslateRequest(BaseModel):
    text: str
    target_language: str
    source_language: Optional[str] = "auto"
