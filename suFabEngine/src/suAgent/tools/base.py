from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass

@dataclass
class Tool:
    name: str
    description: str
    function: Callable
    required_args: List[str]
    optional_args: Optional[Dict[str, Any]] = None

    def validate_args(self, **kwargs):
        for arg in self.required_args:
            if arg not in kwargs:
                raise ValueError(f"Missing required argument: {arg}")

    def __call__(self, **kwargs):
        self.validate_args(**kwargs)
        return self.function(**kwargs)


class ToolSystem:
    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register_tool(self, tool: Tool):
        """注册新工具到系统"""
        if tool.name in self._tools:
            raise ValueError(f"Tool {tool.name} already exists")
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Tool:
        """获取指定工具"""
        if name not in self._tools:
            raise ValueError(f"Tool {name} not found")
        return self._tools[name]

    def list_tools(self) -> List[Dict[str, str]]:
        """列出所有可用工具"""
        return [{"name": t.name, "description": t.description}
                for t in self._tools.values()]