from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import threading

from src.client import QuinceClient
from src.config import settings
from src.logging_setup import configure_logging, get_logger

if sys.platform == "win32":
    try:
        from asyncio.proactor_events import BaseProactorEventLoop
        _orig_close_self_pipe = BaseProactorEventLoop._close_self_pipe

        def _safe_close_self_pipe(self):
            try:
                if getattr(self, "_ssock", None) is not None:
                    _orig_close_self_pipe(self)
            except Exception:
                pass

        BaseProactorEventLoop._close_self_pipe = _safe_close_self_pipe
    except Exception:
        pass

logger = get_logger("run")


async def run_cli_input_loop(client: QuinceClient) -> None:
    """
    Background CLI loop that accepts text prompt input directly from the terminal,
    while Quince's global push-to-talk voice input (Ctrl+Q) remains active.
    """
    await asyncio.sleep(1.0)
    print("\n[Quince CLI] Push-to-Talk active (hold Ctrl+Q to speak) | Or type prompt below:\n")

    while not client._shutdown.is_set():
        try:
            prompt = await asyncio.to_thread(input, "[Quince] > ")
            prompt = prompt.strip()
            if not prompt:
                continue
            if prompt.lower() in ("exit", "quit", ":q"):
                logger.info("Exiting Quince CLI.")
                client.request_shutdown()
                break
            await client.send_text_prompt(prompt)
        except (EOFError, KeyboardInterrupt):
            client.request_shutdown()
            break
        except Exception as exc:
            logger.debug("CLI input error: %s", exc)


async def run_http_server(host: str, port: int, client: QuinceClient) -> None:
    """Lightweight HTTP status server for api.quince.jam (127.0.0.5:10000)."""
    async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            line = await reader.readline()
            while True:
                h = await reader.readline()
                if not h or h in (b"\r\n", b"\n"):
                    break
            is_conn = getattr(getattr(client, "connection", None), "is_connected", False)
            data = {
                "status": "healthy",
                "service": "quince",
                "name": "Quince Voice Assistant Server",
                "host": host,
                "port": port,
                "basket_connected": is_conn,
            }
            body = json.dumps(data).encode("utf-8")
            resp = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/json\r\n"
                b"Access-Control-Allow-Origin: *\r\n"
                b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n"
                b"Connection: close\r\n\r\n" + body
            )
            writer.write(resp)
            await writer.drain()
        except Exception:
            pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    try:
        server = await asyncio.start_server(handle_client, host, port)
        logger.info(f"Quince HTTP Status API listening on http://{host}:{port}/")
        async with server:
            while not client._shutdown.is_set():
                await asyncio.sleep(0.5)
    except Exception as exc:
        logger.warning(f"Could not bind Quince HTTP API on {host}:{port}: {exc}")


async def run_with_http(client: QuinceClient, has_cli: bool = False) -> None:
    host = os.getenv("QUINCE_SERVER_HOST", "127.0.0.5")
    port = int(os.getenv("QUINCE_SERVER_PORT", "10000"))
    http_task = asyncio.create_task(run_http_server(host, port, client))
    cli_task = asyncio.create_task(run_cli_input_loop(client)) if has_cli else None
    try:
        await client.run()
    finally:
        if cli_task:
            cli_task.cancel()
            try:
                await cli_task
            except asyncio.CancelledError:
                pass
        http_task.cancel()
        try:
            await http_task
        except asyncio.CancelledError:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Quince: Voice & Text Companion for Basket")
    parser.add_argument("--gui", action="store_true", help="Launch Quince in GUI mode")
    parser.add_argument("--no-input", action="store_true", help="Run voice-only without interactive CLI text prompt")
    args, _ = parser.parse_known_args()

    configure_logging(settings.log_level)

    client = QuinceClient(settings)

    if args.gui:
        from src.ui.gui import QuinceGUI

        gui = QuinceGUI(client)

        client_thread = threading.Thread(
            target=lambda: asyncio.run(run_with_http(client, has_cli=False)),
            daemon=True,
            name="QuinceClientThread",
        )
        client_thread.start()

        try:
            gui.run()
        except KeyboardInterrupt:
            logger.info("Interrupted by user; shutting down.")
            client.request_shutdown()
        except Exception:
            logger.exception("Quince GUI exited due to an unhandled error.")
            client.request_shutdown()
            sys.exit(1)
        finally:
            client.request_shutdown()
            client_thread.join(timeout=2.0)
        return

    # Default: CLI Mode
    try:
        if args.no_input:
            asyncio.run(run_with_http(client, has_cli=False))
        else:
            asyncio.run(run_with_http(client, has_cli=True))
    except KeyboardInterrupt:
        logger.info("Interrupted by user; shutting down.")
    except Exception:
        logger.exception("Quince exited due to an unhandled error.")
        sys.exit(1)


if __name__ == "__main__":
    main()
