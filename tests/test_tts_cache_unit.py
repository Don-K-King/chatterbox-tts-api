import asyncio

import pytest

from app.core.tts_cache import (
    reset_caches,
    get_or_load_voice_prompt,
    get_conversation_state,
    ensure_slot,
    store_audio,
    get_cached_audio,
    get_conversation_snapshot,
)


@pytest.mark.parametrize("languages", [("en", "de"), ("de", "en")])
def test_conversation_cache_isolated_by_id(tmp_path, languages):
    voice_path = tmp_path / "voice.wav"
    voice_path.write_bytes(b"RIFF0000")

    text = "Hallo Welt"

    async def scenario():
        await reset_caches()
        prompt = await get_or_load_voice_prompt(str(voice_path))

        state_a = await get_conversation_state("session-a")
        async with state_a.lock:
            slot_a, _, _ = ensure_slot(state_a, prompt, languages[0])
            store_audio("session-a", slot_a, text, languages[0], b"audio-a")
            assert get_cached_audio("session-a", slot_a, text, languages[0]) == b"audio-a"

        state_b = await get_conversation_state("session-b")
        async with state_b.lock:
            slot_b, _, _ = ensure_slot(state_b, prompt, languages[0])
            assert get_cached_audio("session-b", slot_b, text, languages[0]) is None

        snapshot_a = await get_conversation_snapshot("session-a")
        snapshot_b = await get_conversation_snapshot("session-b")

        assert snapshot_a is not None
        assert snapshot_b is not None
        assert snapshot_a["primary"]["last_audio_hash"] is not None
        assert snapshot_b["primary"]["last_audio_hash"] is None

    asyncio.run(scenario())


def test_two_voice_slots_with_alternating_languages(tmp_path):
    voice_a = tmp_path / "voice_a.wav"
    voice_b = tmp_path / "voice_b.wav"
    voice_c = tmp_path / "voice_c.wav"
    voice_a.write_bytes(b"VOICEA")
    voice_b.write_bytes(b"VOICEB")
    voice_c.write_bytes(b"VOICEC")

    async def scenario():
        await reset_caches()
        prompt_a = await get_or_load_voice_prompt(str(voice_a))
        prompt_b = await get_or_load_voice_prompt(str(voice_b))
        prompt_c = await get_or_load_voice_prompt(str(voice_c))

        state = await get_conversation_state("alt-session")
        async with state.lock:
            slot_a, name_a, _ = ensure_slot(state, prompt_a, "de")
            store_audio("alt-session", slot_a, "eins", "de", b"eins")

            slot_b, name_b, _ = ensure_slot(state, prompt_b, "en")
            store_audio("alt-session", slot_b, "two", "en", b"zwei")

            # Ensure both slots exist and contain cached audio
            slot_a_repeat, name_a_repeat, _ = ensure_slot(state, prompt_a, "de")
            assert slot_a is slot_a_repeat
            assert get_cached_audio("alt-session", slot_a_repeat, "eins", "de") == b"eins"

            slot_b_repeat, name_b_repeat, _ = ensure_slot(state, prompt_b, "en")
            assert slot_b is slot_b_repeat
            assert get_cached_audio("alt-session", slot_b_repeat, "two", "en") == b"zwei"

            languages_before = {slot.language for slot in state.slots.values()}
            assert languages_before == {"de", "en"}

            # Introduce a third voice to trigger eviction of the least recently used slot
            slot_c, name_c, evicted = ensure_slot(state, prompt_c, "fr")
            store_audio("alt-session", slot_c, "trois", "fr", b"trois")
            assert evicted in {name_a, name_b}
            assert len(state.slots) == 2

        snapshot = await get_conversation_snapshot("alt-session")
        assert snapshot is not None
        assert len(snapshot) == 2
        assert any(slot["language"] == "fr" for slot in snapshot.values())

    asyncio.run(scenario())
