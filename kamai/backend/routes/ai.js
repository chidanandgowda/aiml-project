const express = require('express')

const router = express.Router()
const ML_SERVICE_URL = (process.env.ML_SERVICE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')

async function forwardToModel(path, options = {}) {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 10_000)
  try {
    const response = await fetch(`${ML_SERVICE_URL}${path}`, {
      ...options,
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    })
    return { status: response.status, payload: await response.json() }
  } finally {
    clearTimeout(timeout)
  }
}

router.get('/health', async (_req, res) => {
  try {
    const result = await forwardToModel('/health')
    res.status(result.status).json(result.payload)
  } catch (_error) {
    res.status(503).json({
      error: 'Kamai ML service is unavailable',
      action: 'Start kamai/ml/serve_model.py and try again.',
    })
  }
})

router.get('/model-info', async (_req, res) => {
  try {
    const result = await forwardToModel('/model-info')
    res.status(result.status).json(result.payload)
  } catch (_error) {
    res.status(503).json({ error: 'Kamai ML service is unavailable' })
  }
})

for (const endpoint of ['predict', 'recommend', 'rank']) {
  router.post(`/${endpoint}`, async (req, res) => {
    try {
      const result = await forwardToModel(`/${endpoint}`, {
        method: 'POST',
        body: JSON.stringify(req.body),
      })
      res.status(result.status).json(result.payload)
    } catch (_error) {
      res.status(503).json({ error: 'Kamai ML service is unavailable' })
    }
  })
}

module.exports = router
