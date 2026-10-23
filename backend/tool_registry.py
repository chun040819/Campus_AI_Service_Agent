from dataclasses import dataclass
from typing import Any, Callable

from jsonschema import Draft202012Validator


def error(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": message}}


def _trim_strings(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return [_trim_strings(item) for item in value]
    if isinstance(value, dict):
        return {key: _trim_strings(item) for key, item in value.items()}
    return value


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters_schema: dict[str, Any]
    handler: Callable[..., dict[str, Any]]
    category: str


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        import inspect

        Draft202012Validator.check_schema(tool.parameters_schema)
        parameters = inspect.signature(tool.handler).parameters
        if tool.name in self._tools or set(parameters) != set(tool.parameters_schema["properties"]):
            raise ValueError("Duplicate tool or schema/handler mismatch")
        self._tools[tool.name] = tool

    def schemas(self) -> list[dict[str, Any]]:
        return [{"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters_schema}} for t in self._tools.values()]

    def execute(self, name: str, arguments: Any) -> dict[str, Any]:
        if name not in self._tools:
            return error("INVALID_ARGUMENT", "未註冊的工具")
        tool = self._tools[name]
        arguments = _trim_strings(arguments)
        if list(Draft202012Validator(tool.parameters_schema).iter_errors(arguments)):
            return error("INVALID_ARGUMENT", "工具參數不符合規格")
        # JSON Schema permits 1.0 as integer; this contract requires JSON integers.
        for key, schema in tool.parameters_schema["properties"].items():
            if schema.get("type") == "integer" and key in arguments and type(arguments[key]) is not int:
                return error("INVALID_ARGUMENT", "工具參數必須為整數")
        try:
            return tool.handler(**arguments)
        except Exception:
            return error("INTERNAL_ERROR", "工具暫時無法使用")
