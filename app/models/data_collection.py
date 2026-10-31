from dataclasses import dataclass
from uuid import UUID


@dataclass(slots=True, init=False)
class DataCollection:
    """A data collection the app started: the session in which it groups the runs of one
    volunteer. The name is not unique, since a volunteer can come back for another collection."""

    id: UUID
    volunteer: str

    def __init__(self, payload: dict) -> None:
        collection_id = payload.get("collection_id")
        if not isinstance(collection_id, str):
            raise ValueError("Missing or non-string field: collection_id")
        try:
            self.id = UUID(collection_id.strip())
        except ValueError:
            raise ValueError(f"Field collection_id is not a UUID: {collection_id!r}") from None

        volunteer = payload.get("volunteer")
        if not isinstance(volunteer, str) or not volunteer.strip():
            raise ValueError("Missing, non-string or empty field: volunteer")
        self.volunteer = volunteer.strip()
