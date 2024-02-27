from fly.exception import App_Init_Error


class MiddlewareInitialCheckFailedError(App_Init_Error):
    pass


class MiddlewareAlreadyRegisteredError(App_Init_Error):
    pass
