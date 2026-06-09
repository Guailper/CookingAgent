"""Shared pytest setup for backend tests."""

import importlib.util
import sys
import types

if importlib.util.find_spec("langchain_mcp_adapters") is None:
    fake_mcp_package = types.ModuleType("langchain_mcp_adapters")
    fake_mcp_client_module = types.ModuleType("langchain_mcp_adapters.client")

    class _FakeMultiServerMCPClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            _ = args
            _ = kwargs

        async def get_tools(self) -> list[object]:
            return []

    fake_mcp_client_module.MultiServerMCPClient = _FakeMultiServerMCPClient
    fake_mcp_package.client = fake_mcp_client_module
    sys.modules["langchain_mcp_adapters"] = fake_mcp_package
    sys.modules["langchain_mcp_adapters.client"] = fake_mcp_client_module
