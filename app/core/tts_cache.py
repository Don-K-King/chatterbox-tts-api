"""Caching utilities for TTS voice prompts and conversation state."""

from __future__ import annotations

import asyncio
import logging
import os
import time
import hashlib
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, Iterable

from app.config import Config

try:
    from prometheus_client import Counter
except Exception:  # pragma: no cover - fallback when prometheus_client unavailable
    class _NoOpCounter:  # type: ignore
        def inc(self, amount: int | float = 1) -> None:
            return None

    def Counter(name: str, documentation: str) -> _NoOpCounter:  # type: ignore
        return _NoOpCounter()


logger = logging.getLogger(__name__)

VOICE_PROMPT_CACHE_HITS = Counter(
    "tts_voice_prompt_cache_hits_total",
    "Number of times a cached voice prompt was reused",
)
VOICE_PROMPT_CACHE_MISSES = Counter(
    "tts_voice_prompt_cache_misses_total",
    "Number of times a voice prompt had to be reloaded",
)
CONVERSATION_AUDIO_CACHE_HITS = Counter(
    "tts_conversation_audio_cache_hits_total",
    "Number of cached audio responses returned immediately",
)
CONVERSATION_AUDIO_CACHE_MISSES = Counter(
    "tts_conversation_audio_cache_misses_total",
    "Number of audio generations due to cache miss",
)
CONVERSATION_SLOT_EVICTIONS = Counter(
    "tts_conversation_slot_evictions_total",
    "Number of times a conversation cache slot was evicted",
)


@dataclass
class VoicePrompt:
    """Data describing a cached voice prompt."""

    voice_key: str
    path: str
    mtime: float
    data: bytes
    loaded_at: float = field(default_factory=time.time)


@dataclass
class ConversationSlot:
    """Single slot in the two-slot conversation cache."""

    name: str
    voice_key: str
    language: str
    prompt: VoicePrompt
    last_used: float = field(default_factory=time.time)
    audio_cache: "OrderedDict[str, bytes]" = field(default_factory=OrderedDict)
    last_audio_hash: Optional[str] = None

    def touch(self) -> None:
        self.last_used = time.time()


@dataclass
class ConversationState:
    """Conversation-level cache and lock."""

    conversation_id: str
    slots: Dict[str, ConversationSlot] = field(default_factory=dict)
    last_access: float = field(default_factory=time.time)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def __post_init__(self) -> None:
        # Replace dataclass-created lock with a fresh asyncio.Lock instance
        self.lock = asyncio.Lock()

    def touch(self) -> None:
        self.last_access = time.time()


_voice_prompt_cache: "OrderedDict[str, VoicePrompt]" = OrderedDict()
_voice_prompt_lock = asyncio.Lock()

_conversation_cache: Dict[str, ConversationState] = {}
_conversation_cache_lock = asyncio.Lock()


def _normalise_voice_key(path: str) -> str:
    return os.path.abspath(path)


async def get_or_load_voice_prompt(path: str) -> VoicePrompt:
    """Return a cached voice prompt, loading it from disk if required."""

    voice_key = _normalise_voice_key(path)
    mtime = os.path.getmtime(path) if os.path.exists(path) else 0.0

    async with _voice_prompt_lock:
        cached = _voice_prompt_cache.get(voice_key)
        if cached and cached.mtime == mtime:
            _voice_prompt_cache.move_to_end(voice_key)
            VOICE_PROMPT_CACHE_HITS.inc()
            return cached

    # Load file outside of the cache lock to avoid blocking other coroutines
    if not os.path.exists(path):
        raise FileNotFoundError(f"Voice prompt not found: {path}")

    with open(path, "rb") as fh:
        data = fh.read()

    prompt = VoicePrompt(voice_key=voice_key, path=path, mtime=mtime, data=data)

    async with _voice_prompt_lock:
        previous = _voice_prompt_cache.get(voice_key)
        if previous and previous.mtime == mtime:
            _voice_prompt_cache.move_to_end(voice_key)
            VOICE_PROMPT_CACHE_HITS.inc()
            return previous

        _voice_prompt_cache[voice_key] = prompt
        _voice_prompt_cache.move_to_end(voice_key)
        while len(_voice_prompt_cache) > Config.VOICE_PROMPT_CACHE_SIZE:
            evicted_key, _ = _voice_prompt_cache.popitem(last=False)
            logger.debug("Evicted voice prompt from cache: %s", evicted_key)
        VOICE_PROMPT_CACHE_MISSES.inc()
        return prompt


async def invalidate_voice_prompt(path: str) -> None:
    """Remove a prompt from the cache, used when temporary files are deleted."""

    voice_key = _normalise_voice_key(path)
    async with _voice_prompt_lock:
        if _voice_prompt_cache.pop(voice_key, None) is not None:
            logger.info("Removed voice prompt from cache: %s", voice_key)


async def get_conversation_state(conversation_id: str) -> ConversationState:
    """Return or create the cache entry for the given conversation."""

    await _cleanup_expired_conversations()
    async with _conversation_cache_lock:
        state = _conversation_cache.get(conversation_id)
        if state is None:
            state = ConversationState(conversation_id=conversation_id)
            _conversation_cache[conversation_id] = state
            logger.debug("Created cache entry for conversation %s", conversation_id)
        state.touch()
        return state


async def _cleanup_expired_conversations() -> None:
    """Remove stale conversation cache entries based on TTL."""

    ttl = Config.CONVERSATION_CACHE_TTL_SECONDS
    now = time.time()
    async with _conversation_cache_lock:
        expired: Iterable[Tuple[str, ConversationState]] = [
            (cid, state)
            for cid, state in _conversation_cache.items()
            if not state.lock.locked() and now - state.last_access > ttl
        ]
        for cid, _ in expired:
            logger.info("Expiring cached conversation %s due to inactivity", cid)
            _conversation_cache.pop(cid, None)


def _compute_audio_hash(text: str, voice_key: str, language: str) -> str:
    payload = "|".join([voice_key, language, text])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalise_text(text: str) -> str:
    return text.strip() if text else ""


def ensure_slot(state: ConversationState, prompt: VoicePrompt, language: str) -> Tuple[ConversationSlot, str, Optional[str]]:
    """Ensure the conversation has a slot for the prompt/language combination."""

    voice_key = prompt.voice_key
    state.touch()

    for name, slot in state.slots.items():
        if slot.voice_key == voice_key and slot.language == language:
            slot.prompt = prompt
            slot.touch()
            return slot, name, None

    if "primary" not in state.slots:
        slot_name = "primary"
        evicted = None
    elif "secondary" not in state.slots:
        slot_name = "secondary"
        evicted = None
    else:
        slot_name, evicted_slot = min(state.slots.items(), key=lambda item: item[1].last_used)
        logger.info(
            "Conversation %s replacing slot %s (voice=%s, language=%s) with voice=%s",
            state.conversation_id,
            slot_name,
            evicted_slot.voice_key,
            evicted_slot.language,
            voice_key,
        )
        CONVERSATION_SLOT_EVICTIONS.inc()
        state.slots.pop(slot_name)
        evicted = slot_name

    slot = ConversationSlot(name=slot_name, voice_key=voice_key, language=language, prompt=prompt)
    state.slots[slot_name] = slot
    logger.info(
        "Conversation %s using slot %s for voice=%s language=%s",
        state.conversation_id,
        slot_name,
        voice_key,
        language,
    )
    return slot, slot_name, evicted


def get_cached_audio(conversation_id: str, slot: ConversationSlot, text: str, language: str) -> Optional[bytes]:
    """Return cached audio for the given slot/text if available."""

    key = _compute_audio_hash(_normalise_text(text), slot.voice_key, language)
    audio = slot.audio_cache.get(key)
    if audio is not None:
        slot.last_audio_hash = key
        slot.touch()
        CONVERSATION_AUDIO_CACHE_HITS.inc()
        logger.info(
            "Conversation %s slot %s cache hit for hash %s",
            conversation_id,
            slot.name,
            key,
        )
        return audio

    CONVERSATION_AUDIO_CACHE_MISSES.inc()
    return None


def store_audio(conversation_id: str, slot: ConversationSlot, text: str, language: str, audio_bytes: bytes) -> str:
    """Store generated audio in the slot cache."""

    key = _compute_audio_hash(_normalise_text(text), slot.voice_key, language)
    slot.audio_cache[key] = audio_bytes
    slot.last_audio_hash = key
    slot.touch()

    while len(slot.audio_cache) > Config.CONVERSATION_AUDIO_CACHE_SIZE:
        slot.audio_cache.popitem(last=False)

    logger.info(
        "Conversation %s stored audio hash %s for slot %s (voice=%s)",
        conversation_id,
        key,
        slot.name,
        slot.voice_key,
    )
    return key


async def reset_caches() -> None:
    """Reset caches (intended for tests)."""

    async with _voice_prompt_lock:
        _voice_prompt_cache.clear()
    async with _conversation_cache_lock:
        _conversation_cache.clear()


async def get_conversation_snapshot(conversation_id: str) -> Optional[Dict[str, Dict[str, Optional[str]]]]:
    """Return a lightweight snapshot of a conversation cache entry for debugging/tests."""

    async with _conversation_cache_lock:
        state = _conversation_cache.get(conversation_id)
        if state is None:
            return None
        snapshot: Dict[str, Dict[str, Optional[str]]] = {}
        for name, slot in state.slots.items():
            snapshot[name] = {
                "voice_key": slot.voice_key,
                "language": slot.language,
                "last_audio_hash": slot.last_audio_hash,
            }
        return snapshot


__all__ = [
    "get_or_load_voice_prompt",
    "invalidate_voice_prompt",
    "get_conversation_state",
    "ensure_slot",
    "get_cached_audio",
    "store_audio",
    "reset_caches",
    "get_conversation_snapshot",
]
