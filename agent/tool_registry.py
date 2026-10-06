"""
Tool Registry for InvoicePilot.
Maps tool names to Python callable implementations, descriptions, and parameter schemas.
Ensures the LLM model sees only function names, descriptions, and schemas, never internal implementations.
"""

from typing import Dict, Any, Callable, List, Tuple


class ToolRegistry:
    """
    Central registry for agent-executable tools.
    Supports single-entry registration and standardized tool execution.
    """

    def __init__(self):
        self._tools: Dict[str, Tuple[Callable, str, Dict[str, Any]]] = {}

    def register(self, name: str, func: Callable, description: str, parameters: Dict[str, Any]):
        """
        Register a single tool with its implementation function, description, and JSON parameter schema.

        Args:
            name: String name of the tool (e.g. 'goto', 'read_page').
            func: Python callable executing the tool logic.
            description: Concise description explaining what the tool does.
            parameters: JSON schema object defining arguments, types, and required fields.
        """
        self._tools[name] = (func, description, parameters)

    def get_schemas(self) -> List[Dict[str, Any]]:
        """
        Return function declaration schemas for all registered tools to send to the LLM.
        """
        schemas = []
        for name, (_, description, parameters) in self._tools.items():
            schemas.append({
                "name": name,
                "description": description,
                "parameters": parameters
            })
        return schemas

    def execute(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Safely execute a registered tool by name with provided arguments.

        Returns:
            Dict containing {'ok': bool, 'observation': str, 'error': Optional[str]}
        """
        if name not in self._tools:
            err = f"Tool '{name}' is not registered in ToolRegistry."
            return {"ok": False, "observation": f"Tool execution failed: {err}", "error": err}

        func, _, _ = self._tools[name]
        try:
            result = func(**args)
            if isinstance(result, dict) and "ok" in result and "observation" in result:
                return result
            return {"ok": True, "observation": str(result), "error": None}
        except TypeError as te:
            err = f"Invalid arguments passed to tool '{name}': {str(te)}"
            return {"ok": False, "observation": f"Tool execution failed: {err}", "error": err}
        except Exception as e:
            err = f"Execution error in tool '{name}': {str(e)}"
            return {"ok": False, "observation": f"Tool execution failed: {err}", "error": err}
