import os
from dotenv import load_dotenv
from mcp import StdioServerParameters

# načítaj .env
load_dotenv()

MODEL_NAME = "gpt-4o"

# MCP server – cesta k server.py
BASE_DIR = os.path.dirname(__file__)
SERVER_SCRIPT_PATH = os.path.join(BASE_DIR, "mcp", "server.py")

print("Spúšťam MCP server cez STDIO:", SERVER_SCRIPT_PATH)

SERVER_PARAMS = StdioServerParameters(
    command="python",
    args=[SERVER_SCRIPT_PATH],
    env=None,
)
