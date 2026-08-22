import axios from 'axios';

// In dev: VITE_API_URL is empty → relative URLs → Vite proxy → localhost:5000
// In prod: VITE_API_URL = 'https://your-backend.onrender.com' → direct calls
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
});

export default api;
