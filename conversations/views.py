from __future__ import annotations

from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import ConversationSession, ConversationMessage
from .serializers import ConversationSessionSerializer, ConversationMessageSerializer


def _resolve_session_queryset(request, profile_id: str):
    """
    If authenticated: sessions for that user.
    Else: sessions matching profile_id.
    """
    u = getattr(request, "user", None)
    if u is not None and getattr(u, "is_authenticated", False):
        return ConversationSession.objects.filter(user=u)
    return ConversationSession.objects.filter(profile_id=(profile_id or "default").strip())


@api_view(["GET"])
def session_list(request):
    profile_id = (request.query_params.get("profile_id") or "default").strip()
    loved_one_id = request.query_params.get("loved_one_id")

    qs = _resolve_session_queryset(request, profile_id).order_by("-last_activity_at", "-started_at")

    if loved_one_id:
        qs = qs.filter(loved_one_id=loved_one_id)

    limit = int(request.query_params.get("limit") or 50)
    limit = max(1, min(200, limit))
    qs = qs[:limit]

    data = ConversationSessionSerializer(qs, many=True).data
    return Response({"ok": True, "items": data})


@api_view(["GET"])
def message_list(request):
    profile_id = (request.query_params.get("profile_id") or "default").strip()
    session_id = request.query_params.get("session_id")
    if not session_id:
        return Response({"ok": False, "error": "session_id is required"}, status=400)

    sess_qs = _resolve_session_queryset(request, profile_id)
    session = sess_qs.filter(id=session_id).select_related("loved_one", "user").first()
    if not session:
        return Response({"ok": False, "error": "not_found"}, status=404)

    qs = ConversationMessage.objects.filter(session=session).order_by("seq", "created_at")

    limit = int(request.query_params.get("limit") or 200)
    limit = max(1, min(1000, limit))
    offset = int(request.query_params.get("offset") or 0)
    offset = max(0, offset)

    page = qs[offset : offset + limit]
    data = ConversationMessageSerializer(page, many=True).data

    # include dynamic display names (NOT stored in DB per message)
    sess_data = ConversationSessionSerializer(session).data

    return Response(
        {
            "ok": True,
            "session": {
                "id": sess_data.get("id"),
                "profile_id": sess_data.get("profile_id"),
                "user_display": sess_data.get("user_display"),
                "loved_one_id": sess_data.get("loved_one"),
                "loved_one_name": sess_data.get("loved_one_name"),
                "started_at": sess_data.get("started_at"),
                "ended_at": sess_data.get("ended_at"),
            },
            "count": qs.count(),
            "offset": offset,
            "limit": limit,
            "items": data,
        }
    )


@api_view(["POST"])
def session_end(request):
    profile_id = (request.data.get("profile_id") or "default").strip()
    session_id = request.data.get("session_id")
    if not session_id:
        return Response({"ok": False, "error": "session_id is required"}, status=400)

    sess_qs = _resolve_session_queryset(request, profile_id)
    session = sess_qs.filter(id=session_id).first()
    if not session:
        return Response({"ok": False, "error": "not_found"}, status=404)

    if not session.ended_at:
        session.ended_at = timezone.now()
        session.save(update_fields=["ended_at"])

    return Response({"ok": True, "ended_at": session.ended_at})
