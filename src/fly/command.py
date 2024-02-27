from argparse import ArgumentParser

from fly.exception import App_Init_Error, App_Internal_Error


class CommandManager:
    main_parser = ArgumentParser()
    sub_parser = main_parser.add_subparsers(dest="command", help="available commands")

    def __init__(self, app):
        self._app = app
        self._signal = app._signal

    def execute(self):
        args = self.main_parser.parse_args()
        command = args.command
        if command is None:
            self.main_parser.print_help()
            return
        cmd_args = vars(args)
        cmd_func, _ = cmd_args.pop("func"), cmd_args.pop("command")
        cmd_func(self._app, **cmd_args)


class _CommandMeta(type):
    def __init__(cls, name, bases, attrs):
        super().__init__(name, bases, attrs)
        if name != "BaseAppCommand":
            cls.add_arguments()
            cls.parser.set_defaults(func=cls.handle)

    def __new__(cls, name, bases, attrs):
        if name == "BaseAppCommand":
            return super().__new__(cls, name, bases, attrs)
        if "command" not in attrs:
            raise CommandInitError("Command must have a 'command' attribute to specify the command name")
        if "description" not in attrs:
            attrs["description"] = ""
        command = attrs["command"]
        if command in CommandManager.sub_parser.choices:
            raise CommandDuplicateError(f"Command '{command}' already exists")
        if any(item not in attrs for item in ("add_arguments", "handle")):
            raise CommandInitError(f"Command '{command}' must have 'add_arguments' and 'handle' methods")
        attrs["parser"] = CommandManager.sub_parser.add_parser(attrs["command"], description=attrs["description"])
        # # logger.debug(f"Register command: {command}")
        return super().__new__(cls, name, bases, attrs)


class BaseAppCommand(metaclass=_CommandMeta):
    command = ""
    description = ""

    def __init__(self):
        pass

    @classmethod
    def add_arguments(cls):
        pass

    @classmethod
    def handle(cls, app):
        pass


class CommandInitError(App_Init_Error):
    pass


class CommandDuplicateError(App_Init_Error):
    pass


class CommandNotFoundError(App_Internal_Error):
    pass


class AppRunCommand(BaseAppCommand):
    command = "run"
    description = "run the app"

    @classmethod
    def add_arguments(cls):
        cls.parser.add_argument("--host", default="0.0.0.0", help="host to run")
        cls.parser.add_argument("--port", "-p", default=5000, help="port to run")
        cls.parser.add_argument("--debug", default=False, action="store_true", help="debug mode")

    @classmethod
    def handle(cls, app, host, port, debug):
        port = int(port)
        app.run(host, port, debug)
