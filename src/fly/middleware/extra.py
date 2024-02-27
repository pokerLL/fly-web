from datetime import datetime, timedelta

import jwt

from fly.middleware.core import BaseMiddleware
from fly.response import JsonResponse


class JWTMiddleware(BaseMiddleware):
    """
    fly:
        JWT_SECRET: str = "fly"
        JWT_EXPIRE: int = 3600
    """

    async def process_request(self, request, response):
        token_header = request.headers.get("Authorization")
        if token_header is None:
            return JsonResponse({"error": "Authorization header is missing"}, status=401)

        try:
            token = token_header.split(" ")[1]
        except IndexError:
            return JsonResponse({"error": "Token format is invalid"}, status=401)

        try:
            payload = jwt.decode(token, capp.config.get("JWT_SECRET", "fly"), algorithms=["HS256"])
            request.user = payload
        except jwt.ExpiredSignatureError:
            return JsonResponse({"error": "Token has expired"}, status=401)
        except jwt.InvalidTokenError:
            return JsonResponse({"error": "Invalid token"}, status=401)

    async def process_response(self, request, response):
        user_payload = getattr(request, "user", None)

        if user_payload:
            exp = datetime.fromtimestamp(user_payload["exp"])
            now = datetime.now()
            if (exp - now) < timedelta(minutes=5):
                new_payload = {
                    "user_id": user_payload["user_id"],
                    "exp": datetime.timestamp(datetime.now() + timedelta(seconds=capp.config.get("JWT_EXPIRE", 3600))),
                }
                new_token = jwt.encode(new_payload, capp.config.get("JWT_SECRET", "fly"), algorithm="HS256")

                response.set_header("Authorization", f"Bearer {new_token}")

        return response
