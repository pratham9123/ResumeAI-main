const mongoose = require('mongoose');

const ragSourceSchema = new mongoose.Schema({
  id: { type: String, required: true },
  title: { type: String, default: '' },
  category: { type: String, default: '' },
  similarityScore: { type: Number, default: null },
}, { _id: false });

const ragSchema = new mongoose.Schema({
  enabled: Boolean,
  status: String,
  used: Boolean,
  fallbackUsed: Boolean,
  retrievedCount: Number,
  knowledgeBaseVersion: String,
  sourceIds: [String],
  sources: [ragSourceSchema],
}, { _id: false });

const analysisSchema = new mongoose.Schema({
  uid: { type: String, required: true, index: true },
  resume_text: { type: String },
  job_description: { type: String, required: true },
  target_role: { type: String },
  skills: [String],
  matched_skills: [String],
  missing_skills: [String],
  extra_skills: [String],
  skill_categories: { type: Map, of: [String] },
  jd_categories: { type: Map, of: [String] },
  resume_quality: { type: mongoose.Schema.Types.Mixed },
  score: { type: Number, required: true },
  section_scores: { type: Map, of: Number },
  pdf_url: { type: String },
  breakdown: {
    core: Number,
    secondary: Number,
    experience: Number,
    quality: Number,
  },
  similarity_score: { type: Number },
  deterministic_scores: { type: mongoose.Schema.Types.Mixed },
  generated_feedback: { type: mongoose.Schema.Types.Mixed },
  feedback: { type: String },
  suggestions: [String],
  rag: { type: ragSchema, required: false },
  created_at: { type: Date, default: Date.now },
});

module.exports = mongoose.model('Analysis', analysisSchema);
