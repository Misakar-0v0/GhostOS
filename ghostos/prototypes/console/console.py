from __future__ import annotations
from ghostos.core.ghostos import GhostOS
import time
import asyncio
from typing import Optional, List

from ghostos.core.messages import Message, Role
from ghostos.core.ghosts import Inputs
from ghostos.framework.streams import QueueStream
from ghostos.framework.messages import TaskPayload
from ghostos.helpers import uuid
from threading import Thread
from queue import Queue, Empty
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.shortcuts import PromptSession
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

__all__ = ['ConsolePrototype']


class ConsolePrototype:

    def __init__(
            self, *,
            ghostos: GhostOS,
            ghost_id: str,
            username: str,
            debug: bool = False,
            session_id: Optional[str] = None,
            process_id: Optional[str] = None,
            task_id: Optional[str] = None,
            background_num: int = 1,
    ):
        self._os = ghostos
        self._ghost_id = ghost_id
        self._username = username
        self._process_id = process_id
        self._task_id = task_id
        self._session_id = session_id if session_id else uuid()
        session = PromptSession("\n\n<<< ", )
        self._prompt_session = session
        self._console = Console()
        self._stopped = False
        self._queue = Queue()
        self._debug = debug
        self._threads: List[Thread] = []
        self._background_num = background_num

    def run(self):
        for i in range(self._background_num):
            background_run_task = Thread(target=self._start_background)
            background_run_task.start()
            self._threads.append(background_run_task)
        print_output_task = Thread(target=self._print_output)
        print_output_task.start()
        self._threads.append(print_output_task)
        asyncio.run(self._main())

    def _print_output(self):
        while not self._stopped:
            try:
                message = self._queue.get(block=True, timeout=1)
                if not isinstance(message, Message):
                    raise ValueError(f"Expected Message, got {message}")
                self._print_message(message)
            except Empty:
                continue

    def _start_background(self):
        while not self._stopped:
            stream = self._stream()
            handled = self._os.background_run(stream)
            if not handled:
                time.sleep(1)

    def _stream(self) -> QueueStream:
        return QueueStream(self._queue, streaming=False)

    async def _main(self):
        self._welcome()
        with patch_stdout(raw=True):
            await self._loop()
            self._console.print("Quitting event loop. Bye.")

    async def _loop(self):
        session = self._prompt_session
        bindings = self._bindings()
        while not self._stopped:
            try:
                text = await session.prompt_async(multiline=False, key_bindings=bindings)
                if self._intercept_text(text):
                    continue
                self._console.print(Markdown("\n----\n"))
                self._on_input(text)
            except (EOFError, KeyboardInterrupt):
                self._exit()
            except Exception:
                self._console.print_exception()
                self._exit()

    def _on_input(self, text: str):
        message = Role.USER.new(
            content=text,
            name=self._username,
        )
        inputs_ = Inputs(
            session_id=self._session_id,
            ghost_id=self._ghost_id,
            messages=[message],
            process_id=self._process_id,
            task_id=self._task_id,
        )
        stream = self._stream()
        self._os.on_inputs(inputs_, stream, is_async=True)

    def _intercept_text(self, text: str) -> bool:
        if text == "/exit":
            self._exit()
        return False

    @staticmethod
    def _bindings():
        bindings = KeyBindings()
        return bindings

    def _welcome(self) -> None:
        self._console.print(Markdown("""
----
# Console Demo

print "/exit" to quit
----
"""))

    def _exit(self):
        self._stopped = True
        _continue = True
        self._console.print("start exiting")
        while _continue:
            try:
                self._queue.get_nowait()
            except Empty:
                break
        self._console.print("stop queue")
        self._console.print("queue closed")
        for t in self._threads:
            t.join()
        self._console.print("threads joined")
        self._os.shutdown()
        self._console.print("ghostos shutdown")
        self._console.print("Exit, Bye!")
        exit(0)

    def _print_message(self, message: Message):
        if self._debug:
            self._console.print_json(
                message.model_dump_json(indent=2, exclude_defaults=True),
            )
        if message.is_empty():
            return
        payload = TaskPayload.read(message)
        title = ""
        if payload is not None:
            title = f"{payload.task_name}: {payload.thread_id}"
        content = message.get_content()
        markdown = self._markdown_output(content)
        self._console.print(Panel(markdown, title=title))

    @staticmethod
    def _markdown_output(text: str) -> Markdown:
        return Markdown(text)