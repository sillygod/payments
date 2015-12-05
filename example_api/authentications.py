from rest_framework.authentication import BaseAuthentication
from django.contrib.auth import get_user_model


class EnableExternalRequest(BaseAuthentication):

    """this is a special authentication which removed the
    csrf check for SessionAuthentication.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def authenticate(self, request):
        """no need to authenticate requester
        """

        User = get_user_model()
        user = User.objects.all()[0]

        return (user, None)


    def enforce_csrf(self, request):
        """overwrite this one to disable csrf check
        """
        print('enter')
