from user_app.context import reset_current_user, set_current_user


class CurrentUserMiddleware:
    """
    Resets the current-user ContextVar to None at the start of every request
    so that an unauthenticated request (or an anonymous request on a reused
    thread) can never inherit a user from a previous request.

    The actual user is written into the ContextVar by
    ContextAwareJWTAuthentication.authenticate(), which runs later (inside
    DRF's perform_authentication step).  This middleware is only responsible
    for the clean-up bookkeeping.
    """

    def __init__(self, get_response) -> None:
        self.get_response = get_response

    def __call__(self, request):
        token = set_current_user(None)
        try:
            return self.get_response(request)
        finally:
            reset_current_user(token)
