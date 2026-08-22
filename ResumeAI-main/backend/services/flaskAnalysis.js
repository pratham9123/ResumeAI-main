const axios = require('axios');
const FormData = require('form-data');

class FlaskAnalysisError extends Error {
  constructor(message, { status = 502, code = 'flask_error' } = {}) {
    super(message);
    this.name = 'FlaskAnalysisError';
    this.status = status;
    this.code = code;
  }
}

function positiveInteger(value, fallback) {
  const parsed = Number.parseInt(value, 10);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

function flaskSettings(env = process.env) {
  return {
    baseUrl: env.ML_SERVICE_URL || 'http://localhost:8000',
    analysisTimeoutMs: positiveInteger(env.ML_ANALYSIS_TIMEOUT_MS, 240000),
    healthTimeoutMs: positiveInteger(env.ML_HEALTH_TIMEOUT_MS, 15000),
    healthRetries: positiveInteger(env.ML_HEALTH_RETRIES, 10),
    healthRetryDelayMs: positiveInteger(env.ML_HEALTH_RETRY_DELAY_MS, 8000),
  };
}

function sleep(milliseconds) {
  return new Promise(resolve => setTimeout(resolve, milliseconds));
}

async function waitForFlask({ httpClient, settings, sleepFn = sleep }) {
  for (let attempt = 1; attempt <= settings.healthRetries; attempt += 1) {
    try {
      await httpClient.get(`${settings.baseUrl}/health`, {
        timeout: settings.healthTimeoutMs,
      });
      return;
    } catch {
      if (attempt < settings.healthRetries) {
        await sleepFn(settings.healthRetryDelayMs);
      }
    }
  }
  throw new FlaskAnalysisError(
    'Analysis service is still starting. Please try again shortly.',
    { status: 503, code: 'flask_unavailable' },
  );
}

function normalizeRag(rag) {
  if (!rag || typeof rag !== 'object' || Array.isArray(rag)) {
    return {
      enabled: false,
      status: 'legacy',
      used: false,
      fallbackUsed: false,
      retrievedCount: 0,
      sources: [],
    };
  }

  const sources = Array.isArray(rag.sources)
    ? rag.sources
      .filter(source => source && typeof source.id === 'string')
      .map(source => ({
        id: source.id,
        title: typeof source.title === 'string' ? source.title : '',
        category: typeof source.category === 'string' ? source.category : '',
        similarityScore: Number.isFinite(source.similarityScore)
          ? source.similarityScore
          : null,
      }))
    : [];

  return {
    enabled: Boolean(rag.enabled),
    status: typeof rag.status === 'string' ? rag.status : 'unknown',
    used: Boolean(rag.used),
    fallbackUsed: Boolean(rag.fallbackUsed),
    retrievedCount: Number.isInteger(rag.retrievedCount)
      ? Math.max(0, rag.retrievedCount)
      : sources.length,
    knowledgeBaseVersion: typeof rag.knowledgeBaseVersion === 'string'
      ? rag.knowledgeBaseVersion
      : null,
    sources,
  };
}

function validateFlaskResponse(payload) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    throw new FlaskAnalysisError('Analysis service returned an invalid response.', {
      code: 'malformed_flask_response',
    });
  }
  if (!Number.isFinite(payload.weighted_score?.final_score)) {
    throw new FlaskAnalysisError('Analysis service returned an invalid score.', {
      code: 'malformed_flask_response',
    });
  }
  if (!payload.skill_gap || typeof payload.skill_gap !== 'object') {
    throw new FlaskAnalysisError('Analysis service returned invalid skill analysis.', {
      code: 'malformed_flask_response',
    });
  }
  if (!payload.llm_insights || typeof payload.llm_insights !== 'object') {
    throw new FlaskAnalysisError('Analysis service returned invalid feedback.', {
      code: 'malformed_flask_response',
    });
  }
  return { ...payload, rag: normalizeRag(payload.rag) };
}

function toPublicFlaskError(error) {
  if (error instanceof FlaskAnalysisError) return error;
  if (error?.code === 'ECONNABORTED' || error?.code === 'ETIMEDOUT') {
    return new FlaskAnalysisError(
      'Resume analysis took too long. Please try again.',
      { status: 504, code: 'flask_timeout' },
    );
  }
  const upstreamStatus = Number(error?.response?.status);
  const upstreamMessage = error?.response?.data?.error;
  if (
    upstreamStatus >= 400
    && upstreamStatus < 500
    && typeof upstreamMessage === 'string'
    && !/https?:\/\//i.test(upstreamMessage)
  ) {
    return new FlaskAnalysisError(upstreamMessage, {
      status: upstreamStatus,
      code: 'flask_validation_error',
    });
  }
  return new FlaskAnalysisError(
    'The analysis service could not complete this request. Please try again.',
    { status: 502, code: 'flask_error' },
  );
}

async function requestFlaskAnalysis({
  resumeFile,
  jobDescription,
  targetRole,
  requestId,
  httpClient = axios,
  FormDataClass = FormData,
  settings = flaskSettings(),
  sleepFn,
}) {
  await waitForFlask({ httpClient, settings, sleepFn });

  const form = new FormDataClass();
  form.append('resume', resumeFile.buffer, {
    filename: resumeFile.originalname,
    contentType: resumeFile.mimetype || 'application/pdf',
  });
  form.append('job_description', jobDescription);
  if (targetRole) {
    form.append('target_role', targetRole);
  }

  try {
    // This POST is deliberately attempted once. Retrying could create duplicate analyses.
    const response = await httpClient.post(
      `${settings.baseUrl}/analyze`,
      form,
      {
        headers: {
          ...form.getHeaders(),
          'X-Request-ID': requestId,
        },
        timeout: settings.analysisTimeoutMs,
      },
    );
    return validateFlaskResponse(response.data);
  } catch (error) {
    throw toPublicFlaskError(error);
  }
}

module.exports = {
  FlaskAnalysisError,
  flaskSettings,
  normalizeRag,
  requestFlaskAnalysis,
  validateFlaskResponse,
  waitForFlask,
};
