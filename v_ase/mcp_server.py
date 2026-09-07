"""Official MCP SDK adapter for v_ase's vendor-neutral typed tool catalog."""
from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
import sys

from ._version import __version__
from .ai import ai_skill_path
from .ai_tools import FunctionTools, ToolError
from .ai_discovery import CORE_TOOL_NAMES

INSTRUCTIONS = """Control the same live document as the human. For figure work start
with vase_scene_snapshot: its default summary includes the actual render camera,
display mode, bond visibility, selections and readiness. Request filtered geometry
only to identify atoms/edges. Use vase_search_tools for a feature or exact name;
never dump a full tool catalog. Search returns short matches. Read vase_read_guide
only for the scientific workflow you need; schemas are supplied by the tools.
Use vase_style_scene for simple display toggles, or a minimal vase_apply_scene
patch for related visual/frame changes. Hiding bonds
means show_bonds=false, not clearing pair policies. Keep document/revision guards,
preserve unmentioned fields, and reuse a request_id only for an identical uncertain
retry. Physical edits and analysis use their dedicated discovered tools. Ordinary
mutation replies and structuredContent should be consumed once, without dumping
unchanged state. Publication rendering suppresses transient selection appearance
without changing the GUI selection; interactive mode preserves it. Inspect the
final image. Artifacts are resource links, never Base64 text. Review human events
and conflicts before further edits. Lengths are Angstrom, angles degrees, indices
zero-based; visual bonds and repulsive placement do not establish equilibrium."""
CORE_TOOLS = CORE_TOOL_NAMES


def create_mcp_server(client: FunctionTools, *, discovery="all"):
    """Create an SDK server; register a stable callable catalog by default.

    Schema disclosure belongs at the model host. Some clients do not rebuild
    callable bindings after list-change notifications during an active turn.
    Progressive server registration remains opt-in for verified clients.
    """
    try:
        from mcp.server import Server
        from mcp.server.lowlevel import NotificationOptions
        from mcp.server.subscriptions import InMemorySubscriptionBus, ListenHandler, ToolsListChanged
        from mcp_types.version import MODERN_PROTOCOL_VERSIONS
        from mcp import types
    except ImportError as exc:
        raise RuntimeError('Install MCP support with: python -m pip install "v_ase-gui[mcp]"') from exc
    if discovery not in {"all", "progressive"}:
        raise ValueError("discovery must be all or progressive")
    subscriptions = InMemorySubscriptionBus()
    enabled = set(client.catalog) if discovery == "all" else set(CORE_TOOLS.intersection(client.catalog))
    async def list_tools(ctx, params):
        definitions = client.definitions(sorted(enabled))
        return types.ListToolsResult(tools=[types.Tool.model_validate(d) for d in definitions])

    def response(value, *, error=False):
        structured = value if isinstance(value, dict) else {"result": value}
        content = [types.TextContent(type="text", text=json.dumps(structured, separators=(",", ":"), allow_nan=False))]
        artifact = structured.get("artifact")
        if artifact:
            content.append(types.ResourceLink(type="resource_link", uri=artifact["uri"], name=artifact["name"], mime_type=artifact["mimeType"], size=artifact["size"]))
        return types.CallToolResult(content=content, structured_content=structured, is_error=error)

    async def call_tool(ctx, params):
        try:
            if params.name in {"vase_search_tools", "vase_tool_schema"}:
                value = client.call(params.name, params.arguments or {})
                names = [item["name"] for item in value["tools"]]
                changed = set(names) - enabled
                enabled.update(names)
                if changed:
                    await subscriptions.publish(ToolsListChanged())
                    if ctx.protocol_version not in MODERN_PROTOCOL_VERSIONS:
                        await ctx.session.send_tool_list_changed()
                return response({**value, "loaded": names, "discovery": discovery})
            if params.name not in enabled:
                raise ToolError("Tool is not loaded. Use vase_search_tools first.", code="unknown_tool")
            value = await asyncio.to_thread(client.call, params.name, params.arguments)
            if params.name == "vase_inspect_image":
                metadata, data = client.read_artifact(value["artifact"]["uri"])
                return types.CallToolResult(
                    content=[types.ImageContent(type="image", data=base64.b64encode(data).decode("ascii"),
                                               mime_type=metadata["mimeType"])],
                    structured_content={"artifact": metadata}, is_error=False)
            return response(value)
        except ToolError as exc:
            return response(exc.as_dict(), error=True)
        except (OSError, ValueError) as exc:
            return response(ToolError(str(exc), code="adapter_error", outcome="unknown").as_dict(), error=True)

    skill_files = {"vase://skill": Path(ai_skill_path())}
    skill_files.update({f"vase://skill/references/{path.name}": path
                        for path in sorted(Path(ai_skill_path()).parent.joinpath("references").glob("*.md"))})

    async def list_resources(ctx, params):
        return types.ListResourcesResult(resources=[
            *[types.Resource(uri=uri, name=path.name, mime_type="text/markdown") for uri, path in skill_files.items()],
            types.Resource(uri="vase://connection", name="Shared GUI connection", mime_type="application/json"),
        ])

    async def read_resource(ctx, params):
        uri = str(params.uri)
        if uri in skill_files:
            return types.ReadResourceResult(contents=[types.TextResourceContents(uri=uri, mime_type="text/markdown", text=skill_files[uri].read_text())])
        if uri == "vase://connection":
            return types.ReadResourceResult(contents=[types.TextResourceContents(uri=uri, mime_type="application/json", text=json.dumps({"human_url": client.human_url, "scope": client.scope, "command_url": client.command_url, "artifact_directory": str(client.artifact_dir), "discovery": discovery}))])
        metadata, data = client.read_artifact(uri)
        return types.ReadResourceResult(contents=[types.BlobResourceContents(uri=uri, mime_type=metadata["mimeType"], blob=base64.b64encode(data).decode("ascii"))])

    class VAseServer(Server):
        def get_capabilities(self, notification_options=None, experimental_capabilities=None,
                             extensions=None, *, protocol_version=None):
            supplied = notification_options or NotificationOptions()
            options = NotificationOptions(
                prompts_changed=supplied.prompts_changed,
                resources_changed=supplied.resources_changed,
                tools_changed=supplied.tools_changed or discovery == "progressive")
            return super().get_capabilities(options, experimental_capabilities, extensions,
                                            protocol_version=protocol_version)

    return VAseServer("v_ase", version=__version__, instructions=INSTRUCTIONS,
                      on_list_tools=list_tools, on_call_tool=call_tool,
                      on_list_resources=list_resources, on_read_resource=read_resource,
                      on_subscriptions_listen=ListenHandler(subscriptions) if discovery == "progressive" else None)


def run_mcp_command(args):
    """Run stdio or loopback Streamable HTTP, connecting to or owning a GUI."""
    import contextlib
    from collections import deque
    import subprocess
    import threading
    import webbrowser

    process = None
    command_url = args.connect
    try:
        # Fail before opening a GUI if the optional SDK is missing.
        import mcp.server.stdio
        if not command_url:
            command = [sys.executable, "-m", "v_ase.cli", "gui", "--cli"]
            if args.file:
                command.append(args.file)
            if args.interactive:
                command.append("--interactive")
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=sys.stderr, text=True)
            handshake = json.loads(process.stdout.readline())
            command_url = handshake["command_url"]
            print(f"v_ase human GUI: {handshake['human_url']}", file=sys.stderr, flush=True)
            threading.Thread(target=lambda: deque(process.stdout, maxlen=0), daemon=True).start()
            if not args.no_browser:
                webbrowser.open(handshake["human_url"])
        with FunctionTools(command_url, artifact_dir=args.artifact_dir, timeout=args.timeout) as client:
            server = create_mcp_server(client, discovery=args.discovery)
            if args.transport == "stdio":
                async def serve():
                    async with mcp.server.stdio.stdio_server() as (read, write):
                        await server.run(read, write, server.create_initialization_options())
                asyncio.run(serve())
            else:
                import uvicorn
                app = server.streamable_http_app(host="127.0.0.1", json_response=True)
                uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    except ImportError as exc:
        raise SystemExit('v_ase mcp: install support with python -m pip install "v_ase-gui[mcp]"') from exc
    except (ValueError, OSError, KeyError) as exc:
        raise SystemExit(f"v_ase mcp: {exc}") from exc
    finally:
        if process is not None:
            process.terminate()
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=5)
            if process.poll() is None:
                process.kill()
                process.wait()
    return 0
