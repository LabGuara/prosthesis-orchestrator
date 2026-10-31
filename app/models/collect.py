from dataclasses import dataclass
from uuid import UUID


@dataclass(slots=True, init=False)
class Collect:
    """A collect the app started: the session in which it groups the runs of one
    volunteer. The name is not unique, since a volunteer can come back for another collect."""

    id: UUID
    volunteer: str

    def __init__(self, payload: dict) -> None:
        collect_id = payload.get("collect_id")
        if not isinstance(collect_id, str):
            raise ValueError("Missing or non-string field: collect_id")
        try:
            self.id = UUID(collect_id.strip())
        except ValueError:
            raise ValueError(f"Field collect_id is not a UUID: {collect_id!r}") from None

        volunteer = payload.get("volunteer")
        if not isinstance(volunteer, str) or not volunteer.strip():
            raise ValueError("Missing, non-string or empty field: volunteer")
        self.volunteer = volunteer.strip()
