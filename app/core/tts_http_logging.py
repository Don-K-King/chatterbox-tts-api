"""
HTTP logging helpers for TTS error diagnostics.
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from fastapi import Request
from starlette.datastructures import UploadFile

from app.config import Config
from app.core.aliases import ENDPOINT_ALIASES
from app.core.text_processing import (
    get_streaming_settings,
    split_text_for_streaming,
    split_text_into_chunks,
)
from app.core.voice_library import get_voice_library


logger = logging.getLogger(__name__)

_BODY_LOG_LIMIT_BYTES = 16 * 1024
_REQUEST_HEADER_ALLOWLIST = {
    "x-conversation-id",
    "x-request-id",
    "x-correlation-id",
    "content-type",
    "accept",
}
_RESPONSE_HEADER_ALLOWLIST = {"content-type", "content-length"}
_CONVERSATION_ID_FIELDS = (
    "conversation_id",
    "conversationId",
    "session",
    "session_id",
    "sessionId",
)
_SESSION_ID_FIELDS = ("session_id", "sessionId")
_SEGMENT_ID_FIELDS = ("segment_id", "segmentId")
_REQUEST_ID_HEADERS = ("x-request-id", "x-correlation-id")


def _build_speech_endpoint_prefixes() -> Tuple[str, ...]:
    prefixes = set()
    for primary, aliases in ENDPOINT_ALIASES.items():
        if primary.startswith("/audio/speech") and not primary.startswith("/audio/speech/long"):
            prefixes.add(primary)
            prefixes.update(aliases)
    prefixes.add("/tts")
    return tuple(sorted(prefixes))


_SPEECH_ENDPOINT_PREFIXES = _build_speech_endpoint_prefixes()


def _is_speech_endpoint(path: str) -> bool:
    if "/audio/speech/long" in path:
        return False
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in _SPEECH_ENDPOINT_PREFIXES)


def _normalize_optional(value: Any) -> Optional[str]:
    if value is None:
        return None
    candidate = str(value).strip()
    return candidate or None


def _extract_first(payload: Dict[str, Any], fields: Tuple[str, ...]) -> Optional[str]:
    for field in fields:
        if field in payload:
            candidate = _normalize_optional(payload.get(field))
            if candidate:
                return candidate
    return None


def _extract_with_source(
    payload: Dict[str, Any],
    fields: Tuple[str, ...],
) -> Tuple[Optional[str], Optional[str], bool]:
    for field in fields:
        if field in payload:
            raw_value = payload.get(field)
            normalized = _normalize_optional(raw_value)
            return normalized, f"body.{field}", not bool(normalized)
    return None, None, True


def _filter_headers(headers: Dict[str, str], allowlist: set[str]) -> Dict[str, str]:
    filtered = {}
    for key, value in headers.items():
        if key.lower() in allowlist:
            filtered[key] = value
    return filtered


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _truncate_body(body: str) -> Tuple[str, bool]:
    encoded = body.encode("utf-8")
    if len(encoded) <= _BODY_LOG_LIMIT_BYTES:
        return body, False
    truncated_bytes = encoded[:_BODY_LOG_LIMIT_BYTES]
    return truncated_bytes.decode("utf-8", errors="replace"), True


def _compute_chunk_info(
    text: str,
    stream_format: Optional[str],
    streaming_chunk_size: Optional[int],
    streaming_strategy: Optional[str],
    streaming_quality: Optional[str],
    request_path: str,
) -> Dict[str, Any]:
    if not text:
        return {"chunk_count": 0, "chunks": []}

    is_streaming = stream_format == "sse" or "/stream" in request_path
    if is_streaming:
        settings = get_streaming_settings(streaming_chunk_size, streaming_strategy, streaming_quality)
        chunks = split_text_for_streaming(
            text,
            chunk_size=settings["chunk_size"],
            strategy=settings["strategy"],
            quality=settings["quality"],
        )
    else:
        chunks = split_text_into_chunks(text, Config.MAX_CHUNK_LENGTH)

    chunk_details = [
        {"length": len(chunk), "sha256": _hash_text(chunk)} for chunk in chunks if chunk is not None
    ]
    return {"chunk_count": len(chunks), "chunks": chunk_details}


async def _parse_request_payload(request: Request) -> Dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.body()
        if not body:
            return {}
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {}

    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        payload: Dict[str, Any] = {}
        for key, value in form.items():
            if isinstance(value, UploadFile):
                continue
            payload[key] = value
        return payload

    return {}


def _build_mapping_info(payload: Dict[str, Any]) -> Dict[str, Any]:
    voice_name = _normalize_optional(payload.get("voice"))
    language = _normalize_optional(payload.get("language"))
    response_format = _normalize_optional(payload.get("response_format"))
    voice_source = "default"
    resolved_voice = None
    resolved_language = None
    default_voice = None
    fallback_used = False

    try:
        voice_library = get_voice_library()
        default_voice = voice_library.get_default_voice()
        if voice_name:
            resolved_voice = voice_library.resolve_voice_name(voice_name)
            if resolved_voice:
                voice_source = "voice_library"
                resolved_language = voice_library.get_voice_language(voice_name)
            else:
                fallback_used = True
        elif default_voice:
            fallback_used = True
    except Exception as exc:  # pragma: no cover - defensive logging safety
        logger.debug("Unable to resolve voice mapping for diagnostics: %s", exc)

    return {
        "provider": "chatterbox",
        "mapping_key": resolved_voice or default_voice or voice_name,
        "voice_requested": voice_name,
        "voice_resolved": resolved_voice or default_voice,
        "fallback_used": fallback_used,
        "voice_source": voice_source,
        "language": language,
        "response_format": response_format,
        "resolved_language": resolved_language,
    }


def _redact_payload(payload: Dict[str, Any], request_path: str) -> Dict[str, Any]:
    text = payload.get("input") or payload.get("text") or ""
    text_str = str(text) if text is not None else ""
    stream_format = _normalize_optional(payload.get("stream_format"))
    streaming_chunk_size = payload.get("streaming_chunk_size")
    streaming_strategy = _normalize_optional(payload.get("streaming_strategy"))
    streaming_quality = _normalize_optional(payload.get("streaming_quality"))

    chunk_info = _compute_chunk_info(
        text_str,
        stream_format,
        streaming_chunk_size,
        streaming_strategy,
        streaming_quality,
        request_path,
    )

    return {
        "text_length": len(text_str),
        "text_sha256": _hash_text(text_str) if text_str else None,
        "voice": _normalize_optional(payload.get("voice")),
        "language": _normalize_optional(payload.get("language")),
        "response_format": _normalize_optional(payload.get("response_format")),
        "stream_format": stream_format,
        "speed": payload.get("speed"),
        "exaggeration": payload.get("exaggeration"),
        "cfg_weight": payload.get("cfg_weight"),
        "temperature": payload.get("temperature"),
        "streaming_chunk_size": streaming_chunk_size,
        "streaming_strategy": streaming_strategy,
        "streaming_buffer_size": payload.get("streaming_buffer_size"),
        "streaming_quality": streaming_quality,
        **chunk_info,
    }


def _format_response_body(body: Any) -> Tuple[Optional[str], bool, bool]:
    if body is None:
        return None, False, True
    if isinstance(body, (dict, list)):
        raw = json.dumps(body, ensure_ascii=False)
        is_json = True
    else:
        raw = str(body)
        is_json = False
    if not raw:
        return "", is_json, True
    return raw, is_json, False


def _extract_request_ids(headers: Dict[str, str]) -> Dict[str, Optional[str]]:
    normalized = {str(key).lower(): value for key, value in headers.items()}
    request_id = None
    correlation_id = None
    for header in _REQUEST_ID_HEADERS:
        value = _normalize_optional(normalized.get(header))
        if not value:
            continue
        if header == "x-request-id":
            request_id = request_id or value
        elif header == "x-correlation-id":
            correlation_id = correlation_id or value
    return {"request_id": request_id, "correlation_id": correlation_id}


def _extract_response_content_type(headers: Dict[str, str]) -> Optional[str]:
    normalized = {str(key).lower(): value for key, value in headers.items()}
    return _normalize_optional(normalized.get("content-type"))


def _build_voice_library_snapshot(voice_requested: Optional[str]) -> Dict[str, Any]:
    try:
        voice_library = get_voice_library()
        voices = voice_library.list_voices()
        default_voice = voice_library.get_default_voice()
        has_voice = voice_library.resolve_voice_name(voice_requested) if voice_requested else None
    except Exception as exc:  # pragma: no cover - best effort diagnostics
        logger.debug("Unable to fetch voice library snapshot: %s", exc)
        return {"error": "unavailable"}

    return {
        "voices_count": len(voices),
        "default_voice": default_voice,
        "has_voice": bool(has_voice) if voice_requested else None,
    }


async def log_tts_http_error(
    request: Request,
    status_code: int,
    response_body: Any,
    response_headers: Dict[str, str],
    exception: Optional[BaseException] = None,
) -> None:
    if not _is_speech_endpoint(request.url.path):
        return

    payload = await _parse_request_payload(request)
    request_context = build_tts_request_context(request)
    _log_tts_http_error_from_context(
        request_context=request_context,
        payload=payload,
        status_code=status_code,
        response_body=response_body,
        response_headers=response_headers,
        exception=exception,
    )


def build_tts_request_context(request: Request) -> Dict[str, Any]:
    return {
        "method": request.method,
        "url": str(request.url),
        "path": request.url.path,
        "headers": dict(request.headers),
    }


def log_tts_provider_error(
    *,
    payload: Dict[str, Any],
    status_code: int,
    response_body: Any,
    response_headers: Optional[Dict[str, str]] = None,
    exception: Optional[BaseException] = None,
    request_context: Optional[Dict[str, Any]] = None,
    request_path: Optional[str] = None,
) -> None:
    resolved_path = request_path
    if request_context:
        resolved_path = request_context.get("path") or resolved_path

    if resolved_path and not _is_speech_endpoint(resolved_path):
        return

    _log_tts_http_error_from_context(
        request_context=request_context,
        payload=payload,
        status_code=status_code,
        response_body=response_body,
        response_headers=response_headers or {},
        exception=exception,
        request_path=resolved_path,
    )


def _log_tts_http_error_from_context(
    *,
    request_context: Optional[Dict[str, Any]],
    payload: Dict[str, Any],
    status_code: int,
    response_body: Any,
    response_headers: Dict[str, str],
    exception: Optional[BaseException] = None,
    request_path: Optional[str] = None,
) -> None:
    request_path = request_path or ""
    timestamp = datetime.now(timezone.utc).isoformat()
    conversation_id, conversation_source, conversation_empty = _extract_with_source(
        payload, _CONVERSATION_ID_FIELDS
    )
    session_id = _extract_first(payload, _SESSION_ID_FIELDS)
    segment_id = _extract_first(payload, _SEGMENT_ID_FIELDS)
    if not conversation_id and request_context:
        headers = request_context.get("headers") or {}
        if "x-conversation-id" in headers:
            header_value = headers.get("x-conversation-id")
            conversation_id = _normalize_optional(header_value)
            conversation_source = "header.x-conversation-id"
            conversation_empty = not bool(conversation_id)
        else:
            conversation_source = conversation_source or "missing"
            conversation_empty = conversation_empty or True
    else:
        conversation_source = conversation_source or "missing"

    mapping_info = _build_mapping_info(payload)
    redacted_payload = _redact_payload(payload, request_path)
    request_headers = (request_context or {}).get("headers") or {}
    request_ids = _extract_request_ids(request_headers)
    filtered_request_headers = _filter_headers(dict(request_headers), _REQUEST_HEADER_ALLOWLIST)
    filtered_response_headers = _filter_headers(response_headers, _RESPONSE_HEADER_ALLOWLIST)

    formatted_body, is_json, body_empty = _format_response_body(response_body)
    response_body_logged, truncated = (
        _truncate_body(formatted_body) if formatted_body is not None else ("", False)
    )
    response_content_type = _extract_response_content_type(response_headers)

    request_method = (request_context or {}).get("method") or "INTERNAL"
    request_url = (request_context or {}).get("url") or request_path or "internal://tts"

    log_payload = {
        "timestamp": timestamp,
        "endpoint": request_path,
        "method": request_method,
        "status_code": status_code,
        "request_id": request_ids["request_id"],
        "correlation_id": request_ids["correlation_id"],
        "provider": mapping_info["provider"],
        "mapping_key": mapping_info["mapping_key"],
        "conversation_id": {
            "source": conversation_source,
            "value": conversation_id,
            "empty": conversation_empty,
        },
        "voice_requested": mapping_info["voice_requested"],
        "voice_resolved": mapping_info["voice_resolved"],
        "fallback_used": mapping_info["fallback_used"],
        "language": mapping_info["language"],
        "response_format": mapping_info["response_format"],
        "response_body_truncated": response_body_logged if formatted_body is not None else None,
        "response_content_type": response_content_type,
        "request_json_redacted": redacted_payload,
        "correlation": {
            "session_id": session_id,
            "segment_id": segment_id,
        },
        "request": {
            "method": request_method,
            "url": request_url,
            "timeout_seconds": None,
            "headers": filtered_request_headers,
        },
        "response": {
            "headers": filtered_response_headers,
            "body_is_json": is_json,
            "body_empty": body_empty,
            "body_truncated": truncated,
        },
    }

    if Config.TTS_DEBUG_HTTP and status_code >= 400:
        log_payload["voice_library_snapshot"] = _build_voice_library_snapshot(
            mapping_info["voice_requested"]
        )

    if status_code >= 500:
        logger.error("TTS HTTP error response", extra={"tts_http_error": log_payload}, exc_info=exception)
    else:
        logger.warning("TTS HTTP error response", extra={"tts_http_error": log_payload})
