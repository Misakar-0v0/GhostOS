from __future__ import annotations

import os
from abc import ABC, abstractmethod

from typing import List, Tuple, Iterable, Dict, Optional, Any, Union
from openai.types.chat.completion_create_params import Function, FunctionCall
from openai import NotGiven, NOT_GIVEN
from openai.types.chat.chat_completion_function_call_option_param import ChatCompletionFunctionCallOptionParam

from pydantic import BaseModel, Field
from ghostiss import helpers
from ghostiss.core.messages import Message, Stream, FunctionalToken

"""
Dev logs: 

创建一个大模型的 API 设计. 基于 openai 的 API.
主要目的是让大模型的 API 调用本身可选择.  

"""

OPENAI_DRIVER_NAME = "ghostiss.llms.openai_driver"


# ---- config ---- #


class ModelConf(BaseModel):
    """
    模型的配置.
    """
    model: str = Field(description="llm model name that service provided")
    service: str = Field(description="llm service name")
    temperature: float = Field(default=0.7, description="temperature")
    n: int = Field(default=1, description="number of iterations")
    max_tokens: int = Field(default=512, description="max tokens")
    timeout: float = Field(default=20, description="timeout")
    request_timeout: float = Field(default=40, description="request timeout")
    kwargs: Dict[str, Any] = Field(default_factory=dict, description="kwargs")


class ServiceConf(BaseModel):
    """
    服务的配置.
    """
    name: str = Field(description="Service name")
    driver: str = Field(default=OPENAI_DRIVER_NAME, description="driver name")
    base_url: str = Field(description="llm service provider")
    token: str = Field(default="", description="token")
    proxy: Optional[str] = Field(default=None, description="proxy")

    def load(self) -> None:
        self.token = self._load_env(self.token)
        if self.proxy is not None:
            self.proxy = self._load_env(self.proxy)

    @staticmethod
    def _load_env(value: str) -> str:
        if value.startswith("$"):
            value_key = value[1:]
            value = os.environ.get(value_key, "")
        return value


class LLMsConfig(BaseModel):
    """
    所有的配置项.
    一种可选的方式. 
    """
    services: List[ServiceConf] = Field(default_factory=list)
    models: Dict[str, ModelConf] = Field(default_factory=dict)


# ---- tool and function ---- #

class LLMFunc(BaseModel):
    name: str = Field(description="function name")
    description: str = Field(default="", description="function description")
    parameters: Optional[Dict] = Field(default=None, description="function parameters")


# ---- api objects ---- #

class Chat(BaseModel):
    id: str = Field(default_factory=helpers.uuid, description="trace id")
    messages: List[Message] = Field(default_factory=list)
    functions: List[LLMFunc] = Field(default_factory=list)
    functional_tokens: List[FunctionalToken] = Field(default_factory=list)
    function_call: Optional[str] = Field(default=None, description="function call")

    # stop: Optional[List[str]] = Field(default=None)

    def get_openai_functions(self) -> Union[List[Function], NotGiven]:
        if not self.functions:
            return NOT_GIVEN
        functions = []
        for func in self.functions:
            openai_func = Function(**func.model_dump())
            functions.append(openai_func)
        return functions

    def get_openai_function_call(self) -> Union[FunctionCall, NotGiven]:
        if not self.functions:
            return NOT_GIVEN
        if self.function_call is None:
            return "auto"
        return ChatCompletionFunctionCallOptionParam(name=self.function_call)


# todo: 未来再做这些意义不大的.
# class Cast(BaseModel):
#     model: str = Field(description="llm model")
#     prompt_tokens: int = Field(description="prompt tokens")
#     total_tokens: int = Field(description="total tokens")
#     duration: float = Field(description="time duration")


class Embedding(BaseModel):
    content: str = Field(description="origin content")
    service: str = Field(description="llm service")
    model: str = Field(description="llm model")
    embedding: List[float] = Field(description="embedding")


class Embeddings(BaseModel):
    result: List[Embedding] = Field(default_factory=list)
    # todo: 未来再管这些.
    # cast: Cast = Field(description="cast")


# --- test case --- #


# --- interfaces --- #

class LLMApi(ABC):

    @abstractmethod
    def get_service(self) -> ServiceConf:
        """
        """
        pass

    @abstractmethod
    def get_model(self) -> ModelConf:
        """
        get new api with the given api_conf and return new LLMAPI
        """
        pass

    @abstractmethod
    def text_completion(self, prompt: str) -> str:
        """
        deprecated text completion
        """
        pass

    @abstractmethod
    def get_embeddings(self, text: List[str]) -> Embeddings:
        pass

    @abstractmethod
    def chat_completion(self, chat: Chat) -> Message:
        pass

    @abstractmethod
    def chat_completion_chunks(self, chat: Chat) -> Iterable[Message]:
        """
        todo: 暂时先这么定义了.
        """
        pass

    def deliver_chat_completion(self, chat: Chat, up_stream: Stream) -> None:
        """
        逐个发送消息的包.
        """
        items = self.chat_completion_chunks(chat)
        for item in items:
            up_stream.deliver(item)


class LLMDriver(ABC):

    @abstractmethod
    def driver_name(self) -> str:
        pass

    @abstractmethod
    def new(self, service: ServiceConf, model: ModelConf) -> LLMApi:
        pass


class LLMs(ABC):

    @abstractmethod
    def register_driver(self, driver: LLMDriver) -> None:
        pass

    @abstractmethod
    def register_service(self, service: ServiceConf) -> None:
        pass

    @abstractmethod
    def register_model(self, name: str, model_conf: ModelConf) -> None:
        pass

    @abstractmethod
    def services(self) -> List[ServiceConf]:
        pass

    @abstractmethod
    def get_service(self, name: str) -> Optional[ServiceConf]:
        pass

    @abstractmethod
    def each_api_conf(self) -> Iterable[Tuple[ServiceConf, ModelConf]]:
        pass

    @abstractmethod
    def new_api(self, service_conf: ServiceConf, api_conf: ModelConf) -> LLMApi:
        pass

    @abstractmethod
    def get_api(self, api_name: str) -> Optional[LLMApi]:
        pass

    def force_get_api(self, api_name: str) -> LLMApi:
        """
        sugar
        """
        api = self.get_api(api_name)
        if api is None:
            raise NotImplemented("LLM API {} not implemented.".format(api_name))
        return api