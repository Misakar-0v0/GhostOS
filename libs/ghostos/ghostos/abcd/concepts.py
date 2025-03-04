from __future__ import annotations
from typing import (
    Type, Generic, Protocol, ClassVar, TypeVar, Callable,
    Tuple, Optional, Iterable, List, Union, Dict, Any
)
from typing_extensions import Self

from abc import ABC, abstractmethod
from ghostos_common.identifier import Identical
from ghostos_common.entity import EntityType, EntityClass
from ghostos.prompter import PromptObjectModel, BasePOM
from ghostos.core.runtime import (
    TaskState,
)
from ghostos.core.runtime.events import Event, EventBus
from ghostos.core.runtime.tasks import GoTaskStruct, TaskBrief, GoTasks
from ghostos.core.runtime.threads import GoThreadInfo
from ghostos_moss import PyContext
from ghostos.core.llms import PromptPipe, Prompt, LLMFunc
from ghostos.core.messages import MessageKind, Message, Stream, FunctionCaller, Payload, Receiver, Role, Pipe as MsgPipe
from ghostos.contracts.logger import LoggerItf
from ghostos_container import Container, Provider
from ghostos_common.identifier import get_identifier
from pydantic import BaseModel

"""
# Core Concepts of GhostOS framework.

The word `Ghost` is picked from `Ghost In the Shell` movie.
The Ghost can perform as both conversational object or an async function.
Ghost is the abstract of atomic state machine unit in the GhostOS.

for example, llm-based `Agent` is a state machine, an implementation of Ghost in GhostOS.

Why Agent is a state machine?
1. Agent receives an event at a time, not parallel, or face brain split.
2. Agent keep it state in the system prompt and messages, by nature language.
3. Agent take actions that matching expectation.
So Agent is an AI-State-Machine, defined from prompt, not code; executed by Model, not Interpreter.

About the Ghost Abstract:
1. it is a class.
2. the ghost class can construct ghost instance.
3. any ghost instance can run as a conversational task
4. a conversational task runs in turns, receiving event and replying messages.
5. the conversational task is stateful, accept one event at a time.
6. the conversational task reach the end when it is canceled, done or failed
7. all the ghost has a Goal model to describe its current achievement.
8. The Ghost Class shall be simple and clear to the AI models, when they are creating ghosts themselves.

and the Most valuable features about ghost are:
1. ghosts shall be fractal, can be called by other ghosts.
2. ghost shall be defined by code, which can be generated by meta-agents.
"""

__all__ = (
    "Ghost", "GhostDriver", "GhostOS", "Matrix", "Conversation", "Background",
    "Operator", "Action",
    "Session", "Messenger", "StateValue", "Scope", "EntityType",
    "Mindflow", "Subtasks",
    "Context",
    "Thought",
    "SessionPyContext",
)


class Ghost(Identical, EntityClass, ABC):
    """
    the class defines the model of a kind of ghosts.
    four parts included:
    1. configuration of the Ghost, which is Ghost.__init__. we can predefine many ghost instance for special scenes.
    2. context is always passed by the Caller of a ghost instance. each ghost class has it defined context model.
    3. goal is the static output (other than conversation messages) of a ghost instance.
    4. driver is
    """

    ArtifactType: ClassVar[Optional[Type]] = None
    """ the model of the ghost's artifact, is completing during runtime"""

    ContextType: ClassVar[Optional[Type[ContextType]]] = None
    """ the model of the ghost's context, is completing during runtime'"""

    DriverType: ClassVar[Optional[Type[GhostDriver]]] = None
    """ separate ghost's methods to the driver class, make sure the ghost is simple and clear to other ghost"""


G = TypeVar("G", bound=Ghost)


class GhostDriver(Generic[G], ABC):
    """
    Ghost class is supposed to be a data class without complex methods definitions.
    so it seems much clear when prompt to the LLM or user-level developer.
    when LLM is creating a ghost class or instance, we expect it only see the code we want it to see,
    without knowing the details codes of it, for safety / fewer tokens / more focus or other reasons.

    so the methods of the ghost class defined in this class.
    only core developers should know details about it.
    """

    def __init__(self, ghost: G) -> None:
        self.ghost = ghost

    def make_task_id(self, parent_scope: Scope) -> str:
        """
        generate unique instance id (task id) of the ghost instance.
        """
        from ghostos_common.helpers import md5
        id_ = get_identifier(self.ghost)
        if id_.id:
            # if ghost instance has id, it is unique in process.
            scope_ids = f"{parent_scope.process_id}-{id_.id}"
        else:
            # if ghost do not have id, it is unique to parent by name
            scope_ids = f"{parent_scope.process_id}-{parent_scope.task_id}-{id_.name}"
        # the task id point to a unique entity
        return md5(scope_ids)

    @abstractmethod
    def get_artifact(self, session: Session) -> Optional[G.ArtifactType]:
        """
        generate the ghost goal from session_state
        may be the Goal Model is a SessionStateValue that bind to it.

        The AI behind a ghost is not supposed to operate the session object,
        but work on the goal through functions or Moss Injections.
        """
        pass

    @abstractmethod
    def get_system_instruction(self, session: Session) -> str:
        """
        get system instruction of the ghost.
        usually used in client side.
        """
        pass

    @abstractmethod
    def actions(self, session: Session) -> List[Action]:
        """
        return actions that react to the streaming output of llm
        """
        pass

    @abstractmethod
    def providers(self) -> Iterable[Provider]:
        """
        ghost return conversation level container providers.
        the provider that is not singleton will bind to session also.
        """
        pass

    @abstractmethod
    def parse_event(
            self,
            session: Session,
            event: Event,
    ) -> Union[Event, None]:
        """
        intercept the ghost event
        :returns: if None, the event will be ignored
        """
        pass

    @abstractmethod
    def on_creating(self, session: Session) -> None:
        """
        when the ghost task is created first time.
        this method can initialize the thread, pycontext etc.
        """
        pass

    @abstractmethod
    def on_event(self, session: Session, event: Event) -> Union[Operator, None]:
        """
        all the state machine is only handling session event with the predefined operators.
        """
        pass

    @abstractmethod
    def truncate(self, session: Session) -> GoThreadInfo:
        """
        truncate the history messages in the thread
        """
        pass

    def output_pipes(self) -> List[MsgPipe]:
        """
        session will use this pipes to moderate or filter outputting messages
        rewrite it to define the output pipes.
        :return: ghost level output pipes
        """
        return []

    def is_safe_mode(self) -> bool:
        """
        session safe mode is: (conversation level safe mode || ghost level safe mode)
        rewrite this method can define ghost level safe mode.
        At the safe mode, ghost action caller will not be executed,
        and the last turn will be ignored unless next event is ActionCall.
        """
        return False


class Context(BasePOM, ABC):
    """
    context pom that generate prompt to provide information
    the modeling defines strong-typed configuration to generate prompt.

    context is a payload, so it can be set to the message if needed.
    """
    pass


"""
Thought 的目标是实现一个可以分形嵌套的思维范式, 在单次思考过程中运行. 
这种工程化的实现, 是为了限制模型的思考逻辑, 在思考过程中丰富上下文, 通过 in-context learning 达到最好的推理效果. 
"""

T = TypeVar("T")


class Thought(Generic[T], ABC):
    """
    Unit to build LLM workflow fractally. e.g.:
    1. single thought: a single node of thought
    2. chain of thoughts: a pipeline of thoughts
    3. tree-like thought: a router before thoughts
    4. mode switch thought: change self thought to different sub modes.
    5. reasoning thought: reasoning before action.
    6. memory thought: preparing memory before action.
    """

    @abstractmethod
    def think(self, session: Session, prompt: Prompt) -> Tuple[Prompt, Optional[T]]:
        pass


class Operator(ABC):
    """
    Operator to operating the GhostOS through the Session encapsulation.

    The Operator is just like the primitives of any coding language.
    for example, GhostOS have some operators work like python's `return`, `yield`, `await` .

    I'm not capable to develop a real OS or a new coding language for AI,
    GhostOS is built above python with the additional complexities.

    Operators should be predefined, offer to user-level developer, or AI-models.
    """

    @abstractmethod
    def run(self, session: Session) -> Union[Operator, None]:
        """
        :return: None means stop the loop, otherwise keep going.

        operator returns an operator is a way to encapsulate repetitive codes.
        """
        pass

    @abstractmethod
    def destroy(self):
        """
        Python gc is not trust-worthy
        Especially A keep B, B keep C, C keep A, father and child keep each other.
        I prefer to del the object attributes in the end of the object lifecycle.
        """
        pass


class Action(PromptPipe, ABC):
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def as_function(self) -> Optional[LLMFunc]:
        pass

    @abstractmethod
    def update_prompt(self, prompt: Prompt) -> Prompt:
        pass

    @abstractmethod
    def run(self, session: Session, caller: FunctionCaller) -> Union[Operator, None]:
        pass


class GhostOSModes(Protocol):
    """
    system level global modes
    """
    is_debug: bool
    is_safemode: bool


class GhostOS(Protocol):

    @abstractmethod
    def container(self) -> Container:
        """
        root container for GhostOS
        """
        pass

    @abstractmethod
    def create_matrix(
            self,
            name: str,
            *,
            shell_id: str = "",
            providers: Optional[List[Provider]] = None,
            process_id: Optional[str] = None,
    ) -> Matrix:
        pass


class Background(ABC):

    @abstractmethod
    def on_error(self, error: Exception) -> bool:
        pass

    @abstractmethod
    def on_event(self, event: Event, messages: List[Message]) -> None:
        pass

    @abstractmethod
    def alive(self) -> bool:
        pass

    @abstractmethod
    def halt(self) -> int:
        pass


class Matrix(ABC):

    @abstractmethod
    def container(self) -> Container:
        """
        root container for GhostOS
        """
        pass

    @abstractmethod
    def send_event(self, event: Event) -> None:
        """
        send an event into the loop.
        the event always has a task_id, so the task shall be created first.
        """
        pass

    @abstractmethod
    def sync(
            self,
            ghost: G,
            context: Optional[G.ContextType] = None,
            username: str = "",
            user_role: str = Role.USER.value,
            task_id: str = None,
            force: bool = False,
    ) -> Conversation[G]:
        """
        create a top-level conversation with a ghost.
        top-level means task depth is 0.
        So it never locked until the conversation is created.
        if force is True, the conversation will seize the task locker anyway.
        """
        pass

    def get_or_create_task(
            self,
            ghost: Ghost,
            context: Optional[Ghost.ContextType] = None,
            *,
            task_id: str = None,
            always_create: bool = True,
            save: bool = False,
    ) -> GoTaskStruct:
        pass

    @abstractmethod
    def tasks(self) -> GoTasks:
        pass

    @abstractmethod
    def eventbus(self) -> EventBus:
        pass

    @abstractmethod
    def sync_task(
            self,
            task: Union[str, GoTaskStruct],
            *,
            username: str = "",
            user_role: str = "",
            force: bool = False,
    ) -> Conversation:
        pass

    @abstractmethod
    def call(
            self,
            ghost: G,
            context: Optional[G.ContextType] = None,
            instructions: Optional[Iterable[Message]] = None,
            timeout: float = 0.0,
            stream: Optional[Stream] = None,
    ) -> Tuple[Union[G.ArtifactType, None], TaskState]:
        """
        run a ghost task until it stopped,
        """
        pass

    @abstractmethod
    def run_background_event(self, background: Optional[Background] = None) -> Union[Event, None]:
        """
        run the event loop for the ghosts in the Shell.
        1. pop task notification.
        2. try to converse the task
        3. if failed, pop another task notification.
        4. if success, pop task event and handle it until no event found.
        5. send a task notification after handling, make sure someone check the task events are empty.
        only the tasks that depth > 0 have notifications.
        background run itself is blocking method, run it in a separate thread for parallel execution.
        :return: the handled event
        """
        pass

    @abstractmethod
    def background_run(self, worker: int = 4, background: Optional[Background] = None) -> None:
        pass

    @abstractmethod
    def submit(self, caller: Callable, *args, **kwargs):
        pass

    @abstractmethod
    def close(self):
        pass

    @abstractmethod
    def closed(self) -> bool:
        pass


class Conversation(Protocol[G]):
    """
    interface for operate on synchronized (task is locked) ghost
    """
    task_id: str

    scope: Scope

    logger: LoggerItf

    @abstractmethod
    def container(self) -> Container:
        """
        root container for GhostOS
        """
        pass

    @abstractmethod
    def get_task(self) -> GoTaskStruct:
        pass

    @abstractmethod
    def get_state_values(self) -> Dict[str, EntityType]:
        pass

    @abstractmethod
    def get_thread(self, truncated: bool = False) -> GoThreadInfo:
        pass

    @abstractmethod
    def update_thread(self, thread: GoThreadInfo) -> None:
        pass

    @abstractmethod
    def get_ghost(self) -> G:
        pass

    def get_ghost_driver(self) -> GhostDriver[G]:
        from ghostos.abcd.utils import get_ghost_driver
        ghost = self.get_ghost()
        return get_ghost_driver(ghost)

    @abstractmethod
    def get_context(self) -> G.ContextType:
        pass

    @abstractmethod
    def get_system_instruction(self) -> str:
        """
        the first message of llm request messages is usually system instruction or developer instruction.
        this method is able to return it to client side.
        """
        pass

    @abstractmethod
    def get_functions(self) -> List[LLMFunc]:
        pass

    @abstractmethod
    def get_artifact(self) -> Tuple[Union[G.ArtifactType, None], TaskState]:
        pass

    @abstractmethod
    def refresh(self) -> bool:
        pass

    @abstractmethod
    def talk(
            self,
            query: str,
            context: Optional[G.ContextType] = None,
            *,
            user_name: str = "",
            timeout: float = 0.0,
            request_timeout: float = 0.0,
    ) -> Tuple[Event, Receiver]:
        pass

    @abstractmethod
    def update_context(self, context: Context) -> None:
        """
        update the current context pom of the task
        :param context: context pom
        """
        pass

    @abstractmethod
    def respond(
            self,
            inputs: Iterable[MessageKind],
            context: Optional[G.ContextType] = None,
            *,
            streaming: bool = True,
            timeout: float = 0.0,
            request_timeout: float = 0.0,
    ) -> Tuple[Event, Receiver]:
        """
        create response immediately by inputs. the inputs will change to event.
        """
        pass

    @abstractmethod
    def respond_event(
            self,
            event: Event,
            *,
            timeout: float = 0.0,
            request_timeout: float = 0.0,
            streaming: bool = True,
    ) -> Receiver:
        """
        create response to the event immediately
        """
        pass

    @abstractmethod
    def pop_event(self) -> Optional[Event]:
        """
        pop event of the current task
        """
        pass

    @abstractmethod
    def send_event(self, event: Event) -> None:
        pass

    @abstractmethod
    def fail(self, error: Exception) -> bool:
        """
        exception occur
        :return: catch the exception or not
        """
        pass

    @abstractmethod
    def close(self):
        """
        close the conversation
        """
        pass

    @abstractmethod
    def available(self) -> bool:
        """
        beside closed, conversation may be executing, that means it is not available.
        """
        pass

    @abstractmethod
    def is_closed(self) -> bool:
        """
        closed
        """
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.is_closed():
            return
        if exc_val is not None:
            return self.fail(exc_val)
        else:
            self.close()
            return None


class Messenger(Stream, ABC):
    """
    Messenger is a bridge of message streams
    Messenger finish when the flush method is called.
    Each messenger can nest sub messengers, when sub messenger is finished,
    the parent messenger is not finished until the flush is called.

    why this is an abstract base class?
    there may be more abilities during streaming are needed,
    this project can only provide a basic one.
    """

    @abstractmethod
    def flush(self) -> Tuple[List[Message], List[FunctionCaller]]:
        """
        flush the buffed messages, finish the streaming of this messenger.
        the message buffer shall join all the chunks to message item.
        after the messenger is flushed, it can not send any new message.
        """
        pass


class StateValue(ABC):
    """
    session state value
    """

    @abstractmethod
    def get(self, session: Session) -> Optional[Self]:
        pass

    @abstractmethod
    def bind(self, session: Session) -> None:
        pass

    def get_or_bind(self, session: Session) -> Self:
        value = self.get(session)
        if value is None:
            value = self
            self.bind(session)
        return value


class SessionPyContext(PyContext, StateValue):
    """
    bind pycontext to session.state
    """

    def get(self, session: Session) -> Optional[Self]:
        data = session.state.get(SessionPyContext.__name__, None)
        if data is not None:
            if isinstance(data, Dict):
                return SessionPyContext(**data)
            elif isinstance(data, SessionPyContext):
                return data
        return None

    def bind(self, session: Session) -> None:
        session.state[SessionPyContext.__name__] = self


class Scope(BaseModel):
    """
    scope of the session.
    """
    shell_id: str
    process_id: str
    task_id: str
    parent_task_id: Optional[str] = None


class Session(Generic[G], ABC):
    """
    Session 管理了一个有状态的会话. 所谓 "有状态的会话", 通常指的是:
    shell + ghost + 多轮对话/多轮思考  运行中的状态.

    Session 则提供了 Ghost 的 Task 运行时状态统一管理的 API.
    通常每个运行中的 Task 都会创建一个独立的 Session.
    Session 在运行周期里不会立刻调用底层 IO 存储消息, 而是要等一个周期正常结束.
    这是为了减少运行时错误对状态机造成的副作用.
    """
    instance_count: ClassVar[int] = 0

    ghost: G
    """ghost instance"""

    ghost_driver: GhostDriver[G]
    """ghost driver instance"""

    task: GoTaskStruct
    """current task object, or session scheduling state object."""

    scope: Scope
    """the running scope of the session"""

    state: Dict[str, EntityType]
    """session state that keep session state values"""

    container: Container
    """Session level container"""

    thread: GoThreadInfo
    """thread info of the task"""

    logger: LoggerItf

    @abstractmethod
    def alive(self) -> bool:
        """
        Session 对自身任务进行状态检查.
        如果这个任务被取消或终止, 则返回 false.
        基本判断逻辑:
        1. 消息上游流没有终止.
        2. task 持有了锁.
        3. 设置的超时时间没有过.
        """
        pass

    @abstractmethod
    def allow_streaming(self) -> bool:
        """
        :return: if allow stream responding
        """
        pass

    @abstractmethod
    def get_truncated_thread(self) -> GoThreadInfo:
        """
        根据 Ghost 的逻辑对对话历史消息做处理, 返回处理后的历史消息.
        这个处理逻辑可能是截断.
        :return: 处理后的 thread.
        """
        pass

    @abstractmethod
    def to_messages(self, values: Iterable[Union[MessageKind, Any]]) -> List[Message]:
        """
        工具函数, 用来将各种类型的数据转化为 Message 方便发送.
        :param values:
        :return:str => Text Message; message => message; message class => message. other => VariableMessage.
        """
        pass

    @abstractmethod
    def parse_event(self, event: Event) -> Tuple[Optional[Event], Optional[Operator]]:
        """
        对输入事件进行预处理, 可以用来拦截, 拒答等.
        parse input event without handle it.
        :param event:
        :return: Tuple[parsed_event, [intercept operator?] ]
        """
        pass

    @abstractmethod
    def is_safe_mode(self) -> bool:
        """
        if is safe mode, the output with function callers will not be executed.
        """
        pass

    @abstractmethod
    def system_log(self, log: str) -> None:
        """
        log system info, save to thread as a system (developer) message
        :param log: log info
        """
        pass

    @abstractmethod
    def get_context(self) -> Optional[PromptObjectModel]:
        """
        current context for the ghost
        """
        pass

    @abstractmethod
    def get_artifact(self) -> G.ArtifactType:
        """
        :return: the current state of the ghost goal
        """
        pass

    @abstractmethod
    def get_system_instructions(self) -> str:
        pass

    @abstractmethod
    def refresh(self, throw: bool = False) -> bool:
        """
        refresh the session, update overdue time and task lock.
        """
        pass

    @abstractmethod
    def save(self):
        """
        save status.
        """
        pass

    @abstractmethod
    def mindflow(self) -> Mindflow:
        """
        basic library to operates the current task
        """
        pass

    @abstractmethod
    def subtasks(self) -> Subtasks:
        """
        系统默认的多任务管理.
        """
        pass

    @abstractmethod
    def messenger(
            self, *,
            name: str = "",
            stage: str = "",
            payloads: Optional[List[Payload]] = None,
    ) -> "Messenger":
        """
        Task 当前运行状态下, 向上游发送消息的 Messenger.
        每次会实例化一个 Messenger, 理论上不允许并行发送消息. 但也可能做一个技术方案去支持它.
        Messenger 未来要支持双工协议, 如果涉及多流语音还是很复杂的.
        :param stage: set the stage of the messages.
        :param name: if empty, use the ghost name
        :param payloads: add payloads to all the message complete items.
        """
        pass

    @abstractmethod
    def respond(
            self,
            messages: Iterable[MessageKind],
            stage: str = "",
            save: bool = True,
    ) -> Tuple[List[Message], List[FunctionCaller]]:
        """
        sending messages to client side.
        :param messages: the items to send. streaming or complete message.
        :param stage: set the stage of the all the messages.
        :param save: save the messages to session.thread. If false, shall handle the messages manually
        :return: join the chunks, return parsed (complete messages, function callers)
        """
        pass

    @abstractmethod
    def respond_buffer(
            self,
            messages: Iterable[MessageKind],
            stage: str = "",
    ) -> None:
        """
        buffer the responding messages, send them when the session exit
        :param messages:
        :param stage:
        """
        pass

    @abstractmethod
    def save_threads(
            self,
            *threads: GoThreadInfo,
    ) -> None:
        pass

    def create_tasks(self, *tasks: GoTaskStruct) -> None:
        pass

    @abstractmethod
    def call(self, ghost: G, ctx: G.ContextType) -> G.ArtifactType:
        """
        创建一个子任务, 阻塞并等待它完成.
        todo: 未测试
        :param ghost:
        :param ctx:
        :return: the Goal of the task. if the final state is not finish, throw an exception.
        """
        pass

    # --- 更底层的 API. --- #

    @abstractmethod
    def fire_events(self, *events: "Event") -> None:
        """
        发送多个事件. 这个环节需要给 event 标记 callback.
        在 session.done() 时才会真正执行.
        """
        pass

    @abstractmethod
    def get_task_briefs(self, *task_ids: str) -> Dict[str, TaskBrief]:
        """
        获取多个任务的简介.
        :param task_ids: 可以指定要获取的 task id
        """
        pass

    def handle_event(self, event: Event) -> Optional[Operator]:
        # always let ghost driver decide event handling logic first.
        driver = self.ghost_driver

        # driver parse the event first.
        event = driver.parse_event(self, event)
        if event is None:
            return None

        # session parse event,
        event, op = self.parse_event(event)
        if op is not None:
            self.logger.info("session event is intercepted and op %s is returned", op)
            return op
        if event is None:
            # if event is intercepted, stop the run.
            return None

        # update self thread to truncated thread.
        self.thread = self.get_truncated_thread()

        # driver handle event.
        op = driver.on_event(self, event)
        # only session and driver can change event.
        return op

    def handle_callers(self, callers: Iterable[FunctionCaller], force: bool = False) -> Optional[Operator]:
        """
        handle caller.
        """
        callers = list(callers)
        if not callers:
            return None
        if self.is_safe_mode() and not force:
            # 开启 safe mode
            self.thread.set_approval(False, callers)
            return None

        actions = {a.name(): a for a in self.ghost_driver.actions(self)}
        for caller in callers:
            if caller.name not in actions:
                self.logger.error("session receive caller %s, miss action", caller.name)
                self.respond([caller.new_output(f"Error: function `{caller.name}` not found")])
                continue
            action = actions[caller.name]
            self.logger.error("session handle caller %s with action %s ", caller.name, type(action))
            op = action.run(self, caller)
            if op is not None:
                return op
        return None

    @abstractmethod
    def __enter__(self):
        pass

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class Mindflow(PromptObjectModel, ABC):
    """
    control ghost mind with basic operators.
    """

    MessageKind = Union[str, Message, Any]
    """message kind shall be string or serializable object"""

    # --- 基本操作 --- #
    @abstractmethod
    def finish(self, status: str = "", *replies: MessageKind) -> Operator:
        """
        finish self task
        :param status: describe status of the task
        :param replies: replies to parent task or user
        """
        pass

    @abstractmethod
    def fail(self, reason: str = "", *replies: MessageKind) -> Operator:
        """
        self task failed.
        :param reason: describe status of the task
        :param replies: replies to parent task or user
        """
        pass

    @abstractmethod
    def wait(self, status: str = "", *replies: MessageKind) -> Operator:
        """
        wait for the parent task or user to provide more information or further instruction.
        :param status: describe current status
        :param replies: question, inform or
        """
        pass

    @abstractmethod
    def think(self, *messages: MessageKind, instruction: str = "", sync: bool = False) -> Operator:
        """
        start next round thinking on messages
        :param messages: observe target
        :param instruction: instruction when receive the observation.
        :param sync: if True, observe immediately, otherwise check other event first
        :return:
        """
        pass

    @abstractmethod
    def observe(self, **kwargs) -> Operator:
        """
        observe values
        :param kwargs:
        :return:
        """
        pass

    @abstractmethod
    def error(self, *messages: MessageKind) -> Operator:
        pass


class Subtasks(PromptObjectModel, ABC):
    """
    library that can handle async subtasks by other ghost instance.
    """
    MessageKind = Union[str, Message, Any]
    """message kind shall be string or serializable object"""

    @abstractmethod
    def cancel(self, name: str, reason: str = "") -> None:
        """
        cancel an exists subtask
        :param name: name of the task
        :param reason: the reason to cancel it
        :return:
        """
        pass

    @abstractmethod
    def send(
            self,
            name: str,
            *messages: MessageKind,
            ctx: Optional[Ghost.ContextType] = None,
    ) -> None:
        """
        send message to an existing subtask
        :param name: name of the subtask
        :param messages: the messages to the subtask
        :param ctx: if given, update the ghost context of the task
        :return:
        """
        pass

    @abstractmethod
    def create(
            self,
            ghost: Ghost,
            instruction: str = "",
            ctx: Optional[Ghost.ContextType] = None,
            task_name: Optional[str] = None,
            task_description: Optional[str] = None,
    ) -> None:
        """
        create subtask from a ghost instance
        :param ghost: the ghost instance that handle the task
        :param instruction: instruction to the ghost
        :param ctx: the context that the ghost instance needed
        :param task_name: if not given, use the ghost's name as the task name
        :param task_description: if not given, use the ghost's description as the task description
        """
        pass
