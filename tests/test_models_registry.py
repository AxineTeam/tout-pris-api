import importlib
import pkgutil

import app.models
from app.database import Base


def test_every_model_module_is_reexported_by_the_package():
    registered = set(Base.metadata.tables)

    for module in pkgutil.iter_modules(app.models.__path__):
        importlib.import_module(f"app.models.{module.name}")

    assert set(Base.metadata.tables) == registered
