from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StuffList(Base):
    __tablename__ = "stufflist"
    __table_args__ = {"comment": "A list of stuff the user wants to keep track of"}

    id: Mapped[int] = mapped_column(primary_key=True, comment="Surrogate primary key")
    name: Mapped[str] = mapped_column(index=True, comment="Display name given by the user")
