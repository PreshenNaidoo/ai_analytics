"""MCP server factories for analytics runtime."""


from dataclasses import dataclass
import os

from agents.mcp import MCPServerStdio


@dataclass
class MCPServers:
    """Container for all MCP server clients used by the runtime."""
    mssql_server: MCPServerStdio
    chart_server: MCPServerStdio
    pdf_reader_server: MCPServerStdio
    word_reader_server: MCPServerStdio
    excel_server: MCPServerStdio


def build_servers(timeout_seconds: int = 60) -> MCPServers:
    """Create all MCP servers with a shared client timeout."""
    sql_params = {
        "command": "mssql-mcp-server",
        "env": {"MSSQL_CONNECTION_STRING": os.getenv("MSSQL_CONNECTION_STRING")},
    }
    chart_params = {"command": "npx", "args": ["-y", "@antv/mcp-server-chart"]}
    pdf_reader_params = {"command": "npx", "args": ["-y", "@sylphx/pdf-reader-mcp"]}
    word_reader_params = {"command": "uvx", "args": ["--from", "office-word-mcp-server", "word_mcp_server"]}
    excel_params = {"command": "uvx", "args": ["excel-mcp-server", "stdio"]}

    return MCPServers(
        mssql_server=MCPServerStdio(params=sql_params, client_session_timeout_seconds=timeout_seconds),
        chart_server=MCPServerStdio(params=chart_params, client_session_timeout_seconds=timeout_seconds),
        pdf_reader_server=MCPServerStdio(params=pdf_reader_params, client_session_timeout_seconds=timeout_seconds),
        word_reader_server=MCPServerStdio(params=word_reader_params, client_session_timeout_seconds=timeout_seconds),
        excel_server=MCPServerStdio(params=excel_params, client_session_timeout_seconds=timeout_seconds),
    )
