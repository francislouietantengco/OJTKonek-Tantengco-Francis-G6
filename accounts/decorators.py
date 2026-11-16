from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def role_required(*roles):
    """
    Allow only logged-in users whose role is in `roles` (BR-05).
      - Logged-out user  -> sent to the login page (by @login_required)
      - Wrong role       -> sent back to their own dashboard with an error message
    """

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.role not in roles:
                messages.error(request, "You do not have permission to open that page.")
                return redirect("accounts:dashboard")
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
