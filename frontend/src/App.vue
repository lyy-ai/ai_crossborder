<template>
  <div>
    <Job v-if="currentJob" :jid="currentJob" @back="currentJob = null" />
    <template v-else>
    <div class="header">
      <h1>🌍 跨境爆品短视频工厂</h1>
      <div>
        <span v-for="(ok, name) in healthBadges" :key="name" class="badge" :class="ok ? 'ok' : 'bad'">{{ svcNames[name] || name }}</span>
      </div>
    </div>

    <div class="tabs">
      <div class="tab" :class="{ active: tab === 'products' }" @click="tab = 'products'">📦 产品档案</div>
      <div class="tab" :class="{ active: tab === 'jobs' }" @click="tab = 'jobs'; loadJobs()">🚀 批量任务</div>
    </div>

    <!-- 产品档案 -->
    <div v-if="tab === 'products'">
      <div class="card">
        <h2>✨ 新建产品</h2>
        <div class="row">
          <div><label>产品名称</label><input v-model="pform.name" placeholder="例如：SoundPro X5 无线蓝牙耳机" /></div>
          <div><label>品类</label><input v-model="pform.category" placeholder="例如：3C数码" /></div>
          <div>
            <label>目标市场</label>
            <select v-model="pform.market">
              <option v-for="m in markets" :key="m">{{ m }}</option>
            </select>
          </div>
        </div>
        <label>产品卖点（用；分隔，3-5 条）</label>
        <textarea v-model="pform.selling_points" rows="2" placeholder="例如：40小时超长续航；主动降噪-45dB；蓝牙5.4低延迟；IPX5防水"></textarea>
        <label>产品图（白底图最佳，可多选）</label>
        <label class="upload-box">
          <input type="file" multiple accept="image/*" style="display:none" @change="e => pform.files = e.target.files" />
          <span class="upload-icon">🖼️</span>
          <span v-if="!pform.files || !pform.files.length">点击选择图片（可多选）</span>
          <span v-else class="upload-files">已选 {{ pform.files.length }} 张：{{ [...pform.files].map(f => f.name).join('、') }}</span>
        </label>
        <div style="margin-top:16px">
          <button class="btn green big" :disabled="creating" @click="createProduct">{{ creating ? '上传中…' : '💾 保存产品' }}</button>
          <span v-if="pmsg" class="muted" style="margin-left:12px">{{ pmsg }}</span>
        </div>
      </div>

      <div class="card" v-for="p in products" :key="p.id">
        <div style="display:flex;justify-content:space-between">
          <div style="flex:1">
            <b>{{ p.name }}</b> <span class="badge info">{{ p.market }}</span> <span class="badge info">{{ p.category }}</span>
            <div class="muted" style="margin-top:6px">{{ p.selling_points.join('；') }}</div>
            <div class="thumbs">
              <img v-for="img in p.images" :key="img" :src="api.productImg(p.id, img)" />
            </div>
          </div>
          <div style="margin-left:16px;display:flex;flex-direction:column;gap:8px">
            <button class="btn" @click="openWizard(p)">🎬 批量生成视频</button>
            <button class="btn red" @click="removeProduct(p)">🗑 删除产品</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 批量任务列表 -->
    <div v-if="tab === 'jobs'">
      <div class="card">
        <div v-if="!jobs.length" class="muted">暂无任务，先到「产品档案」创建产品并发起批量生成</div>
        <div v-for="j in jobs" :key="j.id" class="item" @click="currentJob = j.id">
          <div>
            <b>{{ productName(j.product_id) }}</b>
            <div class="muted">{{ j.platforms.join('/') }} · {{ j.languages.join('/') }} · {{ j.variants }}变体</div>
          </div>
          <span class="badge" :class="j.status === 'done' ? 'ok' : (j.status === 'failed' ? 'bad' : 'run')">{{ statusText(j.status) }}</span>
        </div>
      </div>
    </div>

    <!-- 生成向导弹层 -->
    <div v-if="wizard" class="modal-mask" @click.self="wizard = null">
      <div class="card modal">
        <h2>🎬 批量生成 · {{ wizard.name }}</h2>
        <label>目标平台（多选）</label>
        <div class="pills">
          <span v-for="p in ['tiktok', 'shorts', 'reels']" :key="p" class="pill"
                :class="{ on: wform.platforms.includes(p) }" @click="toggle(wform.platforms, p)">
            {{ { tiktok: '🎵 TikTok', shorts: '▶️ YouTube Shorts', reels: '📸 Instagram Reels' }[p] }}
          </span>
        </div>
        <label>语言（多选）</label>
        <div class="pills">
          <span class="pill" :class="{ on: wform.languages.includes('en') }" @click="toggle(wform.languages, 'en')">🇺🇸 英语</span>
          <span class="pill" :class="{ on: wform.languages.includes('ja') }" @click="toggle(wform.languages, 'ja')">🇯🇵 日语</span>
        </div>
        <div class="row">
          <div><label>每平台每语言变体数</label><input type="number" v-model.number="wform.variants" min="1" max="5" /></div>
          <div>
            <label>配音音色</label>
            <select v-model="wform.voice_gender"><option value="female">女声</option><option value="male">男声</option></select>
          </div>
          <div>
            <label>模式</label>
            <select v-model="wform.auto_produce">
              <option :value="false">先审脚本再制作</option>
              <option :value="true">全自动一键出片</option>
            </select>
          </div>
        </div>
        <div class="warn" style="margin-top:10px;font-size:14px">预计生成 {{ wform.platforms.length * wform.languages.length * wform.variants }} 条视频；AI 场景镜头每个约 1-2 分钟</div>
        <div style="margin-top:16px">
          <button class="btn green big" :disabled="!wform.platforms.length || !wform.languages.length || starting" @click="startJob">{{ starting ? '创建中…' : '🚀 开始批量生成' }}</button>
          <button class="btn gray big" style="margin-left:10px" @click="wizard = null">取消</button>
        </div>
      </div>
    </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from './api'
import Job from './Job.vue'

const currentJob = ref(null)

const tab = ref('products')
const products = ref([])
const jobs = ref([])
const health = ref({})
const creating = ref(false)
const pmsg = ref('')
const wizard = ref(null)
const starting = ref(false)
const markets = ['美国', '欧洲', '日本', '东南亚', '中东']
const svcNames = { llm: '脚本', comfy: '绘图', video: '视频', tts: '配音', bailian: '云端百炼' }
const healthBadges = computed(() => {
  const h = health.value || {}
  const usingCloud = h._providers && Object.values(h._providers).some(m => m === 'bailian')
  if (usingCloud) return { bailian: !!h.bailian }
  return Object.fromEntries(Object.entries(h).filter(([k]) => !k.startsWith('_') && k !== 'bailian'))
})
const pform = ref({ name: '', category: '', market: '美国', selling_points: '', files: [] })
const wform = ref({ platforms: ['tiktok'], languages: ['en'], variants: 2, voice_gender: 'female', auto_produce: false })

function statusText(s) {
  return { created: '已创建', running: '进行中', script_done: '脚本完成', done: '已完成', partial: '部分完成', failed: '失败' }[s] || s
}
function productName(pid) {
  const p = products.value.find(x => x.id === pid)
  return p ? p.name : pid
}
async function loadProducts() { products.value = (await api.listProducts()).products }
async function loadJobs() {
  jobs.value = (await api.listJobs()).jobs
  if (!products.value.length) await loadProducts()
}
async function createProduct() {
  if (!pform.value.name.trim()) { pmsg.value = '请填写产品名称（输入框里的文字只是示例提示）'; return }
  if (!pform.value.selling_points.trim()) { pmsg.value = '请填写产品卖点（输入框里的文字只是示例提示）'; return }
  if (!pform.value.files || !pform.value.files.length) { pmsg.value = '请选择至少 1 张产品图'; return }
  creating.value = true; pmsg.value = ''
  try {
    const fd = new FormData()
    fd.append('name', pform.value.name)
    fd.append('selling_points', pform.value.selling_points)
    fd.append('market', pform.value.market)
    fd.append('category', pform.value.category)
    for (const f of pform.value.files) fd.append('files', f)
    const r = await api.createProduct(fd)
    pmsg.value = '已保存，正在打开生成向导…'
    await loadProducts()
    const np = products.value.find(x => x.id === r.product_id)
    if (np) openWizard(np)
    pform.value = { name: '', category: '', market: '美国', selling_points: '', files: [] }
  } catch (e) { pmsg.value = '失败: ' + e.message }
  creating.value = false
}
function openWizard(p) { wizard.value = p }
async function removeProduct(p) {
  if (!confirm(`确定删除产品「${p.name}」吗？该产品的图片档案会一并删除（已生成的成片不受影响）。`)) return
  try {
    await api.deleteProduct(p.id)
    await loadProducts()
  } catch (e) { alert('删除失败: ' + e.message) }
}
function toggle(arr, v) {
  const i = arr.indexOf(v)
  if (i >= 0) arr.splice(i, 1); else arr.push(v)
}
async function startJob() {
  starting.value = true
  try {
    const r = await api.createJob({ product_id: wizard.value.id, ...wform.value })
    wizard.value = null
    currentJob.value = r.job_id
  } catch (e) { alert(e.message) }
  starting.value = false
}

onMounted(async () => {
  await loadProducts()
  try { health.value = await api.health() } catch (e) {}
  setInterval(async () => { try { health.value = await api.health() } catch (e) {} }, 30000)
})
</script>
