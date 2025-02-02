from typing import List, Tuple
from typing_extensions import Self
from pydantic import BaseModel, Field
from typing import Dict, Optional
from ghostos.abcd import Session
from ghostos.container import Container, Provider, INSTANCE
from ghostos.libraries.notebook.abcd import Notebook
from ghostos.contracts.storage import FileStorage
from ghostos.contracts.workspace import Workspace
from ghostos.helpers import yaml_pretty_dump
import yaml


class NotebookConfig(BaseModel):
    default_memo_topics: List[str] = Field(
        default_factory=lambda: ["todo_list", "instructions"],
        description="default memo topics",
    )
    memo_content_limit: int = Field(
        default=10,
        description="the maximum number of contents of a topic",
    )
    default_notes_context_depth: int = Field(
        default=2,
        description="",
    )


class Note(BaseModel):
    path: str = Field(description="the path of the notebook node in filename pattern, like 'path/path/name'")
    description: str = Field(description="the description of the notebook node")
    content: str = Field(default="", description="the content of notebook node")


class NotebookData(BaseModel):
    """
    the data of the notebook
    """
    _memo_title = str
    _memo_content = str
    _memo_priority = float

    memo: Dict[str, Dict[_memo_title, Tuple[_memo_content, _memo_priority]]] = Field(
        default_factory=dict,
        description="the memo data, ",
    )
    notes: Dict[str, Note] = Field(
        default_factory=dict,
        description="the nodes of notes, from path to note",
    )


class NoteTree:
    """
    generated by deepseek-reasoner
    """

    def __init__(self, note: Note):
        self.note = note
        path = note.path
        parts = path.split('/') if path else []
        self.depth = len(parts)
        if self.depth == 0:
            self.prefix = ""
            self.name = ""
        else:
            self.prefix = '/'.join(parts[:-1])
            self.name = parts[-1]
        self.children: Dict[str, NoteTree] = {}

    def is_branch(self) -> bool:
        return len(self.children) > 0

    def add_note(self, note: Note) -> None:
        current_path = self.note.path
        note_path = note.path

        if current_path:
            if not (note_path.startswith(f"{current_path}/") or note_path == current_path):
                return
            remaining = note_path[len(current_path) + 1:]
        else:
            remaining = note_path

        components = [c for c in remaining.split('/') if c] if remaining else []
        current = self
        for comp in components:
            if comp not in current.children:
                new_path = f"{current.note.path}/{comp}" if current.note.path else comp
                current.children[comp] = NoteTree(Note(path=new_path, description="", content=""))
            current = current.children[comp]
        current.note = note

    def get_node(self, path: str) -> Optional[Self]:
        components = [c for c in path.split('/') if c]
        current = self
        for comp in components:
            if comp not in current.children:
                return None
            current = current.children[comp]
        return current

    def list_notes(self, depth: int = 2) -> str:
        def dfs(node, current_depth):
            result = []
            for name, child in node.children.items():
                prefix = '  ' * current_depth
                symbol = '+' if child.is_branch() else '-'
                result.append(f"{prefix}{symbol} {name}")
                if current_depth < depth and child.is_branch():
                    result.extend(dfs(child, current_depth + 1))
            return result

        if len(self.children) == 0:
            return "empty"

        return '\n'.join(dfs(self, 0))


class SimpleNotebookImpl(Notebook):
    """
    very simple notebook implementation
    """

    def __init__(
            self,
            notebook_id: str,
            storage: FileStorage,
            config: NotebookConfig,
            data: Optional[NotebookData] = None,
    ):
        self._notebook_id = notebook_id
        self._cache_file = f"test_notebook_{notebook_id}.yml"
        self._storage = storage
        self._config = config
        self._data = self._get_data_from_storage(data)
        self._note_tree = NoteTree(note=Note(path='', description=''))
        self._rerank_memo()
        self._rebuild_note_tree()

    def _get_data_from_storage(self, default: Optional[NotebookData] = None) -> NotebookData:
        filename = self._cache_file
        if self._storage.exists(filename):
            content = self._storage.get(filename)
            data = yaml.safe_load(content)
            return NotebookData(**data)
        elif default is not None:
            return default
        else:
            data = NotebookData()
            for topic in self._config.default_memo_topics:
                data.memo[topic] = {}
            return data

    def _rerank_memo(self):
        for topic in self._data.memo:
            # 按照优先级排序，优先级高的在前
            contents = self._data.memo[topic]
            keys = list(contents.keys())
            keys.sort(key=lambda x: x[1], reverse=True)
            # 删除超过限制的项
            if len(keys) > self._config.memo_content_limit:
                keys = keys[:self._config.memo_content_limit]
            new_contents = {}
            for key in keys:
                new_contents[key] = contents[key]
            self._data.memo[topic] = new_contents

    def _rebuild_note_tree(self):
        self._note_tree = NoteTree(note=Note(path='', description=''))
        for note in self._data.notes.values():
            self._note_tree.add_note(note)

    def add_memo(self, topic: str, title: str, content: str = "", priority: float = 0.0) -> None:
        if topic not in self._data.memo:
            self._data.memo[topic] = {}
        self._data.memo[topic][title] = (content, priority)
        self._rerank_memo()
        self._save()

    def save_note(self, path: str, desc: str, content: str) -> None:
        self._data.notes[path] = Note(path=path, description=desc, content=content)
        self._rebuild_note_tree()
        self._save()

    def read_note(self, path: str) -> str:
        if path in self._data.notes:
            return self._data.notes[path].content
        return f"note `{path}` not found"

    def move_note(self, path: str, new_path: str) -> None:
        if path not in self._data.notes:
            return
        note = self._data.notes.pop(path)
        note.path = new_path
        self._data.notes[new_path] = note
        self._rebuild_note_tree()
        self._save()

    def remove_note(self, path: str) -> bool:
        if path not in self._data.notes:
            return False
        self._data.notes.pop(path)
        self._rebuild_note_tree()
        self._save()
        return True

    def list_notes_tree(self, prefix: str = '', depth: int = 3) -> str:
        found = self._note_tree.get_node(prefix)
        return found.list_notes(depth)

    def _save(self) -> None:
        content = yaml_pretty_dump(self._data.model_dump(exclude_defaults=True))
        filename = self._cache_file
        self._storage.put(filename, content.encode())

    def dump_context(self) -> str:
        memo_context = self._dump_memo_context()
        depth = self._config.default_notes_context_depth
        note_tree_context = self._note_tree.list_notes()
        return f"""
Here are the context of your notebook. 
You can use the notebook to record something you want to keep in long term memory.
And you can read or search the topic that you are needed.

Your memo are: 
```yaml
{memo_context}
```

Your notes tree in depth {depth}:

```markdown
{note_tree_context}
```
"""

    def _dump_memo_context(self) -> str:
        memo_context = ""
        if len(self._data.memo) == 0:
            return "empty"
        count = 0
        for topic in self._data.memo:
            contents = [f"  - [{count}] {content}" for content, priority in self._data.memo[topic].values()]
            contents_text = '\n'.join(contents)
            memo_context += f"""
+ topic `{topic}`:
{contents_text.rstrip() or "  - empty"}  
"""
            count += 1
        return memo_context

    def self_prompt(self, container: Container) -> str:
        return self.dump_context()

    def get_title(self) -> str:
        return "Notebook Context"


class SimpleNotebookProvider(Provider[Notebook]):
    """
    just for test.
    """

    def singleton(self) -> bool:
        return False

    def factory(self, con: Container) -> Optional[INSTANCE]:
        session = con.force_fetch(Session)
        workspace = con.force_fetch(Workspace)
        task_id = session.task.task_id
        storage = workspace.runtime_cache()
        return SimpleNotebookImpl(
            notebook_id=task_id,
            storage=storage,
            config=NotebookConfig(),
        )
