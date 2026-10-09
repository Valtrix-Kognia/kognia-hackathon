UNKNOWN_SPEAKER_ID = "desconocido"
UNKNOWN_SPEAKER_LABEL = "Hablante desconocido"


class SpeakerRegistry:
    """Maps STT diarization ids to stable, human-readable labels for one session.

    Labels are assigned in order of first appearance and never reassigned, so a
    provider id always keeps the same label for the lifetime of the session.
    """

    def __init__(self) -> None:
        self._labels: dict[str, str] = {}

    def resolve(self, provider_speaker_id: str | None) -> tuple[str, str, bool]:
        """Return (speaker_id, speaker_label, is_new)."""
        if provider_speaker_id is None or str(provider_speaker_id).strip() == "":
            return UNKNOWN_SPEAKER_ID, UNKNOWN_SPEAKER_LABEL, False
        key = str(provider_speaker_id).strip()
        if key in self._labels:
            return key, self._labels[key], False
        label = f"Hablante {len(self._labels) + 1}"
        self._labels[key] = label
        return key, label, True

    def peek(self, provider_speaker_id: str | None) -> tuple[str, str]:
        """Look up a label without registering a new speaker (used for unstable partials)."""
        key = (
            str(provider_speaker_id).strip() if provider_speaker_id is not None else ""
        )
        if key in self._labels:
            return key, self._labels[key]
        return UNKNOWN_SPEAKER_ID, UNKNOWN_SPEAKER_LABEL

    @property
    def known(self) -> dict[str, str]:
        return dict(self._labels)
