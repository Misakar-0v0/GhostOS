import streamlit as st
import time
import streamlit_react_jsonschema as srj
from ghostos.prototypes.streamlitapp.pages.router import GhostChatRoute
from ghostos.prototypes.streamlitapp.utils.session import Singleton
from ghostos.prototypes.streamlitapp.widgets.messages import (
    render_messages,
    render_message_item,
)
from ghostos.prototypes.streamlitapp.widgets.renderer import render_object
from ghostos.core.runtime import GoThreadInfo
from ghostos.core.messages import Receiver, Role
from ghostos.abcd import Shell, Conversation, Context
from ghostos.identifier import get_identifier
from ghostos.helpers import gettext as _
from ghostos.helpers import generate_import_path, yaml_pretty_dump
from pydantic import BaseModel, Field
import inspect


class ButtonInfo(BaseModel):
    label: str = Field(description="The label of the subpage.")
    help: str = Field(default="todo", description="The help text of the subpage.")
    icon: str = Field(default=":material/thumb_up:", description="The icon of the subpage.")


chat = ButtonInfo(
    label=_("Chat"),
)
ghost_settings = ButtonInfo(
    label=_("Ghost Settings"),
)
context_settings = ButtonInfo(
    label=_("Context Settings"),
)
task_info = ButtonInfo(
    label=_("Task Info"),
)
thread_info = ButtonInfo(
    label=_("Thread Info"),
)

subpages = [chat, context_settings, ghost_settings, task_info, thread_info]

chat_input_type = ButtonInfo(
    label=_("Chat Input"),
)

input_types = [chat_input_type]


def main():
    route = GhostChatRoute.get_or_bind(st.session_state)
    # create shell
    ghost = route.get_ghost()
    context = route.get_context()
    conversation = Singleton.get(Conversation, st.session_state, force=False)
    if not conversation:
        shell = Singleton.get(Shell, st.session_state)
        # create conversation
        conversation = shell.sync(ghost, context)
        Singleton(conversation, Conversation).bind(st.session_state)

    # run the pages
    run_chat_page(route, conversation)

    # rebind route.
    route.bind(st.session_state)


def run_chat_page(route: GhostChatRoute, conversation: Conversation):
    with st.sidebar:
        for subpage in subpages:
            button = st.button(
                label=subpage.label,
                help=subpage.help,
                icon=subpage.icon,
                use_container_width=True,
            )
            if button:
                route.page_type = subpage.label
        if route.page_type == chat.label:
            st.divider()
            if st.button("Image Input", use_container_width=True):
                route.input_type = "image"
            if st.button("Textarea Input", use_container_width=True):
                route.input_type = "text"
            if st.button("File Input", use_container_width=True):
                route.input_type = "file"
            if st.button("Video Shortcut Input", use_container_width=True):
                route.input_type = "video"

    # header
    st.title("Ghost")
    ghost = route.get_ghost()
    id_ = get_identifier(ghost)
    import_path = generate_import_path(ghost.__class__)
    data = {
        _("name"): id_.name,
        _("desc"): id_.description,
        _("class"): import_path,
    }
    # description
    st.markdown(f"""
```yaml
{yaml_pretty_dump(data)}
```
""")

    # body
    if route.page_type == context_settings.label:
        render_context_settings(route, conversation)
    elif route.page_type == ghost_settings.label:
        render_ghost_settings(route)
    elif route.page_type == task_info.label:
        render_task_info_settings(route, conversation)
    elif route.page_type == thread_info.label:
        render_thread_info_settings(route, conversation)
    else:
        render_chat(route, conversation)


def render_chat(route: GhostChatRoute, conversation: Conversation):
    st.title(route.page_type)
    if route.input_type == "any":
        pass
    else:
        st.write("chat input")
        if chat_input := st.chat_input("Your message"):
            message = Role.USER.new(chat_input)
            route.inputs.append(message)
            route.bind(st.session_state)
    chatting()


@st.fragment
def chatting():
    conversation = Singleton.get(Conversation, st.session_state)
    thread = conversation.thread()
    render_thread_messages(thread)

    while True:
        route = GhostChatRoute.get(st.session_state)
        # has input
        if route is not None and route.inputs:
            inputs = route.inputs
            route.inputs = []
            route.bind(st.session_state)

            with st.chat_message("user"):
                st.write("todo")

            receiver = conversation.respond(inputs)
            render_receiver(receiver)
        elif event := conversation.pop_event():
            receiver = conversation.respond_event(event)
            render_receiver(receiver)
        else:
            time.sleep(0.5)


def render_receiver(receiver: Receiver):
    receiver.wait()
    st.write("todo")


def render_ghost_settings(route: GhostChatRoute):
    ghost = route.get_ghost()
    st.subheader(_(route.page_type))
    # render ghost info
    if isinstance(ghost, BaseModel):
        data, mod = srj.pydantic_instance_form(ghost)
        if st.button("Save"):
            st.write("todo saving ghosts")
    else:
        st.write(ghost)
    source = inspect.getsource(ghost.__class__)
    with st.expander("source code", expanded=False):
        st.code(source)


def render_context_settings(route: GhostChatRoute, conversation: Conversation):
    st.subheader(route.page_type)
    ctx = route.get_context()
    ghost = route.get_ghost()
    if ctx is None and ghost.ContextType is None:
        st.info("No specific Context for this Ghost")
        return
    if ctx is None:
        if ghost.ContextType is not None:
            data, submitted = srj.pydantic_form(ghost.ContextType)
            if submitted and isinstance(data, Context):
                conversation.update_context(data)
                ctx = data
    else:
        data, submitted = srj.pydantic_instance_form(ctx)
        if submitted and isinstance(data, Context):
            conversation.update_context(data)
            ctx = data

    # render prompt
    if ctx is not None:
        st.subheader(_("context prompt"))
        try:
            prompt = ctx.get_prompt(conversation.container())
            st.markdown(prompt)
        except Exception as e:
            st.error(e)
    if ghost.ArtifactType:
        st.subheader(_("Artifact"))
        artifact = conversation.get_artifact()
        render_object(artifact)


def render_task_info_settings(route: GhostChatRoute, conversation: Conversation):
    from ghostos.core.runtime.tasks import TaskBrief
    st.subheader(route.page_type)
    task = conversation.task()
    brief = TaskBrief.from_task(task)
    srj.pydantic_instance_form(brief, readonly=True)

    with st.expander(_("Detail"), expanded=False):
        st.write(task.model_dump(exclude_defaults=True))


def render_thread_info_settings(route: GhostChatRoute, conversation: Conversation):
    st.subheader(route.page_type)

    thread = conversation.thread()

    with st.expander(_("Detail"), expanded=False):
        st.write(thread_info.model_dump(exclude_defaults=True))
    st.subheader(_("Thread Messages"))
    render_thread_messages(thread)


def render_thread_messages(thread: GoThreadInfo):
    turns = thread.turns()
    count = 0
    for turn in turns:
        count += 1
        messages = list(turn.messages())
        if messages:
            st.write(f"turn {count}")
            render_messages(messages)
