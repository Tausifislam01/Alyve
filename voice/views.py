from __future__ import annotations

import os
import requests
import uuid

from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from django.conf import settings

from .models import LovedOne
from .rag_factory import get_rag


_rag = get_rag()


def _lo_queryset_for_profile(profile_id: str, request=None):
    """
    New models.py uses LovedOne.user (FK) instead of profile_id.
    Backward-compat:
      - if request.user authenticated => use that
      - else if profile_id is numeric => treat as user_id
      - else => user is NULL (default/anonymous)
    Returns: (queryset, profile_key_for_rag)
    """
    if request is not None:
        u = getattr(request, "user", None)
        if u is not None and getattr(u, "is_authenticated", False):
            return LovedOne.objects.filter(user=u)

    return LovedOne.objects.none()

def _maybe_clone_eleven_voice(lo: LovedOne, sample_paths: list[str]) -> str:
    """
    Create an ElevenLabs cloned voice if LovedOne.eleven_voice_id is empty.
    Returns the existing/new voice_id, or "" if ELEVENLABS_API_KEY is not set.
    """
    api_key = settings.VOICE_APP.get("ELEVENLABS_API_KEY") or os.getenv("ELEVENLABS_API_KEY", "")
    if not api_key:
        return getattr(lo, "eleven_voice_id", "") or ""

    existing = getattr(lo, "eleven_voice_id", "") or ""
    if existing:
        return existing

    base_url = (settings.VOICE_APP.get("ELEVENLABS_BASE_URL") or os.getenv("ELEVENLABS_BASE_URL", "")).rstrip("/")
    if not base_url:
        raise RuntimeError("ELEVENLABS_BASE_URL must be set")

    url = f"{base_url}/v1/voices/add"
    headers = {"xi-api-key": api_key}

    name = (getattr(lo, "name", "") or "").strip() or f"lovedone-{lo.id}"
    data = {
        "name": name,
        "description": f"Cloned voice for LovedOne id={lo.id}",
    }

    print(f"file paths for cloning: {sample_paths}")
    files = []
    for p in sample_paths:
        try:
            fp = open(p, "rb")
        except OSError:
            continue
        files.append(("files", fp))

    if not files:
        return existing

    try:
        r = requests.post(url, headers=headers, data=data, files=files, timeout=90)
    finally:
        for _, fp in files:
            try:
                fp.close()
            except Exception:
                pass

    if r.status_code >= 400:
        raise RuntimeError(f"ElevenLabs clone failed: {r.status_code} {r.text[:400]}")

    j = r.json()
    voice_id = (j.get("voice_id") or "").strip()
    if not voice_id:
        raise RuntimeError("ElevenLabs clone returned no voice_id")

    if hasattr(lo, "eleven_voice_id"):
        lo.eleven_voice_id = voice_id
        lo.save(update_fields=["eleven_voice_id"])

    return voice_id


@api_view(["POST"])
@parser_classes([JSONParser])
def lovedone_create(request):
    profile_id = (request.data.get("profile_id") or "default").strip()
    name = (request.data.get("name") or "").strip()
    relationship = (request.data.get("relationship") or "").strip()
    nickname_for_user = (request.data.get("nickname_for_user") or "").strip()
    speaking_style = (request.data.get("speaking_style") or "").strip()

    # NEW (user-based): decide which user to attach, if any
    user = None
    if getattr(request, "user", None) is not None and request.user.is_authenticated:
        user = request.user
    elif profile_id.isdigit():
        # Assign by FK id without importing User
        lo = LovedOne.objects.create(
            user_id=int(profile_id),
            name=name,
            relationship=relationship,
            nickname_for_user=nickname_for_user,
            speaking_style=speaking_style,
        )
        return Response({"ok": True, "loved_one_id": lo.id})

    lo = LovedOne.objects.create(
        user=user,  # None => anonymous/default
        name=name,
        relationship=relationship,
        nickname_for_user=nickname_for_user,
        speaking_style=speaking_style,
    )
    return Response({"ok": True, "loved_one_id": lo.id})


@api_view(["GET"])
def lovedone_list(request):
    profile_id = (request.query_params.get("profile_id") or "default").strip()
    qs, _profile_key = _lo_queryset_for_profile(profile_id, request=request)

    items = qs.order_by("-created_at")
    data = []
    for lo in items:
        data.append(
            {
                "id": lo.id,
                "name": lo.name,
                "relationship": lo.relationship,
                "nickname_for_user": lo.nickname_for_user,
                "speaking_style": lo.speaking_style,
                "eleven_voice_id": getattr(lo, "eleven_voice_id", "") or "",
                "created_at": lo.created_at.isoformat() if getattr(lo, "created_at", None) else None,
                # New fields (safe to include; won't break old clients)
                "catch_phrase": getattr(lo, "catch_phrase", "") or "",
                "description": getattr(lo, "description", "") or "",
                "core_memories": getattr(lo, "core_memories", "") or "",
                "last_conversation_at": lo.last_conversation_at.isoformat()
                if getattr(lo, "last_conversation_at", None)
                else None,
                "voice_file": lo.voice_file.url if getattr(lo, "voice_file", None) else None,
            }
        )
    return Response({"ok": True, "items": data})


@api_view(["GET"])
def lovedone_get(request):
    profile_id = (request.query_params.get("profile_id") or "default").strip()
    loved_one_id = request.query_params.get("loved_one_id")
    if not loved_one_id:
        return Response({"error": "loved_one_id is required"}, status=400)

    qs = _lo_queryset_for_profile(profile_id, request=request)
    print(f"Debug: lovedone_get qs={qs}")
    print(f"Debug: lovedone_get filter id={loved_one_id}")
    lo = qs.filter(id=loved_one_id).first()
    if not lo:
        return Response({"error": "not_found"}, status=404)

    return Response(
        {
            "ok": True,
            "item": {
                "id": lo.id,
                "name": lo.name,
                "relationship": lo.relationship,
                "nickname_for_user": lo.nickname_for_user,
                "speaking_style": lo.speaking_style,
                "eleven_voice_id": getattr(lo, "eleven_voice_id", "") or "",
                "created_at": lo.created_at.isoformat() if getattr(lo, "created_at", None) else None,
                "catch_phrase": getattr(lo, "catch_phrase", "") or "",
                "description": getattr(lo, "description", "") or "",
                "core_memories": getattr(lo, "core_memories", "") or "",
                "last_conversation_at": lo.last_conversation_at.isoformat()
                if getattr(lo, "last_conversation_at", None)
                else None,
                "voice_file": lo.voice_file.url if getattr(lo, "voice_file", None) else None,
            },
        }
    )


@api_view(["POST"])
@parser_classes([JSONParser])
def add_memory(request):
    profile_id = (request.data.get("profile_id") or "default").strip()
    loved_one_id = request.data.get("loved_one_id")
    text = (request.data.get("text") or "").strip()

    if not loved_one_id:
        return Response({"error": "loved_one_id is required"}, status=400)
    if not text:
        return Response({"error": "text is required"}, status=400)

    qs, profile_key = _lo_queryset_for_profile(profile_id, request=request)
    lo = qs.filter(id=loved_one_id).first()
    if not lo:
        return Response({"error": "loved_one not found"}, status=404)

    # NEW: Memory model removed -> append into LovedOne.core_memories
    existing = (getattr(lo, "core_memories", "") or "").strip()
    lo.core_memories = (existing + "\n" + text).strip() if existing else text
    lo.save(update_fields=["core_memories"])

    memory_id = uuid.uuid4().hex

    indexed_ids = _rag.add_memory(
        profile_id=profile_key,
        loved_one_id=int(lo.id),
        text=text,
        memory_id=memory_id,
    )

    return Response({"ok": True, "memory_id": memory_id, "indexed_ids": indexed_ids})


@api_view(["POST"])
@parser_classes([MultiPartParser, FormParser])
def upload_voice_sample(request):
    profile_id = (request.data.get("profile_id") or "default").strip()
    loved_one_id = request.data.get("loved_one_id")
    f = request.FILES.get("file")
    force_reclone = request.data.get("force_reclone")

    if not loved_one_id:
        return Response({"error": "loved_one_id is required"}, status=400)
    if not f:
        return Response({"error": "file is required"}, status=400)

    qs, _profile_key = _lo_queryset_for_profile(profile_id, request=request)
    lo = qs.filter(id=loved_one_id).first()
    if not lo:
        return Response({"error": "loved_one not found"}, status=404)

    # Optional: force re-clone (reset existing eleven_voice_id before cloning).
    fr = str(force_reclone or "").strip().lower()
    if fr in ("1", "true", "yes", "y", "on"):
        if hasattr(lo, "eleven_voice_id") and (getattr(lo, "eleven_voice_id", "") or ""):
            lo.eleven_voice_id = ""
            lo.save(update_fields=["eleven_voice_id"])

    # NEW: VoiceSample model removed -> store file directly on LovedOne.voice_file
    lo.voice_file = f
    lo.save(update_fields=["voice_file"])

    voice_id = getattr(lo, "eleven_voice_id", "") or ""

    # Clone gating (env-driven)
    min_samples = int(settings.VOICE_APP.get("ELEVENLABS_MIN_SAMPLES_FOR_CLONE", 1) or 1)
    max_files = int(settings.VOICE_APP.get("ELEVENLABS_MAX_FILES_FOR_CLONE", 5) or 5)

    # With the new schema we typically have only one file, but keep the same gating contract.
    samples_count = 1

    sample_paths = []
    try:
        if getattr(lo, "voice_file", None) and hasattr(lo.voice_file, "path"):
            sample_paths = [lo.voice_file.path][:max_files]
    except Exception:
        sample_paths = []

    if (not voice_id) and (samples_count >= min_samples):
        try:
            voice_id = _maybe_clone_eleven_voice(lo, sample_paths)
        except Exception as e:
            return Response(
                {
                    "ok": True,
                    "voice_file_saved": True,
                    "warning": f"clone_failed: {type(e).__name__}: {e}",
                    "samples_count": samples_count,
                    "min_samples_for_clone": min_samples,
                }
            )

    return Response(
        {
            "ok": True,
            "voice_file_saved": True,
            "eleven_voice_id": voice_id,
            "samples_count": samples_count,
            "min_samples_for_clone": min_samples,
            "has_cloned_voice": bool(voice_id),
        }
    )
