"""The single point of contact between the web app and the AI model.

Every other module calls `run_inference()` and nothing else. Swapping the trained
model (.pt / ONNX) means editing the body of this function only — the signature and
the returned payload shape must not change. See docs/SWAP_MODEL.md.
"""


def run_inference(image_path: str) -> dict:
    """Run detection + classification on one image.

    Returns a payload matching the JSON contract in CLAUDE.md
    (keys: summary, detections).

    CURRENT STAGE: not implemented yet. Stage 3 fills this in with a realistic
    mock generator; the real model is loaded here later.
    """
    raise NotImplementedError("Implemented in stage 3 (mock inference).")
