import asyncio
import json

from bot.main import (
    consult_rulebook,
    create_and_save_character,
    get_character_state,
    load_game,
    save_game,
    update_character,
    roll_dice,
)

FUNCTION_MAP = {
    "consult_rulebook": consult_rulebook,
    "create_and_save_character": create_and_save_character,
    "get_character_state": get_character_state,
    "load_game": load_game,
    "save_game": save_game,
    "update_character": update_character,
    "roll_dice": roll_dice,
}

HELLO_LINE = "#$#mcp version: 2.1 ready\n"


class MCPServerProtocol(asyncio.Protocol):
    """Minimal MCP protocol server."""

    def __init__(self):
        self.transport = None
        self.buffer = ""

    def connection_made(self, transport: asyncio.Transport):
        self.transport = transport
        self.transport.write(HELLO_LINE.encode())

    def data_received(self, data: bytes):
        self.buffer += data.decode()
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            line = line.strip()
            if not line:
                continue
            if line.startswith("#$#"):
                try:
                    self.handle_mcp(line[3:])
                except Exception as exc:
                    self.send_error(str(exc))
            else:
                # ignore non MCP lines
                pass

    def handle_mcp(self, payload: str):
        """Handle a MCP command line."""
        if payload.startswith("call "):
            # format: call <function> <json-args>
            try:
                _cmd, func_name, json_args = payload.split(" ", 2)
            except ValueError:
                raise ValueError("Invalid call syntax")
            func = FUNCTION_MAP.get(func_name)
            if not func:
                raise ValueError(f"Unknown function {func_name}")
            args = json.loads(json_args)
            result = func(**args)
            self.send_mcp("result", {"function": func_name, "result": result})
        elif payload.startswith("hello"):
            # client handshake response
            pass
        else:
            raise ValueError("Unknown command")

    def send_mcp(self, command: str, data: dict):
        line = f"#$#{command} {json.dumps(data)}\n"
        self.transport.write(line.encode())

    def send_error(self, message: str):
        self.send_mcp("error", {"message": message})


async def main(host: str = "0.0.0.0", port: int = 5050):
    loop = asyncio.get_running_loop()
    server = await loop.create_server(MCPServerProtocol, host, port)
    print(f"MCP server running on {host}:{port}")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
