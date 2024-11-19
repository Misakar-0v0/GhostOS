from typing import Optional, List
from ghostos.prototypes.streamlitapp.utils.route import Route, Router, Link
from ghostos.core.messages import Message
from ghostos.core.aifunc import ExecFrame
from ghostos.abcd import Ghost, Context
from ghostos.entity import EntityMeta, from_entity_meta, get_entity
from enum import Enum
from pydantic import Field


class PagePath(str, Enum):
    HOMEPAGE = "ghostos.prototypes.streamlitapp.pages.homepage"
    AIFUNCS = "ghostos.prototypes.streamlitapp.pages.aifuncs"
    GHOSTOS = "ghostos.prototypes.streamlitapp.pages.ghosts"

    def suffix(self, attr_name: str):
        return self.value + attr_name


# --- ghosts --- #

class GhostChatRoute(Route):
    link = Link(
        name="ghost_chat",
        import_path=PagePath.GHOSTOS.suffix(".chat:main"),
        streamlit_icon=":material/smart_toy:",
        button_help="todo",
        antd_icon="robot",
    )
    ghost_meta: Optional[EntityMeta] = Field(default=None, description="ghost meta")
    context_meta: Optional[EntityMeta] = Field(default=None, description="context meta")
    input_type: str = Field(default="Chat", description="input type")
    page_type: str = Field(default="Chat", description="page type")

    inputs: List[Message] = Field(default_factory=list, description="inputs")

    __ghost__ = None

    def get_ghost(self) -> Ghost:
        if self.__ghost__ is None:
            self.__ghost__ = get_entity(self.ghost_meta, Ghost)
        return self.__ghost__

    __context__ = None

    def get_context(self) -> Optional[Context]:
        if self.context_meta is None:
            return None
        if self.__context__ is None:
            self.__context__ = get_entity(self.context_meta, Context)
        return self.__context__


# --- home --- #

class Home(Route):
    link = Link(
        name="GhostOS",
        import_path=PagePath.HOMEPAGE.suffix(":home"),
        streamlit_icon=":material/home:",
        button_help="help",
        antd_icon="house-fill",
    )


class Navigator(Route):
    link = Link(
        name="Navigator",
        import_path=PagePath.HOMEPAGE.suffix(":navigator"),
        streamlit_icon=":material/home:",
        antd_icon="box-fill",
    )


class GhostOSHost(Route):
    link = Link(
        name="GhostOS Host",
        import_path=PagePath.HOMEPAGE.suffix(":ghostos_host"),
        streamlit_icon=":material/smart_toy:",
    )


class Helloworld(Route):
    """
    test only
    """
    link = Link(
        name="Hello World",
        import_path=PagePath.HOMEPAGE.suffix(":helloworld"),
        streamlit_icon=":material/home:",
    )


# --- ai functions --- #

class AIFuncListRoute(Route):
    link = Link(
        name="AIFunc List",
        import_path=PagePath.AIFUNCS.suffix(".index:main"),
        streamlit_icon=":material/functions:",
    )
    search: str = Field(
        default="",
        description="search ai functions with keyword",
    )


class AIFuncDetailRoute(Route):
    link = Link(
        name="AIFunc Detail",
        import_path=PagePath.AIFUNCS.suffix(".detail:main"),
        streamlit_icon=":material/functions:",
    )
    aifunc_id: str = Field(
        default="",
        description="AIFunc ID, which is import path of it",
    )
    frame: Optional[ExecFrame] = Field(
        default=None,
        description="current execution frame",
    )
    executed: bool = False
    received: List[Message] = Field(
        default_factory=list,
        description="list of execution messages",
    )
    timeout: float = 40
    exec_idle: float = 0.2

    def clear_execution(self):
        self.executed = False
        self.received = []
        self.frame = None


# --- routers --- #

def default_router() -> Router:
    return Router(
        [
            Home(),
            Helloworld(),
            Navigator(),
            GhostOSHost(),
            AIFuncListRoute(),
            AIFuncDetailRoute(),
            GhostChatRoute(),
        ],
        home=Home.label(),
        navigator_page_names=[
            GhostOSHost.label(),
            AIFuncListRoute.label(),
        ],
        default_menu={
            Home.label(): None,
        },
        default_sidebar_buttons=[
        ],
    )
