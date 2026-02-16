import strawberry
from .types import MeResponse, LovedOneType
from graphql import GraphQLError
from voice.models import LovedOne
@strawberry.type
class Query:
    @strawberry.field
    def me(self, info) -> MeResponse:
        user = info.context.get("request").user
        print(user)
        if user is None or user.is_anonymous:
           raise GraphQLError("Authentication failed", extensions={"code": "UNAUTHENTICATED"})
        return MeResponse(
            user = user,
        )
    
    @strawberry.field
    def loved_ones(self, info, limit: int=10, offset: int=20) -> list[LovedOneType]:
        user = info.context.get("request").user
        if user is None or user.is_anonymous:
           raise GraphQLError("Authentication failed", extensions={"code": "UNAUTHENTICATED"})
        return LovedOne.objects.filter(user=user).order_by("-created_at")[offset:offset+limit]
