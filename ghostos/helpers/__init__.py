from typing import TYPE_CHECKING
from ghostos.helpers.dictionary import (dict_without_none, dict_without_zero)
from ghostos.helpers.string import camel_to_snake
from ghostos.helpers.yaml import yaml_pretty_dump, yaml_multiline_string_pipe
from ghostos.helpers.modules import (
    import_from_path,
    import_class_from_path,
    parse_import_module_and_spec,
    join_import_module_and_spec,
    get_module_spec,
    generate_module_spec,
    generate_import_path,
    Importer,
    is_method_belongs_to_class,
    get_calling_modulename,
    rewrite_module,
    rewrite_module_by_path,
)
from ghostos.helpers.io import BufferPrint
from ghostos.helpers.time import Timeleft
from ghostos.helpers.hashes import md5
from ghostos.helpers.trans import gettext, ngettext, get_current_locale, GHOSTOS_DOMAIN

from ghostos.helpers.coding import reflect_module_code
from ghostos.helpers.openai import get_openai_key

if TYPE_CHECKING:
    from typing import Callable


# --- private methods --- #
def __uuid() -> str:
    from uuid import uuid4
    return str(uuid4())


# --- facade --- #

uuid: "Callable[[], str]" = __uuid
""" patch this method to change global uuid generator"""
