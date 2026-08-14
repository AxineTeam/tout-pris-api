from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StuffList(Base):
    __tablename__ = "stufflist"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(index=True)
