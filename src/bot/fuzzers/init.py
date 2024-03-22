
"""Fuzzing engine initialization."""

import importlib

from bot import fuzzing
from bot.fuzzers.templates.python.PythonTemplateEngine import PythonFuzzerEngine as engine


def run(include_private=True, include_lowercase=False):
    """Initialise builtin fuzzing engines."""
    if include_private:
        engines = fuzzing.ENGINES
    else:
        engines = fuzzing.PUBLIC_ENGINES

    for engine_name in engines:
        try:
            module = f'bot.fuzzers.{engine_name}.engine'
            mod = importlib.import_module(module)
            engine.register(engine_name, mod.Engine)
            if include_lowercase and engine_name.lower() != engine_name:
                engine.register(engine_name.lower(), mod.Engine)
        except Exception as e:
              print(e)


