"""Central configuration. Secrets are read only from the process environment."""
import os
from pathlib import Path
BACKEND_ROOT = Path(__file__).resolve().parent
DATA_ROOT = Path(os.environ.get("PANMAN_DATA_ROOT", str(BACKEND_ROOT)))
RAW_DATA_DIR = str(DATA_ROOT / "raw_data_files")
VECTOR_DB_DIR = str(DATA_ROOT / "vector_db")
ASSISTANT_NAME = os.environ.get("PANMAN_DISPLAY_NAME", "Dr. David Panman")
API_HOST = "127.0.0.1"
API_PORT = 8000
API_LOG_LEVEL = "info"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_CHAT_MODEL = "gpt-5.4-mini"
OPENAI_EMBED_MODEL = "text-embedding-3-small"
OPENAI_EMBED_DIMENSIONS = 1536
OPENAI_STT_MODEL = "gpt-transcribe"
OPENAI_TTS_MODEL = "gpt-4o-mini-tts"
OPENAI_TTS_VOICE = "cedar"
OPENAI_TTS_INSTRUCTIONS = (
    "Speak in a natural, refined British English accent. Use the composed, measured "
    "delivery of an educated British gentleman from the 1920s. Maintain a mature "
    "masculine vocal character, warm tone, clear articulation, and natural conversational "
    "pacing. Avoid theatrical exaggeration, excessive formality, or artificial old-fashioned pronunciation."
)
OPENAI_TIMEOUT_SECONDS = 45
OPENAI_MAX_RETRIES = 0
OPENAI_MAX_CONCURRENT = 4
CHAT_MAX_OUTPUT_TOKENS = 1200
EMBED_QUERY_PREFIX = ""
EMBED_DOCUMENT_PREFIX = ""
EMBED_NORMALIZATION = "l2"
EMBED_CACHE_FILE = str(DATA_ROOT / "vector_db" / "openai_embeddings.sqlite3")
SESSION_MAX_TURNS = 6
SESSION_MAX_CHARS = 10000
SESSION_IDLE_SECONDS = 1800
SESSION_MAX_REQUESTS = 256
MAX_SESSIONS = 20
TURN_TIMEOUT_SECONDS = 180
MAX_AUDIO_BYTES = 10 * 1024 * 1024
RECORDING_SILENCE_MS = 1600
RECORDING_MIN_SPEECH_MS = 450
RECORDING_MAX_MS = 30000
RECORDING_RMS_THRESHOLD = 0.018
RECORDING_PRE_ROLL_MS = 400
RECORDING_BUFFER_FRAMES = 1024
BARGE_IN_RMS_THRESHOLD = 0.045
BARGE_IN_MIN_MS = 250
AUDIO_QUEUE_LIMIT = 4
AUDIO_ACK_TIMEOUT_SECONDS = 90
TTS_STREAM_MIN_CHARS = 60
TTS_STREAM_MAX_CHARS = 320
TTS_STREAM_MAX_BUFFER_SECONDS = 1.5
AVATAR_MODEL_FILE = "assets/scene.gltf"
AVATAR_HEAD_FRACTION = 0.14
AVATAR_HEIGHT_FRACTION = 0.14
AVATAR_WIDTH_FRACTION = 0.13
DIAGNOSTICS_ENABLED = True
# No prices are assumed. Usage logs carry actual reported metadata only.
API_PRICING = {}
BROWSER_ALLOWED_ORIGINS = ("http://localhost:8000", "http://127.0.0.1:8000")
QA_TOP_K = 5
# Indexing and retrieval. Changing embedding models requires running ingestion.
CHROMA_COLLECTION_NAME = "texmin_qa"
INGESTION_VERSION = 9
INDEX_PROMOTION_EVAL_FILE = str(BACKEND_ROOT / "evals" / "golden_local.jsonl")
INDEX_MIN_RECALL_AT_5 = 0.8
CHUNK_SIZE = 900
CHUNK_OVERLAP = 200
EMBEDDING_BATCH_SIZE = 32
INGESTION_WORKERS = 2
FAST_FILE_CHECK = False
MIN_EXTRACTED_TEXT_CHARS = 80
OCR_ENABLED = True
OCR_LANG = "eng+hin"
OCR_PDF_DPI = 200
OCR_TESSERACT_CONFIG = "--psm 6"
OCR_TESSERACT_EXECUTABLE = "tesseract"
OCR_EMBEDDED_IMAGES = True
OCR_MAX_IMAGES_PER_PAGE = 12
OCR_MIN_IMAGE_PIXELS = 10000
RETRIEVAL_FETCH_K = 40
HYBRID_SEARCH_ENABLED = True
HYBRID_RRF_K = 60
CONTEXT_MAX_CHARS = 16000



def validate_config():
    if OPENAI_MAX_RETRIES != 0:
        raise ValueError("Automatic SDK retries must remain disabled to prevent duplicate charges")
    if EMBED_NORMALIZATION != "l2":
        raise ValueError("This index requires l2 normalization")
    if CHUNK_SIZE <= 0 or not 0 <= CHUNK_OVERLAP < CHUNK_SIZE:
        raise ValueError("Invalid chunk sizes")
    if min(OPENAI_EMBED_DIMENSIONS, EMBEDDING_BATCH_SIZE, AUDIO_QUEUE_LIMIT, OPENAI_TIMEOUT_SECONDS) <= 0:
        raise ValueError("Limits must be positive")
    if not 0 < RECORDING_MIN_SPEECH_MS < RECORDING_MAX_MS:
        raise ValueError("Invalid recording duration")


def configure_runtime_environment(**kwargs):
    validate_config()
