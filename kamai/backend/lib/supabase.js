const { createClient } = require('@supabase/supabase-js')
require('dotenv').config()

const isConfigured = Boolean(process.env.SUPABASE_URL && process.env.SUPABASE_ANON_KEY)

let supabase
if (isConfigured) {
  supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_ANON_KEY)
  supabase.isConfigured = true
} else {
  const configurationError = () => {
    throw new Error('Supabase is not configured. Copy .env.example to .env and add project credentials.')
  }
  supabase = {
    isConfigured: false,
    from: configurationError,
    rpc: configurationError,
  }
  console.warn('Supabase is not configured; database routes are disabled, but health and AI routes remain available.')
}

module.exports = supabase
