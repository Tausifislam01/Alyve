import strawberry 
from accounts.models import User
from typing import Optional
from voice.models import LovedOne, Memory, VoiceSample

@strawberry.django.type(User)
class UserType:
    id: strawberry.auto
    full_name: strawberry.auto
    email: strawberry.auto
    is_active: strawberry.auto

# @strawberry.type
# class ErrorType:
#     message: str
#     code: Optional[str] = None
#
@strawberry.type
class MeResponse:
    user: Optional['UserType']
    # error: Optional['ErrorType']

@strawberry.type
class AuthPayload:
    access_token: Optional[str]
    refresh_token: Optional[str]
    # error: Optional[ErrorType]

@strawberry.type
class RegisterPayload:
    success: bool
    # error: Optional[ErrorType]

@strawberry.type
class VerifyOTPPayload:
    success: bool
    # error: Optional[ErrorType]
    
@strawberry.type
class RefreshPayload:
    access_token: Optional[str]
    refresh_token: Optional[str]

@strawberry.type
class SentOTPPayload:
    success: bool

@strawberry.type
class CheckOTPPayload:
    valid: bool

@strawberry.type
class ChangePasswordPayload:
    success: bool

@strawberry.django.type(LovedOne)
class LovedOneType:
    id: strawberry.auto
    name: strawberry.auto
    relationship: strawberry.auto
    nickname_for_user: strawberry.auto
    description: strawberry.auto
    last_conversation_at: strawberry.auto
    speaking_style: strawberry.auto
    catch_phrase: strawberry.auto
    created_at: strawberry.auto
