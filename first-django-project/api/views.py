from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def hello(request):
    return Response({"message": "Hello from AirTribe"})

@api_view(["GET"])
def add_two_numbers(request):
    try:
        a = int(request.query_params.get("a"))
        b = int(request.query_params.get("b"))
    except (TypeError, ValueError):
        return Response(
            {"error": "'a' and 'b' must be numbers."},
            status=400,
        )
    return Response({"sum": a + b})
