from fly.exception import HTTP_500_INTERNAL_SERVER_ERROR


class SignaleNotFoundError(HTTP_500_INTERNAL_SERVER_ERROR):
    pass


class SignalCallbackError(HTTP_500_INTERNAL_SERVER_ERROR):
    pass
