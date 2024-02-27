import inspect
from functools import wraps
from typing import Annotated, Any, Optional, get_args, get_origin

from pydantic import BaseModel

from fly.exception import HTTP_400_BAD_REQUEST, HTTP_500_INTERNAL_SERVER_ERROR
from fly.utils import logger


class BaseParam:
    def __init__(self, val_name: Optional[str] = None, val_from: Optional[str] = None):
        self.val_name = val_name
        self.val_from = val_from


class HeaderParam(BaseParam):
    def __init__(self, val_name: Optional[str] = None):
        super().__init__(val_name, "header")


class QueryParam(BaseParam):
    def __init__(self, val_name: Optional[str] = None):
        super().__init__(val_name, "query")


class PathParam(BaseParam):
    def __init__(self, val_name: Optional[str] = None):
        super().__init__(val_name, "path")


class CookieParam(BaseParam):
    def __init__(self, val_name: Optional[str] = None):
        super().__init__(val_name, "cookie")


class BodyParam(BaseModel):
    pass


dynamic_schema_registry: dict[object, BaseModel] = {}


def validate_original_schema(_type, value):
    if _type in dynamic_schema_registry:
        _schema_kls = dynamic_schema_registry[_type]
    else:

        class DynamicSchema(BaseModel):
            value: _type

        dynamic_schema_registry[_type] = DynamicSchema
        _schema_kls = DynamicSchema

    return _schema_kls(value=value).value


def validate_schema(sig, input_d: dict[str, Any], is_response=False):
    # logger.debug(f"validate_schema - {sig}({type(sig)}) {input_d}")
    resp = {}
    try:
        if is_response:
            ra = sig.return_annotation
            resp = input_d
            if issubclass(ra, BaseModel):
                resp = ra(**input_d).model_dump()
            elif ra is not inspect._empty:
                resp = validate_original_schema(sig.return_annotation, input_d)
            return resp

        for name, param in sig.parameters.items():
            expected_type = param.annotation

            default = param.default if param.default is not inspect.Parameter.empty else None
            value = input_d.get(name, default)

            # logger.debug(f"--> validate_schema - {name} {expected_type} {default} {value}")

            if get_origin(expected_type) is Annotated:  # Annotated[<type>, Something]
                inner_type, _ = get_args(expected_type)
                value = validate_original_schema(inner_type, value)
            elif issubclass(expected_type, BaseModel):  # subclass of BaseModel
                value = expected_type(**value).model_dump()
            elif expected_type is not inspect._empty:  # int str or list[str] etc
                value = validate_original_schema(expected_type, value)
            # elif expected_type is inspect._empty: # no annotation
            #     logger.warning(f"validate_schema - {name} has no annotation")

            resp[name] = value
    except Exception as e:
        raise SchemaValidationFailed(f"Schema validation failed: {name}-{input_d}-{is_response} :{e}") from e
    return resp


async def process_request(request, route_func, extra_params=None):
    # func_name = f"{route_func.__module__}.{route_func.__name__}"

    param_type_dict = {
        "path": request.path_params,
        "query": request.query_params,
        "header": request.header,
        "cookie": request.cookie,
    }
    extra_params = extra_params or {}

    def get_from_params(name, dict_key=None):
        # logger.debug(f"get_from_params - {func_name} {name} {dict_key}")
        if dict_key is not None:
            return param_type_dict[dict_key].get(name)
        res = [params[name] for _, params in param_type_dict.items() if name in params]
        return res[0] if res else None

    sig = inspect.signature(route_func)
    input_d = {}

    for name, param in sig.parameters.items():
        expected_type = param.annotation

        if get_origin(expected_type) is Annotated:  # Annotated[<type>, HeaderParam("name")] / Annotated[<type>, PathParam("name")] ..
            _, param_info = get_args(expected_type)
            input_d[name] = get_from_params(name, param_info.val_from)
        elif issubclass(expected_type, BaseModel):  # for BodyParam acutally
            input_d[name] = await request.body.dict()
        elif name in extra_params:  # if in extra_params, use it
            input_d[name] = extra_params[name]
        else:  # else may appears in path/query/header/cookie - use it
            input_d[name] = get_from_params(name)

    try:
        func_args = validate_schema(sig, input_d)
    except SchemaValidationFailed as e:
        raise RequestSchemaValidationFailed(f"Request schema validation failed: {e}") from e
    return func_args


async def process_response(response, route_func):
    try:
        response = validate_schema(inspect.signature(route_func), response, is_response=True)
    except SchemaValidationFailed as e:
        raise ResponseSchemaValidationFailed(f"Response schema validation failed: {e}") from e
    return response


def validate_it(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # 获取函数签名
        sig = inspect.signature(func)
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()
        input_d = bound_args.arguments
        # logger.debug(f"validate_it - func: {func.__module__}.{func.__name__} input:{input_d}")
        validated_args = validate_schema(sig, input_d)
        resp = func(**validated_args)
        resp = validate_schema(sig, resp, is_response=True)
        return resp

    return wrapper


class SchemaValidationFailed(HTTP_500_INTERNAL_SERVER_ERROR):
    pass


class RequestSchemaValidationFailed(HTTP_400_BAD_REQUEST, SchemaValidationFailed):
    pass


class ResponseSchemaValidationFailed(SchemaValidationFailed):
    pass
    # logger.debug(f"--> validate_schema - {name} {expected_type} {default} {value}")
