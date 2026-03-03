from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Ensure model metadata registration for migrations/table creation.
from domain.auth import models as auth_models  # noqa: F401,E402  # register auth metadata on import
from domain.content import models as content_models  # noqa: F401,E402  # register content metadata on import
from domain.explain import models as explain_models  # noqa: F401,E402  # register explain metadata on import
from domain.learning import models as learning_models  # noqa: F401,E402  # register learning metadata on import
