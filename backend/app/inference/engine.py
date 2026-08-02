"""The single point of contact between the web app and the AI model.

Every other module calls `run_inference()` and nothing else. Swapping the trained
model (.pt / ONNX) means editing the body of this function only — the signature and
the returned payload shape must not change. See docs/SWAP_MODEL.md.
"""

from app.inference import mock


def run_inference(image_path: str, gps: tuple[float, float] | None = None) -> dict:
    """Detect and classify palm trees in one image.

    Returns ``{"detections": [...]}`` where each detection carries `bbox`, `disease`,
    `severity`, `confidence` and `gps` — the model-derived half of the JSON contract
    in CLAUDE.md. Identity fields (`image_id`, `filename`, `captured_at`) and the
    `summary` are added by the caller, which owns that data; the model cannot know them.

    `gps` is the image centre from EXIF, passed in so detections can be geo-referenced.

    CURRENT STAGE: mocked. To use the real model, replace the call below with
    loading the .pt/ONNX file and running predict, then map its output into the
    same dict shape. Nothing else in the codebase changes.
    """
    return mock.generate(image_path, gps)
