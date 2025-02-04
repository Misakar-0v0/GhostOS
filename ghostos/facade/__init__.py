from ghostos.facade._llms import (
    get_llm_configs,  # get the ghostos llms config
    set_default_model,  # set the default model to llms, only work during runtime
)

from ghostos.facade._contracts import (
    get_logger,  # get ghostos logger
)

from ghostos.facade._model_funcs_facade import (
    text_completion,  #
    file_reader,
)

# ghostos.facade is a composer of all the application level functions.
# easy to use, but more likely are the tutorials of how to use ghostos
# todo: a facade agent is required
