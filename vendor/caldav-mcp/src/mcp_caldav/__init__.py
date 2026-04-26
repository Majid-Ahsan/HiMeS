"""MCP CalDAV Server - Calendar integration for MCP."""

import asyncio
import logging
import os

import click
from dotenv import load_dotenv

__version__ = "0.1.0"

# Initialize logging
logging_level = logging.WARNING
if os.getenv("MCP_VERBOSE", "").lower() in ("true", "1", "yes"):
    logging_level = logging.DEBUG

logging.basicConfig(
    level=logging_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("mcp-caldav")


@click.command()
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="Increase verbosity (can be used multiple times)",
)
@click.option(
    "--env-file",
    type=click.Path(exists=True, dir_okay=False),
    help="Path to .env file",
)
@click.option(
    "--transport",
    type=click.Choice(["stdio", "sse"]),
    default="stdio",
    help="Transport type (stdio or sse)",
)
@click.option(
    "--port",
    default=8000,
    help="Port to listen on for SSE transport",
)
@click.option(
    "--caldav-url",
    help="CalDAV server URL (e.g., https://caldav.example.com/)",
)
@click.option("--caldav-username", help="CalDAV username")
@click.option("--caldav-password", help="CalDAV password or app password")
def main(
    verbose: bool,
    env_file: str | None,
    transport: str,
    port: int,
    caldav_url: str | None,
    caldav_username: str | None,
    caldav_password: str | None,
) -> None:
    """MCP CalDAV Server - Universal calendar functionality for MCP

    Works with any CalDAV-compatible calendar server.
    """
    # Configure logging based on verbosity
    logging_level = logging.WARNING
    if verbose == 1:
        logging_level = logging.INFO
    elif verbose >= 2:
        logging_level = logging.DEBUG

    logging.getLogger("mcp-caldav").setLevel(logging_level)

    # Load environment variables from file if specified
    if env_file:
        logger.debug(f"Loading environment from file: {env_file}")
        load_dotenv(env_file)
    else:
        logger.debug("Attempting to load environment from default .env file")
        load_dotenv()

    # Set environment variables from command line arguments if provided
    if caldav_url:
        os.environ["CALDAV_URL"] = caldav_url
    if caldav_username:
        os.environ["CALDAV_USERNAME"] = caldav_username
    if caldav_password:
        os.environ["CALDAV_PASSWORD"] = caldav_password

    from . import server

    # Run the server with specified transport
    asyncio.run(server.run_server(transport=transport, port=port))


__all__ = ["__version__", "main", "server"]

if __name__ == "__main__":
    main()
