"""External integrations: Open-Meteo, MyMemory and optional operator-managed AI.
External lookups are explicit user actions; the account email is never transmitted.
"""
from __future__ import annotations
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .models import User
from .security import current_user, csrf_protect, enforce_origin

router = APIRouter(prefix="/api", tags=["External integrations"])


def remote_json(base_url: str, params: dict | None = None, headers: dict | None = None,
                body: dict | None = None, timeout=7):
    url = base_url
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, headers=headers or {"Accept": "application/json"})
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise HTTPException(503, "Внешний сервис временно недоступен")
            # Limit JSON payload size, including content-length-free responses.
            raw = response.read(256_001)
            if len(raw) > 256_000:
                raise HTTPException(502, "Ответ внешнего сервиса слишком велик")
            return json.loads(raw)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError):
        raise HTTPException(503, "Внешний сервис не ответил. Повторите позже") from None


@router.get("/location/search")
def geocode(city: str, user: User = Depends(current_user)):
    city = city.strip()
    if not 2 <= len(city) <= 80:
        raise HTTPException(422, "Введите название города (2–80 символов)")
    result = remote_json("https://geocoding-api.open-meteo.com/v1/search",
                         {"name": city, "count": 5, "language": "ru"})
    return {"items": [{"name": i.get("name"), "country": i.get("country"),
                      "latitude": i["latitude"], "longitude": i["longitude"]}
                     for i in result.get("results", [])]}


@router.get("/weather")
def weather(latitude: float, longitude: float, user: User = Depends(current_user)):
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise HTTPException(422, "Неверные координаты")
    result = remote_json("https://api.open-meteo.com/v1/forecast", {
        "latitude": latitude, "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "forecast_days": 5, "timezone": "auto"})
    return {"current": result.get("current", {}), "daily": result.get("daily", {}),
            "source": "Open-Meteo", "timezone": result.get("timezone", "")}


class TranslateInput(BaseModel):
    text: str = Field(min_length=1, max_length=450)
    source: str = "ru"
    target: str = "en"


LANGS = {"ru", "en", "no", "tr", "de", "fr", "es", "it", "ar", "uk"}


@router.post("/translate", dependencies=[Depends(csrf_protect)])
def translate(data: TranslateInput, request: Request, user: User = Depends(current_user)):
    enforce_origin(request)
    if data.source not in LANGS or data.target not in LANGS or data.source == data.target:
        raise HTTPException(422, "Выберите два разных поддерживаемых языка")
    if len(data.text.encode("utf-8")) > 500:
        raise HTTPException(422, "Текст слишком длинный для сервиса перевода")
    result = remote_json("https://api.mymemory.translated.net/get",
                         {"q": data.text, "langpair": f"{data.source}|{data.target}"})
    translated = (result.get("responseData") or {}).get("translatedText", "")
    if not translated:
        raise HTTPException(503, "Перевод не получен")
    return {"translation": translated, "source": "MyMemory", "note": "Текст отправлен внешнему сервису"}


class AiInput(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)


@router.get("/ai/status")
def ai_status(user: User = Depends(current_user)):
    return {"configured": bool(os.getenv("VAINAH_AI_API_KEY") and os.getenv("VAINAH_AI_BASE_URL")
                               and os.getenv("VAINAH_AI_MODEL")), "provider": "OpenAI-compatible"}


@router.post("/ai/chat", dependencies=[Depends(csrf_protect)])
def ai_chat(data: AiInput, request: Request, user: User = Depends(current_user)):
    enforce_origin(request)
    key = os.getenv("VAINAH_AI_API_KEY", "")
    base_url = os.getenv("VAINAH_AI_BASE_URL", "").rstrip("/")
    model = os.getenv("VAINAH_AI_MODEL", "")
    if not (key and base_url and model):
        raise HTTPException(503, "ИИ-модель не подключена: задайте VAINAH_AI_API_KEY, VAINAH_AI_BASE_URL и VAINAH_AI_MODEL")
    if not base_url.startswith("https://"):
        raise HTTPException(503, "Для ИИ требуется защищённое HTTPS-соединение")
    response = remote_json(f"{base_url}/chat/completions", headers={
        "Authorization": f"Bearer {key}", "Accept": "application/json"}, body={
        "model": model, "messages": [
            {"role": "system", "content": "You are Vainah AI, a helpful assistant. Respond in the language of the user. Do not pretend to have capabilities you lack."},
            {"role": "user", "content": data.prompt}], "max_tokens": 650}, timeout=25)
    try:
        answer = response["choices"][0]["message"]["content"]
        if not isinstance(answer, str): raise ValueError()
    except (KeyError, IndexError, ValueError, TypeError):
        raise HTTPException(502, "ИИ вернул неожиданный ответ") from None
    return {"answer": answer, "model": model}
