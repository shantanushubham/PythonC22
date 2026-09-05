from django.http import JsonResponse


class MyMiddleware:

    def __init__(self, get_response) -> None:
        self.get_response = get_response

    def __call__(self, request) -> JsonResponse:
        print(f"{request.method} - {request.path}")  # /users/1/ - GET
        response = self.get_response(request)
        print(f"Response Status: {response.status_code}")
        return response


# JWT auth now lives in tasks.authentication.JwtAuthentication
# Request -> Middleware -> View
# Response <-  Middleware <-
