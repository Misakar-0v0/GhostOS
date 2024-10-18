from abc import ABC, abstractmethod
from typing import MutableMapping, Optional, ClassVar, Any, TypeVar, Type, List
from typing_extensions import Self
from pydantic import BaseModel
from ghostos.helpers import generate_import_path

__all__ = [
    'SessionStateValue', 'ModelSingleton',
    'SingletonContracts',
    'Singleton',
    # functions
    'expect',
]


class SessionStateValue(ABC):
    """
    Value that bind to streamlit.session_state
    """

    @classmethod
    @abstractmethod
    def get(cls, session_state: MutableMapping) -> Optional[Self]:
        """
        load self value from session_state
        :param session_state: the streamlit session state
        :return: None if not bound yet
        """
        pass

    @classmethod
    def get_or_bind(cls, session_state: MutableMapping) -> Self:
        value = cls.get(session_state)
        if value is None:
            default_value = cls.default()
            default_value.bind(session_state)
            return default_value
        if not isinstance(value, cls):
            raise ValueError(f"type {cls} can not find self in streamlit.session_state, {value} found")
        return value

    @classmethod
    @abstractmethod
    def default(cls) -> Self:
        """
        default self value
        """
        pass

    @abstractmethod
    def bind(self, session_state: MutableMapping) -> None:
        """
        bind self to session_state
        :param session_state: streamlit.session_state
        """
        pass


class ModelSingleton(BaseModel, SessionStateValue, ABC):
    """
    use pydantic.BaseModel to define state value
    """

    @classmethod
    def get(cls, session_state: MutableMapping) -> Optional[Self]:
        """
        load self value from session_state
        :param session_state: the streamlit session state
        :return: None if not bound yet
        """
        key = cls.session_key()
        if key not in session_state:
            return None
        return session_state.get(key, None)

    @classmethod
    def session_key(cls) -> str:
        return generate_import_path(cls)

    @classmethod
    def default(cls) -> Self:
        # SingletonModel shall have default value for each field.
        return cls()

    def bind(self, session_state: MutableMapping) -> None:
        key = self.session_key()
        session_state[key] = self


T = TypeVar('T')


class Singleton:
    """
    session state singleton, key is the class type
    """

    def __init__(self, value: object):
        self.value = value
        self.key = self.gen_key(type(value))

    def bind(self, session_state: MutableMapping, force: bool = False) -> None:
        """
        :param session_state: streamlit session state
        :param force: if False, only bind when target is not exists.
        """
        if force or self.key not in session_state:
            session_state[self.key] = self.value

    @classmethod
    def get(cls, t: Type[T], session_state: MutableMapping) -> T:
        key = cls.gen_key(t)
        if key not in session_state:
            raise KeyError(f'key {key} not found in session state')
        value = session_state[key]
        return value

    @classmethod
    def gen_key(cls, t: Type) -> str:
        return generate_import_path(t)

    @classmethod
    def bound(cls, t: Type, session_state: MutableMapping) -> bool:
        key = cls.gen_key(t)
        return key in session_state


class SingletonContracts:
    def __init__(self, types: List[Type]):
        self.types = types

    def validate(self, session_state: MutableMapping) -> List[Type]:
        unbound = []
        for typ in self.types:
            if not Singleton.bound(typ, session_state):
                unbound.append(typ)
        return unbound


def expect(session_state: MutableMapping, key: str, value: Any) -> bool:
    if key not in session_state:
        return False
    return value == session_state[key]
