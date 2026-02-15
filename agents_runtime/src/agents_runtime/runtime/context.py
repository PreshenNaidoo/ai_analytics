"""Runtime context assembly."""


from dataclasses import dataclass
from typing import Any

from agents_runtime.config import RuntimeSettings
from agents_runtime.mcp.servers import MCPServers
from agents_runtime.memory.store import create_chroma_client, create_embedding_function


@dataclass
class RuntimeContext:
    """Holds shared runtime objects for one execution context."""
    settings: RuntimeSettings
    servers: MCPServers
    chroma_client: Any
    embedding_fn: Any

    @property
    def mssql_server(self):
        """Shortcut access to the MSSQL MCP server."""
        return self.servers.mssql_server

    @property
    def chart_server(self):
        """Shortcut access to the chart MCP server."""
        return self.servers.chart_server

    @property
    def pdf_reader_server(self):
        """Shortcut access to the PDF reader MCP server."""
        return self.servers.pdf_reader_server

    @property
    def word_reader_server(self):
        """Shortcut access to the Word reader MCP server."""
        return self.servers.word_reader_server

    @property
    def excel_server(self):
        """Shortcut access to the Excel MCP server."""
        return self.servers.excel_server

    @staticmethod
    def create(settings: RuntimeSettings, servers: MCPServers) -> "RuntimeContext":
        """Build a context with Chroma client and embedding function."""
        return RuntimeContext(
            settings=settings,
            servers=servers,
            chroma_client=create_chroma_client(settings.chroma_dir),
            embedding_fn=create_embedding_function(),
        )
