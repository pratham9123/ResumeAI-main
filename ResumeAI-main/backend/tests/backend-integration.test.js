const test = require('node:test');
const assert = require('node:assert/strict');

const Analysis = require('../models/Analysis');
const { normalizeTargetRole } = require('../constants/targetRoles');
const {
  FlaskAnalysisError,
  requestFlaskAnalysis,
  validateFlaskResponse,
} = require('../services/flaskAnalysis');
const {
  buildAnalysisDocument,
  serializeAnalysis,
} = require('../services/analysisPersistence');

function flaskPayload(overrides = {}) {
  return {
    resume_text: 'Resume text',
    skills: ['python'],
    skill_categories: {},
    jd_categories: {},
    skill_gap: { matched: ['python'], missing: ['docker'], extra: [] },
    similarity_score: 0.61,
    weighted_score: { final_score: 72, breakdown: { core: 0.7 } },
    resume_quality: { overall: 0.7 },
    section_scores: { projects: 7 },
    llm_insights: {
      summary: 'Good backend alignment.',
      feedback: 'Good backend alignment.',
      suggestions: ['Add deployment evidence.'],
      priority_actions: [],
    },
    rag: {
      enabled: true,
      status: 'success',
      used: true,
      fallbackUsed: false,
      retrievedCount: 1,
      knowledgeBaseVersion: 'sha256:test-version',
      sources: [{
        id: 'backend-001',
        title: 'Backend guidance',
        category: 'project_bullets',
        similarityScore: 0.78,
        text: 'must not be persisted',
      }],
    },
    ...overrides,
  };
}

class FakeFormData {
  constructor() {
    this.entries = [];
    FakeFormData.instance = this;
  }

  append(...args) {
    this.entries.push(args);
  }

  getHeaders() {
    return { 'content-type': 'multipart/form-data; boundary=test' };
  }
}

const settings = {
  baseUrl: 'http://internal-ml:8000',
  analysisTimeoutMs: 321000,

  healthTimeoutMs: 100,
  healthRetries: 1,
  healthRetryDelayMs: 1,
};

test('accepts only supported target-role identifiers', () => {
  assert.equal(normalizeTargetRole(' Backend_Developer '), 'backend_developer');
  assert.equal(normalizeTargetRole('astronaut'), null);
  assert.equal(normalizeTargetRole(''), null);
});

test('forwards resume, job description, and target role to Flask exactly once', async () => {
  const calls = { get: 0, post: 0 };
  const httpClient = {
    async get(url, config) {
      calls.get += 1;
      assert.equal(url, 'http://internal-ml:8000/health');
      assert.equal(config.timeout, 100);
    },
    async post(url, form, config) {
      calls.post += 1;
      assert.equal(url, 'http://internal-ml:8000/analyze');
      assert.equal(form, FakeFormData.instance);
      assert.equal(config.timeout, 321000);
      assert.equal(config.headers['X-Request-ID'], 'req-backend-1');
      return { data: flaskPayload() };
    },
  };

  await requestFlaskAnalysis({
    resumeFile: {
      buffer: Buffer.from('pdf'),
      originalname: 'resume.pdf',
      mimetype: 'application/pdf',
    },
    jobDescription: 'Backend role requiring Python.',
    targetRole: 'backend_developer',
    requestId: 'req-backend-1',
    httpClient,
    FormDataClass: FakeFormData,
    settings,
  });

  assert.equal(calls.get, 1);
  assert.equal(calls.post, 1);
  assert.deepEqual(
    FakeFormData.instance.entries.map(entry => entry[0]),
    ['resume', 'job_description', 'target_role'],
  );
  assert.equal(FakeFormData.instance.entries[1][1], 'Backend role requiring Python.');
  assert.equal(FakeFormData.instance.entries[2][1], 'backend_developer');
});

test('normalizes a successful RAG response and strips full source text', () => {
  const result = validateFlaskResponse(flaskPayload());

  assert.equal(result.rag.used, true);
  assert.equal(result.rag.knowledgeBaseVersion, 'sha256:test-version');
  assert.deepEqual(result.rag.sources[0], {
    id: 'backend-001',
    title: 'Backend guidance',
    category: 'project_bullets',
    similarityScore: 0.78,
  });
});

test('accepts a legacy Flask response without RAG fields', () => {
  const payload = flaskPayload();
  delete payload.rag;

  const result = validateFlaskResponse(payload);

  assert.equal(result.rag.status, 'legacy');
  assert.equal(result.rag.used, false);
  assert.deepEqual(result.rag.sources, []);
});

test('maps a Flask analysis timeout to a safe 504 without retrying POST', async () => {
  let postCalls = 0;
  const httpClient = {
    async get() {},
    async post() {
      postCalls += 1;
      const error = new Error('timeout at http://internal-ml:8000');
      error.code = 'ECONNABORTED';
      throw error;
    },
  };

  await assert.rejects(
    requestFlaskAnalysis({
      resumeFile: { buffer: Buffer.from('pdf'), originalname: 'resume.pdf' },
      jobDescription: 'Backend role requiring Python.',
      targetRole: 'backend_developer',
      httpClient,
      FormDataClass: FakeFormData,
      settings,
    }),
    error => {
      assert.ok(error instanceof FlaskAnalysisError);
      assert.equal(error.status, 504);
      assert.equal(error.code, 'flask_timeout');
      assert.doesNotMatch(error.message, /internal-ml/);
      return true;
    },
  );
  assert.equal(postCalls, 1);
});

test('rejects malformed Flask responses', () => {
  assert.throws(
    () => validateFlaskResponse({ weighted_score: { final_score: 'bad' } }),
    error => error.code === 'malformed_flask_response' && error.status === 502,
  );
});

test('maps RAG metadata and generated feedback into a valid MongoDB document', async () => {
  const mapped = buildAnalysisDocument({
    uid: 'user-1',
    jobDescription: 'Backend role requiring Python.',
    targetRole: 'backend_developer',
    pdfUrl: 'https://files.example/resume.pdf',
    mlData: validateFlaskResponse(flaskPayload()),
  });
  const document = new Analysis(mapped);

  await document.validate();
  assert.equal(document.rag.used, true);
  assert.deepEqual(document.rag.sourceIds, ['backend-001']);
  assert.equal(document.rag.knowledgeBaseVersion, 'sha256:test-version');
  assert.equal(document.generated_feedback.summary, 'Good backend alignment.');
  assert.equal(document.rag.sources[0].text, undefined);
});

test('normalizes older MongoDB records without RAG or structured feedback', () => {
  const oldDocument = Analysis.hydrate({
    _id: '507f1f77bcf86cd799439011',
    uid: 'user-1',
    job_description: 'Legacy job description',
    score: 64,
    feedback: 'Legacy feedback',
    suggestions: ['Legacy suggestion'],
  });

  const result = serializeAnalysis(oldDocument);

  assert.equal(result.feedback, 'Legacy feedback');
  assert.equal(result.generated_feedback.feedback, 'Legacy feedback');
  assert.equal(result.rag.status, 'legacy');
  assert.equal(result.rag.used, false);
});
