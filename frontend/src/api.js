const API = `http://${location.hostname}:10046`

export async function req(path, opts = {}) {
  const r = await fetch(API + path, opts)
  if (!r.ok) throw new Error((await r.text()).slice(0, 300))
  return r.json()
}

export const api = {
  base: API,
  staticUrl: (rel) => `${API}/static/output/${rel}`,
  productImg: (pid, fname) => `${API}/static/output/products/${pid}/${fname}`,
  listProducts: () => req('/api/products'),
  deleteProduct: (pid) => req(`/api/products/${pid}`, { method: 'DELETE' }),
  createProduct: (formData) => req('/api/products', { method: 'POST', body: formData }),
  listJobs: () => req('/api/jobs'),
  createJob: (body) => req('/api/jobs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  getJob: (jid) => req(`/api/jobs/${jid}`),
  saveScript: (vid, script) => req(`/api/videos/${vid}/script`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(script) }),
  regenScript: (vid) => req(`/api/videos/${vid}/regen_script`, { method: 'POST' }),
  produce: (jid) => req(`/api/jobs/${jid}/produce`, { method: 'POST' }),
  reproduce: (vid) => req(`/api/videos/${vid}/reproduce`, { method: 'POST' }),
  downloadUrl: (jid) => `${API}/api/jobs/${jid}/download`,
  health: () => req('/api/health/services'),
  wsUrl: (jid) => `ws://${location.hostname}:10046/ws/${jid}`,
}
