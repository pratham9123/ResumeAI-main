require('dotenv').config();
const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const morgan = require('morgan');
const mongoose = require('mongoose');
const rateLimit = require('express-rate-limit');
const path = require('path');
const crypto = require('crypto');

const analyzeRoutes = require('./routes/analyze');
const historyRoutes = require('./routes/history');

const app = express();
const PORT = process.env.PORT || 5000;
const requestIdPattern = /^[A-Za-z0-9._-]{1,64}$/;
app.use((req, res, next) => {
  const supplied = String(req.get('X-Request-ID') || '').trim();
  req.id = requestIdPattern.test(supplied) ? supplied : crypto.randomUUID();
  res.setHeader('X-Request-ID', req.id);
  next();
});



// Required for Render/Heroku/Railway – they sit behind a reverse proxy
// Without this, express-rate-limit throws ERR_ERL_UNEXPECTED_X_FORWARDED_FOR
app.set('trust proxy', 1);

// Security & middleware
// app.use(helmet({ 
//   crossOriginEmbedderPolicy: false,
//   crossOriginResourcePolicy: { policy: "cross-origin" },
//   frameguard: false,
//   contentSecurityPolicy: false
// }));
// app.use((req, res, next) => {
//   res.removeHeader('Content-Security-Policy');
//   res.removeHeader('X-Frame-Options');
//   next();
// });
const allowedOrigins = (process.env.FRONTEND_URL || 'http://localhost:3000').split(',').map(o => o.trim());
app.use(cors({ origin: allowedOrigins, credentials: true }));


app.use(morgan('dev'));
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));

// Serve local uploads as fallback for PDFs
app.use('/uploads', express.static(path.join(__dirname, 'uploads')));

// Rate limiting
app.use('/api/analyze', rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 20,
  message: { error: 'Too many analysis requests. Please wait.' }
}));

// MongoDB
mongoose.connect(process.env.MONGODB_URI || 'mongodb://localhost:27017/resumeai')
  .then(() => console.log('✅ MongoDB connected'))
  .catch(err => console.error('❌ MongoDB error:', err));

// Routes
app.use('/api', analyzeRoutes);
app.use('/api', historyRoutes);

// Health check
app.get('/api/health', (req, res) => res.json({ status: 'ok', time: new Date() }));

// Error handler
app.use((err, req, res, next) => {
  console.error('Unhandled backend error', err?.name || 'UnknownError');
  res.status(500).json({ error: 'Internal server error' });
});

const server = app.listen(PORT, () => console.log(`🚀 Backend running on port ${PORT}`));

// Allow the configured Flask timeout plus persistence overhead.
const flaskTimeoutMs = Number.parseInt(process.env.ML_ANALYSIS_TIMEOUT_MS || '240000', 10);
server.setTimeout((Number.isFinite(flaskTimeoutMs) ? flaskTimeoutMs : 240000) + 30000);
