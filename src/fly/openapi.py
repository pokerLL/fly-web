import inspect
import json
import os
import re
from pathlib import Path
from typing import Annotated, get_args, get_origin

from apispec import APISpec
from pydantic import BaseModel

from fly.constant import BuiltinSignal, RouteType
from fly.response import Response
from fly.utils import ConfigDict, logger, update_dict
from fly.command import BaseAppCommand


OPENAPI_DEFAULT_CONFIG = {
    "title": "title",
    "version": "1.0.0",
    "info": {
        "description": "Fly API of App",
    },
    # 前面三项可以从fly.config中获取 后面的从fly.config["openapi"]中获取
    # "servers": [{"url": "http://127.0.0.1:8000", "description": "Development server"}],
    "servers": [],
    "security": [{"ApiKeyAuth": []}],
    "openapi_route": "/openapi",
    "swagger_route": "/swagger",
    "output_fp": "openapi.json",
}


class FLyOpenAPISpec:
    def __init__(self, app, config):
        logger.debug(f"init openapi spec -> {type(config)} {config}")
        self.app = app
        self.spec = APISpec(
            title=config["title"],
            version=config["version"],
            info=config["info"],
            servers=config["servers"],
            security=config["security"],
            openapi_version="3.0.2",
        )
        self.has_generated = False
        self.spec.components.security_scheme("ApiKeyAuth", {"type": "apiKey", "in": "header", "name": "Authorization"})
        self._define_common_responses()

    def _define_common_responses(self):
        self.spec.components.response("NotFound", {"description": "Resource not found", "content": {"application/json": {"example": {"message": "Not found"}}}})
        self.spec.components.response(
            "Unauthorized", {"description": "Authorization information is missing or invalid", "content": {"application/json": {"example": {"message": "Unauthorized"}}}}
        )
        self.spec.components.response("BadRequest", {"description": "Invalid request", "content": {"application/json": {"example": {"message": "Bad request"}}}})

    def _parse_param(self, param, route_func):
        param_spec = {}
        expected_type = param.annotation
        param_type_name = str(expected_type.__name__) if expected_type != inspect._empty else "string"

        if get_origin(expected_type) is Annotated:
            inner_type, param_info = get_args(expected_type)
            param_type_name = str(inner_type.__name__)
            param_in = param_info.val_from
            param_spec = {"name": param_info.val_name or param.name, "in": param_in, "required": True, "schema": self._build_param_schema(inner_type, param_type_name)}
        elif issubclass(expected_type, BaseModel):
            schema = expected_type.schema()
            if self.spec.components.schemas.get(expected_type.__name__) is None:
                self.spec.components.schema(expected_type.__name__, schema)
            param_spec = {"name": param.name, "in": "body", "required": True, "schema": {"$ref": f"#/components/schemas/{expected_type.__name__}"}}
        else:
            param_spec = {
                "name": param.name,
                "in": "query",
                "required": False,
                "schema": self._build_param_schema(expected_type, param_type_name),
                "description": "Actually no matter where the param appeared, it will be parsed",
            }
        return param_spec

    def _build_param_schema(self, expected_type, type_name):
        if type_name == "list":
            item_type = get_args(expected_type)[0]
            item_type_name = str(item_type.__name__)
            return {"type": "array", "items": {"type": self._get_openapi_type(item_type_name)}}
        else:
            return {"type": self._get_openapi_type(type_name)}

    def _get_openapi_type(self, type_name):
        openapi_types = {"int": "integer", "float": "number", "str": "string", "bool": "boolean", "list": "array", "dict": "object"}
        return openapi_types.get(type_name, "string")

    def _convert_path(self, path):
        return re.sub(r"<(?:\w+:)?(\w+)>", r"{\1}", path)

    def generate_spec(self):
        self.has_generated = True
        for route in self.app._route.patterns:
            path = self._convert_path(route._path)
            route_func = route._func

            if hasattr(route_func, "_get_func"):
                for method in route_func._route_dict:
                    self._add_route_spec(route, path, method.lower(), getattr(route_func, method.lower()))
            else:
                for method in route._methods:
                    self._add_route_spec(route, path, method.lower(), route_func)

    def _add_route_spec(self, route, path, method, route_func):
        sig = inspect.signature(route_func)
        parameters = []
        request_body = None

        for name, param in sig.parameters.items():
            if name in ("cls", "self"):  # 忽略 cls 和 self 参数
                continue
            param_spec = self._parse_param(param, route_func)
            if param_spec["in"] == "body":
                request_body = {"required": True, "content": {"application/json": {"schema": param_spec["schema"]}}}
            else:
                parameters.append(param_spec)

        response_schema = {}
        if issubclass(sig.return_annotation, BaseModel):
            response_schema_name = sig.return_annotation.__name__
            if self.spec.components.schemas.get(response_schema_name) is None:
                response_schema = sig.return_annotation.schema()
                self.spec.components.schema(response_schema_name, response_schema)
            response_schema = {"$ref": f"#/components/schemas/{response_schema_name}"}

        operation = {
            "tags": [self._extract_tag_from_path(path)],
            "summary": f"{route.route_type.upper()} request",
            "description": inspect.getdoc(route_func) or "No detailed description provided",
            "parameters": parameters,
            "responses": {"200": {"description": "Successful Response", "content": {"application/json": {"schema": response_schema}}}},
        }

        if request_body:
            operation["requestBody"] = request_body

        self.spec.path(path=path, operations={method: operation})

    def _extract_tag_from_path(self, path):
        path_parts = path.strip("/").split("/")
        return path_parts[0] if path_parts and path_parts[0] else "index"

    def output_to_file(self, output_file):
        if not self.has_generated:
            self.generate_spec()
        with open(output_file, "w") as f:
            print(f"output to file: {os.path.realpath(output_file)}")
            f.write(json.dumps(self.spec.to_dict(), indent=2))


class FlyOpenAPIManager:
    def __init__(self, app):
        self._app = app
        self._signal = app._signal
        self._route = app._route
        self._spec = None
        self.config = None
        self._init()

    def _init(self):
        self._signal.connect(BuiltinSignal.APP_STARTUP, self.parse_config)
        self._signal.connect(BuiltinSignal.SERVER_STARTUP, self._register_route)

    def _register_route(self):
        self._spec = FLyOpenAPISpec(self._app, self.config)

        def openapi_file_route():
            if not os.path.exists(Path(self._app.root_path) / "openapi.json") or self._app.config.get("debug", False):
                self._spec.output_to_file(Path(self._app.root_path) / "openapi.json")
            content = Path(self._app.root_path).joinpath("openapi.json").read_text()
            resp = Response(200, content)
            resp.set_header("Content-Type", "text/plain")
            return resp

        def swagger_ui_route():
            # url: "/openapi.yaml"
            fp = Path(__file__).parent / "static" / "swagger.html"
            content = fp.read_text()
            content = content.replace("/openapi.yaml", self.config["openapi_route"])
            resp = Response(200, content)
            return resp

        self._route.add_route(self.config["openapi_route"], ["GET"], openapi_file_route, RouteType.NORMAL)
        self._route.add_route(self.config["swagger_route"], ["GET"], swagger_ui_route, RouteType.NORMAL)

    def parse_config(self):
        self.config = update_dict(OPENAPI_DEFAULT_CONFIG, self._app.config.get("openapi", {}))
        self.config["servers"].append({"url": f"http:{self._app.host_ip}:{self._app.port}/", "description": "Development server" if self._app.debug else "Production server"})


class FlyOpenApiCommand(BaseAppCommand):
    command = "swagger"
    description = "Generate OpenAPI spec and start the server"
    """
    Usgae:
        fly swagger gen [-o ./swagger.json]
    """

    @classmethod
    def add_arguments(cls):
        cls.parser.add_argument("action", choices=["gen"], help="action to perform")
        cls.parser.add_argument("-o", "--output", help="output file path")

    @classmethod
    def handle(cls, app, **kwargs):
        action = kwargs["action"]
        if action == "gen":
            output_fp = kwargs.get("output", "openapi.json")
            spec = FLyOpenAPISpec(app, update_dict(OPENAPI_DEFAULT_CONFIG, app.config, app.config.get("openapi", {})))
            spec.output_to_file(output_fp)
        else:
            raise NotImplementedError("Not implemented yet")
