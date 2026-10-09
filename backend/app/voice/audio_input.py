from livekit.agents import room_io
from livekit.plugins import ai_coustics

NOISE_MODELS = {
    "quail_l": ai_coustics.EnhancerModel.QUAIL_L,
    "quail_vf_s": ai_coustics.EnhancerModel.QUAIL_VF_S,
    "quail_vf_l": ai_coustics.EnhancerModel.QUAIL_VF_L,
}


def build_audio_input(
    noise_model: str, enhancement_level: float | None
) -> room_io.AudioInputOptions:
    """Server-side noise suppression for the shared microphone.

    QUAIL_L removes non-speech noise and keeps every voice. The *_VF ("voice focus")
    models isolate the foreground speaker and would erase secondary participants,
    which defeats multi-speaker diarization, so they are only kept for comparison.
    """
    if noise_model == "none":
        return room_io.AudioInputOptions()
    parameters = (
        ai_coustics.ModelParameters(enhancement_level=enhancement_level)
        if enhancement_level is not None
        else None
    )
    return room_io.AudioInputOptions(
        noise_cancellation=ai_coustics.audio_enhancement(
            model=NOISE_MODELS[noise_model], model_parameters=parameters
        )
    )
