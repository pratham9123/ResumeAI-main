const express = require('express');
const multer = require('multer');
const cloudinary = require('cloudinary').v2;
const streamifier = require('streamifier');
const { verifyToken } = require('../middleware/auth');
const Analysis = require('../models/Analysis');
const { normalizeTargetRole } = require('../constants/targetRoles');
const {
  FlaskAnalysisError,
  requestFlaskAnalysis,
} = require('../services/flaskAnalysis');
const {
  buildAnalysisDocument,
  serializeAnalysis,
} = require('../services/analysisPersistence');

cloudinary.config({
  cloud_name: process.env.CLOUDINARY_CLOUD_NAME,
  api_key: process.env.CLOUDINARY_API_KEY,
  api_secret: process.env.CLOUDINARY_API_SECRET,
});

const router = express.Router();
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 5 * 1024 * 1024 },
});

async function persistPdf(buffer, originalName, uid) {
  const safeName = originalName.replace(/[^a-zA-Z0-9.-]/g, '_');
  try {
    if (!process.env.CLOUDINARY_CLOUD_NAME) {
      throw new Error('Cloud storage is not configured');
    }
    return await new Promise((resolve, reject) => {
      const stream = cloudinary.uploader.upload_stream(
        {
          resource_type: 'raw',
          type: 'upload',
          access_mode: 'public',
          public_id: `resumes/${uid}/${Date.now()}-${safeName}`,
        },
        (error, result) => (result ? resolve(result.secure_url) : reject(error)),
      );
      streamifier.createReadStream(buffer).pipe(stream);
    });
  } catch (error) {
    console.warn('Cloud resume storage unavailable; using local fallback', error?.name);
    const fs = require('fs');
    const path = require('path');
    const uploadDir = path.join(__dirname, '../uploads');
    if (!fs.existsSync(uploadDir)) fs.mkdirSync(uploadDir, { recursive: true });
    const fileName = `${Date.now()}-${safeName}`;
    fs.writeFileSync(path.join(uploadDir, fileName), buffer);
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:5000';
    return `${backendUrl}/uploads/${fileName}`;
  }
}

// POST /api/analyze
router.post('/analyze', verifyToken, upload.single('resume'), async (req, res) => {
  try {
    const { job_description: jobDescription, target_role: rawTargetRole } = req.body;
    const uid = req.user.uid;

    if (!req.file) return res.status(400).json({ error: 'No resume file uploaded' });
    if (!jobDescription?.trim()) {
      return res.status(400).json({ error: 'Job description is required' });
    }

    const targetRole = normalizeTargetRole(rawTargetRole);
    if (rawTargetRole && !targetRole) {
      return res.status(400).json({ error: 'Invalid target role' });
    }

    const mlData = await requestFlaskAnalysis({
      resumeFile: req.file,
      jobDescription: jobDescription.trim(),
      targetRole,
      requestId: req.id,
    });

    const pdfUrl = await persistPdf(req.file.buffer, req.file.originalname, uid);
    const analysis = new Analysis(buildAnalysisDocument({
      uid,
      jobDescription: jobDescription.trim(),
      targetRole,
      pdfUrl,
      mlData,
    }));
    await analysis.save();

    return res.json({
      analysisId: analysis._id,
      score: analysis.score,
      rag: {
        used: Boolean(analysis.rag?.used),
        fallbackUsed: Boolean(analysis.rag?.fallbackUsed),
      },
    });
  } catch (error) {
    if (error instanceof FlaskAnalysisError) {
      console.warn('Flask analysis request failed', { requestId: req.id, code: error.code });
      return res.status(error.status).json({ error: error.message });
    }
    console.error('Analyze request failed', { requestId: req.id, errorType: error?.name || 'UnknownError' });
    return res.status(500).json({ error: 'Analysis failed. Please try again.' });
  }
});

// GET /api/result/:id
router.get('/result/:id', verifyToken, async (req, res) => {
  try {
    const analysis = await Analysis.findOne({ _id: req.params.id, uid: req.user.uid });
    if (!analysis) return res.status(404).json({ error: 'Analysis not found' });
    const result = serializeAnalysis(analysis);
    if (result.pdf_url) result.pdf_proxy_url = `/api/pdf/${analysis._id}`;
    return res.json(result);
  } catch (error) {
    console.error('Result retrieval failed', error?.name || 'UnknownError');
    return res.status(500).json({ error: 'Could not load analysis.' });
  }
});

// GET /api/pdf/:id - Proxy the PDF through the backend.
router.get('/pdf/:id', verifyToken, async (req, res) => {
  try {
    const analysis = await Analysis.findOne({ _id: req.params.id, uid: req.user.uid });
    if (!analysis?.pdf_url) return res.status(404).json({ error: 'PDF not found' });

    const pdfUrl = analysis.pdf_url;
    if (pdfUrl.startsWith('http://localhost') || pdfUrl.startsWith('http://127.0.0.1')) {
      const path = require('path');
      const urlPath = new URL(pdfUrl).pathname;
      return res.sendFile(path.join(__dirname, '..', urlPath));
    }

    const protocol = pdfUrl.startsWith('https') ? require('https') : require('http');
    return protocol.get(pdfUrl, stream => {
      res.setHeader('Content-Type', 'application/pdf');
      res.setHeader('Content-Disposition', 'inline');
      stream.pipe(res);
    }).on('error', () => {
      res.status(502).json({ error: 'Could not fetch PDF' });
    });
  } catch (error) {
    console.error('PDF retrieval failed', error?.name || 'UnknownError');
    return res.status(500).json({ error: 'Could not load PDF.' });
  }
});

router.delete('/result/:id', verifyToken, async (req, res) => {
  try {
    const analysis = await Analysis.findOneAndDelete({
      _id: req.params.id,
      uid: req.user.uid,
    });
    if (!analysis) return res.status(404).json({ error: 'Analysis not found' });
    return res.json({ success: true });
  } catch (error) {
    console.error('Analysis deletion failed', error?.name || 'UnknownError');
    return res.status(500).json({ error: 'Could not delete analysis.' });
  }
});

module.exports = router;
