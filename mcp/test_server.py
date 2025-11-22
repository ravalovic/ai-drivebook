import asyncio
import os
import sys
from datetime import datetime
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    # Cesta k  serveru 
    server_script_path = os.path.join(os.path.dirname(__file__), "server.py")

    print("Spúšťam MCP server cez STDIO:", server_script_path)

    # Konfigurácia STDIO servera  dokumentácia MCP
    server_params = StdioServerParameters(
        command="python",          # alebo "python3" podľa prostredia
        args=[server_script_path],
        env=None,                  # zdedené prostredie je OK
    )

    #  STDIO transport
    async with stdio_client(server_params) as (read, write):
        print("STDIO spojenie nadviazané, vytváram ClientSession...")

        async with ClientSession(read, write) as session:
            # Inicializácia MCP session 
            await session.initialize()

            print("Session inicializovaná, listujem nástroje na serveri...")
            tools_response = await session.list_tools()
            print("Dostupné nástroje:")
            for t in tools_response.tools:
                print(f" - {t.name}: {t.description}")

            print("\nVolám tool 'driving_time_between_cities'...")

            result = await session.call_tool(
                "driving_time_between_cities",
                {
                    "city1": "Vrbové",
                    "city2": "Bratislava",
                },
            )

            print("\n===== VÝSLEDOK TOOLU =====")
            print(result)
            print("===========================")


if __name__ == "__main__":
    asyncio.run(main())
