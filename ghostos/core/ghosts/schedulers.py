from typing import Dict, Any, TypedDict, Required, Optional
from abc import ABC, abstractmethod
from ghostos.core.ghosts.operators import Operator
from ghostos.core.ghosts.thoughts import Thought
from ghostos.core.ghosts.assistants import Assistant
from ghostos.core.messages.message import MessageKind

__all__ = [
    'MultiTask', 'Taskflow', 'NewTask', 'Replier',
]


class Taskflow(ABC):
    """
    这个 library 可以直接管理当前任务的状态调度.
    通过method 返回的 Operator 会操作系统变更当前任务的状态.
    """

    @abstractmethod
    def awaits(self, reply: str = "", log: str = "") -> Operator:
        """
        当前任务挂起, 等待下一轮输入.
        :param reply: 可以发送回复, 或者主动提出问题或要求. 并不是必要的.
        :param log: 如果不为空, 会更新当前任务的日志. 只需要记录对任务进行有意义而且非常简介的讯息.
        """
        pass

    @abstractmethod
    def observe(self, objects: Dict[str, Any], reason: str = "", instruction: str = "") -> Operator:
        """
        系统会打印这些变量的值, 作为一条新的输入消息让你观察, 开启你的下一轮思考.
        是实现 Chain of thought 的基本方法.
        :param objects: the observing objects by name to value
        :param reason: if given, will record the observing reason to task logs.
        :param instruction: give the instruction when observe the result, in case of forgetting.
        """
        pass

    @abstractmethod
    def think(self, instruction: str = "") -> Operator:
        """
        think another round
        :param instruction: optional instruction for next round thinking
        """
        pass

    @abstractmethod
    def finish(self, log: str, response: str) -> Operator:
        """
        结束当前的任务, 返回任务结果.
        如果当前任务是持续的, 还要等待更多用户输入, 请使用 awaits.
        :param log: 简单记录当前任务完成的理由.
        :param response: 发送一条或多条消息作为任务的结论发送给用户.
        """
        pass

    @abstractmethod
    def fail(self, reason: str, reply: str) -> Operator:
        """
        标记当前任务失败
        :param reason: 记录当前任务失败的原因.
        :param reply: 发送给用户或者父任务的消息. 如果为空的话, 把 log 作为讯息传递.
        """
        pass


class NewTask(TypedDict):
    """
    useful to create a child task
    """
    task_name: Required[str]
    """task specific name that you can identify this task in future"""

    task_desc: str
    """task description that why you create this task"""

    thought: Required[Thought]
    """Thought instance that dispatched to run this task"""

    instruction: str
    """the instruction to the task thought. could be empty"""


class MultiTask(ABC):
    """
    You are equipped with this MultiTasks Library that can execute thought in an asynchronous task.
    A thought is a mind-machine usually driven by LLM, can resolve certain type of task in multi-turns chain of thought.
    During the process, the thought may send messages to you, finish/fail the task or await for more information.
    You shall use MultiTasks library to help you resolve your task, interactively and asynchronous.
    """

    @abstractmethod
    def wait_on_tasks(self, *new_tasks: NewTask) -> Operator:
        """
        使用 Thought 创建多个任务, 同时等待这些任务返回结果. 当结果返回时会触发下一轮思考.
        :param new_tasks: the information to create a child task
        """
        pass

    @abstractmethod
    def run_tasks(self, *new_tasks: NewTask) -> None:
        """
        使用 thoughts 动态创建一个或者多个 task 异步运行. 不影响你当前状态.
        """
        pass

    @abstractmethod
    def send_task(self, task_name: str, *messages: MessageKind) -> None:
        """
        主动向一个指定的 task 进行通讯.
        :param task_name: task 的名称
        :param messages: 消息会发送给目标 task
        """
        pass

    @abstractmethod
    def cancel_task(self, task_name: str, reason: str) -> None:
        """
        取消一个已经存在的 task.
        :param task_name: 目标 task 的名称.
        :param reason: 取消的理由.
        """
        pass


# simple and sync version of taskflow
class Replier(ABC):
    """
    reply to the input message
    """

    @abstractmethod
    def reply(self, content: str) -> Operator:
        """
        reply to the input message
        :param content: content of the reply
        :return: wait for further input
        """
        pass

    @abstractmethod
    def ask_clarification(self, question: str) -> Operator:
        """
        the input query is not clear enough, ask clarification.
        :param question: the question will send back
        :return: wait for clarification input
        """
        pass

    @abstractmethod
    def fail(self, reply: str) -> Operator:
        """
        fail to handle request, and reply
        :param reply: content of the reply
        :return: wait for further input
        """
        pass

    @abstractmethod
    def think(
            self,
            observations: Optional[Dict[str, Any]] = None,
            instruction: Optional[str] = None,
    ) -> Operator:
        """
        think another round with printed values or observations
        :param observations: print the observations as message
        :param instruction: tell self what to do next
        :return: think another round
        """
        pass


class MultiAssistant(ABC):

    @abstractmethod
    def ask_assistant(self, assistant: Assistant, query: str) -> None:
        """
        ask an assistant to do something or reply some information.
        :param assistant: the assistant instance
        :param query: query to the assistant.
        """
        pass
