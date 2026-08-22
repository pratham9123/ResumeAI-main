const express = require('express');
const { verifyToken } = require('../middleware/auth');
const Analysis = require('../models/Analysis');
const { serializeAnalysis } = require('../services/analysisPersistence');

const router = express.Router();

// GET /api/history - fetch the authenticated user's analysis history.
router.get('/history', verifyToken, async (req, res) => {
  try {
    const analyses = await Analysis.find({ uid: req.user.uid })
      .sort({ created_at: -1 })
      .select('-resume_text')
      .limit(50);
    return res.json({ analyses: analyses.map(serializeAnalysis) });
  } catch (error) {
    console.error('History retrieval failed', error?.name || 'UnknownError');
    return res.status(500).json({ error: 'Could not load analysis history.' });
  }
});

module.exports = router;
