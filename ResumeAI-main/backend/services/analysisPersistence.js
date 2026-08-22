function sourceIds(rag) {
  return [...new Set((rag.sources || []).map(source => source.id).filter(Boolean))];
}

function buildAnalysisDocument({ uid, jobDescription, targetRole, pdfUrl, mlData }) {
  const feedback = mlData.llm_insights || {};
  const rag = mlData.rag || {
    enabled: false,
    status: 'legacy',
    used: false,
    fallbackUsed: false,
    retrievedCount: 0,
    sources: [],
  };

  return {
    uid,
    resume_text: mlData.resume_text,
    job_description: jobDescription,
    target_role: targetRole,
    skills: mlData.skills || [],
    matched_skills: mlData.skill_gap?.matched || [],
    missing_skills: mlData.skill_gap?.missing || [],
    extra_skills: mlData.skill_gap?.extra || [],
    skill_categories: mlData.skill_categories || {},
    jd_categories: mlData.jd_categories || {},
    resume_quality: mlData.resume_quality || {},
    score: mlData.weighted_score.final_score,
    section_scores: mlData.section_scores || {},
    pdf_url: pdfUrl,
    breakdown: mlData.weighted_score.breakdown || {},
    similarity_score: mlData.similarity_score || 0,
    deterministic_scores: {
      weighted_score: mlData.weighted_score,
      similarity_score: mlData.similarity_score || 0,
      resume_quality: mlData.resume_quality || {},
      section_scores: mlData.section_scores || {},
    },
    generated_feedback: feedback,
    feedback: feedback.feedback || feedback.summary || '',
    suggestions: Array.isArray(feedback.suggestions) ? feedback.suggestions : [],
    rag: {
      enabled: Boolean(rag.enabled),
      status: rag.status || 'unknown',
      used: Boolean(rag.used),
      fallbackUsed: Boolean(rag.fallbackUsed),
      retrievedCount: rag.retrievedCount || 0,
      knowledgeBaseVersion: rag.knowledgeBaseVersion || null,
      sourceIds: sourceIds(rag),
      sources: rag.sources || [],
    },
  };
}

function serializeAnalysis(analysis) {
  const result = typeof analysis.toObject === 'function' ? analysis.toObject() : { ...analysis };
  if (!result.generated_feedback) {
    result.generated_feedback = {
      feedback: result.feedback || '',
      suggestions: result.suggestions || [],
    };
  }
  if (!result.rag) {
    result.rag = {
      enabled: false,
      status: 'legacy',
      used: false,
      fallbackUsed: false,
      retrievedCount: 0,
      knowledgeBaseVersion: null,
      sourceIds: [],
      sources: [],
    };
  }
  return result;
}

module.exports = { buildAnalysisDocument, serializeAnalysis };
