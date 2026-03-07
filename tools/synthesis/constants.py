"""Constants and model selection for synthesis pipeline."""
from tools.research_common import model_for_lane

MAX_FINDINGS = 80
EXCERPT_CHARS = 2000
SOURCE_CONTENT_CHARS = 6000
SECTION_WORDS_MIN, SECTION_WORDS_MAX = 500, 1500
SYNTHESIZE_CHECKPOINT = "synthesize_checkpoint.json"


def _model() -> str:
    return model_for_lane("synthesize")
