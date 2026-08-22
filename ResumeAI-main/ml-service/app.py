import io
import logging
import os
import re
import sys
import time
import uuid

# Force UTF-8 on Windows (avoids charmap codec errors with emoji in logs)
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
from flask import Flask, g, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import RequestEntityTooLarge

load_dotenv()

from knowledge_base.schema import ALLOWED_ROLES
from modules.analysis_pipeline import run_analysis_pipeline
from modules.api_errors import FeedbackGenerationError
from modules.api_response import build_analysis_response
from modules.rag_runtime import get_rag_runtime
from modules.text_extractor import extract_text_from_pdf

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _positive_int_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


MAX_RESUME_BYTES = _positive_int_env("MAX_RESUME_BYTES", 5 * 1024 * 1024)
MAX_REQUEST_BYTES = _positive_int_env("MAX_REQUEST_BYTES", 6 * 1024 * 1024)
MAX_JOB_DESCRIPTION_CHARS = _positive_int_env(
    "MAX_JOB_DESCRIPTION_CHARS", 50_000
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES
CORS(app)

_rag_runtime = get_rag_runtime()
_rag_health = _rag_runtime.initialize()
_rag_enabled = _rag_runtime.settings.enabled
_rag_debug_response = _rag_runtime.settings.debug or _env_flag(
    "RAG_DEBUG_RESPONSE", False
)
_use_transformer = os.getenv("SEMANTIC_MODEL_SHARED", "1") != "0"
logger.info(
    "Service startup complete (rag_enabled=%s, rag_ready=%s, semantic_mode=%s)",
    _rag_enabled,
    _rag_health.ready,
    "sentence-transformers" if _use_transformer else "tfidf",
)


def _request_id() -> str:
    return getattr(g, "request_id", "unknown")


@app.before_request
def assign_request_id():
    supplied = request.headers.get("X-Request-ID", "").strip()
    g.request_id = supplied if REQUEST_ID_PATTERN.fullmatch(supplied) else uuid.uuid4().hex
    g.request_started = time.perf_counter()


@app.after_request
def attach_request_id(response):
    response.headers["X-Request-ID"] = _request_id()
    return response


def _error_response(message: str, error_type: str, status_code: int):
    return jsonify({"error": message, "error_type": error_type}), status_code


@app.errorhandler(RequestEntityTooLarge)
def request_too_large(_error):
    logger.warning("Request rejected (request_id=%s, reason=request_too_large)", _request_id())
    return _error_response("Request is too large.", "validation_error", 413)


@app.route("/health", methods=["GET"])
def health():
    rag_health = _rag_runtime.health
    service_status = "healthy" if not rag_health.enabled or rag_health.ready else "degraded"
    return jsonify(
        {
            "service": "resume-analysis",
            "status": service_status,
            "rag": {
                "enabled": rag_health.enabled,
                "ready": rag_health.ready,
                "knowledgeBaseVersion": rag_health.knowledge_base_version,
            },
        }
    )


@app.route("/analyze", methods=["POST"])
def analyze():
    request_id = _request_id()
    try:
        if "resume" not in request.files:
            return _error_response("No resume file provided.", "validation_error", 400)

        resume_file = request.files["resume"]
        if not resume_file.filename:
            return _error_response("No resume file selected.", "validation_error", 400)
        if not resume_file.filename.lower().endswith(".pdf"):
            return _error_response("Resume must be a PDF file.", "validation_error", 400)

        job_description = request.form.get("job_description", "").strip()
        if not job_description:
            return _error_response("Job description is required.", "validation_error", 400)
        if len(job_description) > MAX_JOB_DESCRIPTION_CHARS:
            return _error_response("Job description is too large.", "validation_error", 413)

        raw_target_role = request.form.get("target_role", "").strip().lower()
        target_role = raw_target_role or None
        if target_role and target_role not in ALLOWED_ROLES:
            return _error_response("Invalid target role.", "validation_error", 400)

        pdf_bytes = resume_file.stream.read(MAX_RESUME_BYTES + 1)
        if len(pdf_bytes) > MAX_RESUME_BYTES:
            return _error_response("Resume file is too large.", "validation_error", 413)
        if not pdf_bytes:
            return _error_response("Empty file uploaded.", "validation_error", 400)

        logger.info("Resume extraction started (request_id=%s)", request_id)
        try:
            resume_text = extract_text_from_pdf(io.BytesIO(pdf_bytes))
        except Exception as exc:
            logger.warning(
                "Resume extraction failed (request_id=%s, error_type=%s)",
                request_id,
                type(exc).__name__,
            )
            return _error_response(
                "Could not process the resume PDF.", "validation_error", 422
            )
        if not resume_text or len(resume_text) < 50:
            return _error_response(
                "Could not extract enough text. Ensure the PDF contains selectable text.",
                "validation_error",
                422,
            )

        result = run_analysis_pipeline(
            resume_text=resume_text,
            job_description=job_description,
            pdf_bytes=pdf_bytes,
            target_role=target_role,
            request_id=request_id,
        )
        public_result = build_analysis_response(
            result,
            include_rag_debug=_rag_debug_response,
        )
        total_latency_ms = round((time.perf_counter() - g.request_started) * 1000)
        fallback_reason = (
            result.get("rag", {}).get("retrieval_metadata", {}).get("fallback_reason")
        )
        logger.info(
            "Analysis completed (request_id=%s, total_latency_ms=%d, score=%s, "
            "retrieved_count=%d, rag_used=%s, fallback_reason=%s)",
            request_id,
            total_latency_ms,
            result.get("weighted_score", {}).get("final_score"),
            public_result["rag"]["retrievedCount"],
            public_result["rag"]["used"],
            fallback_reason or "none",
        )
        return jsonify(public_result)

    except FeedbackGenerationError:
        logger.error("Feedback service failed (request_id=%s)", request_id, exc_info=app.debug)
        return _error_response(
            "AI feedback could not be generated. Please try again.",
            "feedback_error",
            502,
        )
    except Exception as exc:
        logger.error(
            "Analysis failed (request_id=%s, error_type=%s)",
            request_id,
            type(exc).__name__,
            exc_info=app.debug,
        )
        return _error_response("Analysis failed. Please try again.", "analysis_error", 500)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    debug = _env_flag("FLASK_DEBUG", False)
    app.run(host="0.0.0.0", port=port, debug=debug)
