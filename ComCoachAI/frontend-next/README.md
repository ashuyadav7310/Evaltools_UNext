# ComCoach AI Next.js Frontend

Production-grade Next.js migration of the existing Streamlit frontend. The Streamlit frontend is unchanged.

## Runtime

```bash
npm install
npm run dev
npm run build
npm start
```

The API base URL resolution preserves the existing names:

1. `COMCOACH_API_BASE_URL`
2. `API_BASE_URL`
3. `http://127.0.0.1:8000/api`

Backend routes remain unchanged and under `/api`.

## Audio Reliability Notes

The participant recorder uses browser-native `MediaRecorder` instead of Streamlit recording widgets. It checks secure-context requirements, requests microphone permission directly, selects the best supported mobile MIME type, stores the captured blob in IndexedDB until successful submission, supports manual audio upload fallback, shows upload progress, and allows retry after unstable network failures.

For production mobile recording, serve the frontend over HTTPS. Also keep reverse proxy upload settings aligned with recording sizes and slow cellular uploads. The current nginx config already has `client_max_body_size 100M`; production deployments should also review proxy read/send timeouts if long analysis calls are expected.
