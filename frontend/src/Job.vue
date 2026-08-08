<template>
  <div v-if="data">
    <div class="card" style="display:flex;justify-content:space-between;align-items:center">
      <div>
        <button class="btn gray small" @click="$emit('back')">← 返回</button>
        <b style="font-size:17px;margin-left:10px">{{ data.product?.name }}</b>
        <span class="badge info">{{ data.job.platforms.join('/') }}</span>
        <span class="badge info">{{ data.job.languages.join('/') }}</span>
        <span class="badge" :class="data.job.status === 'done' ? 'ok' : (data.job.status === 'failed' ? 'bad' : 'run')">{{ data.job.status }}</span>
      </div>
      <div>
        <button class="btn" :disabled="!scriptReady || producing" @click="produce">{{ producing ? '制作中…' : '🎥 开始制作全部' }}</button>
        <a v-if="hasFinal" :href="api.downloadUrl(jid)" style="margin-left:8px"><button class="btn green">⬇ 打包下载</button></a>
      </div>
    </div>

    <div class="tabs">
      <div class="tab" :class="{ active: tab === 'scripts' }" @click="tab = 'scripts'">📝 脚本审阅</div>
      <div class="tab" :class="{ active: tab === 'monitor' }" @click="tab = 'monitor'">🎞 生产监控</div>
      <div class="tab" :class="{ active: tab === 'finals' }" @click="tab = 'finals'">🎬 成片库</div>
    </div>

    <!-- 脚本审阅 -->
    <div v-if="tab === 'scripts'">
      <div v-if="!data.videos.length" class="card muted">脚本生成中…</div>
      <div class="card" v-for="v in data.videos" :key="v.id">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <div>
            <b>{{ v.platform }} · {{ langName(v.language) }} · 变体{{ v.variant }}</b>
            <span class="badge" :class="v.compliance?.pass ? 'ok' : 'bad'">
              {{ v.compliance ? (v.compliance.pass ? '合规✓' : `合规风险×${v.compliance.issues.length}`) : '未检' }}
            </span>
            <span class="badge info">{{ v.status }}</span>
          </div>
          <div>
            <button class="btn small gray" @click="regenScript(v)">🔄 重写脚本</button>
            <button class="btn small green" style="margin-left:6px" @click="saveScript(v)" :disabled="savingId === v.id">{{ savingId === v.id ? '保存中' : '💾 保存' }}</button>
          </div>
        </div>

        <template v-if="v.script">
          <div v-if="v.compliance && !v.compliance.pass" class="warn" style="margin:8px 0">
            <div v-for="(iss, i) in v.compliance.issues" :key="i">⚠ 「{{ iss.text }}」{{ iss.reason }} → 建议：{{ iss.suggestion }}</div>
          </div>
          <label>钩子 Hook</label>
          <input v-model="v.script.hook" />
          <div class="shot" v-for="(s, i) in v.script.shots" :key="i">
            <div style="margin-bottom:6px">
              <span class="tag" :class="s.type">{{ s.type }}</span>
              <span class="muted">镜头{{ i + 1 }} · {{ s.duration }}s</span>
            </div>
            <div class="row">
              <div><label>大字幕 overlay</label><input v-model="s.overlay_text" /></div>
              <div><label>口播台词 vo</label><input v-model="s.vo_line" /></div>
              <div style="max-width:80px"><label>时长</label><input type="number" v-model.number="s.duration" min="2" max="8" /></div>
            </div>
            <template v-if="s.type === 'scene'">
              <label>视频提示词（英文）</label>
              <textarea v-model="s.video_prompt" rows="2"></textarea>
            </template>
          </div>
          <div class="row">
            <div><label>CTA</label><input v-model="v.script.cta" /></div>
            <div><label>发布文案 caption</label><input v-model="v.script.caption" /></div>
          </div>
        </template>
        <div v-else class="muted">生成中…</div>
      </div>
    </div>

    <!-- 生产监控 -->
    <div v-if="tab === 'monitor'">
      <div class="grid">
        <div class="cell" v-for="v in data.videos" :key="v.id">
          <b>{{ v.platform }} · {{ langName(v.language) }} · v{{ v.variant }}</b>
          <div style="margin:6px 0">
            <span class="badge" :class="stCls(v.status, 'script')">脚本</span>
            <span class="badge" :class="stCls(v.status, 'scene')">图</span>
            <span class="badge" :class="stCls(v.status, 'clip')">视</span>
            <span class="badge" :class="stCls(v.status, 'voice')">音</span>
            <span class="badge" :class="v.status === 'done' ? 'ok' : (v.status === 'failed' ? 'bad' : 'info')">{{ v.status === 'done' ? '成片✓' : v.status }}</span>
          </div>
          <img v-for="img in sceneImgs(v)" :key="img" :src="img" style="width:48%;margin:2px" />
          <video v-if="v.final" :src="api.staticUrl(v.final) + '?t=' + ts" controls muted></video>
          <div v-if="v.status === 'failed'" style="margin-top:6px">
            <button class="btn small gray" @click="reproduce(v)">重做本条</button>
          </div>
        </div>
      </div>
      <div class="card" v-if="logs.length" style="margin-top:12px">
        <h2>实时日志</h2>
        <div v-for="(l, i) in logs.slice(-40)" :key="i" class="muted">{{ l }}</div>
      </div>
    </div>

    <!-- 成片库 -->
    <div v-if="tab === 'finals'">
      <div class="card muted" v-if="!finalVideos.length">暂无成片</div>
      <div class="grid">
        <div class="cell" v-for="v in finalVideos" :key="v.id">
          <b>{{ v.platform }} · {{ langName(v.language) }} · v{{ v.variant }}</b>
          <video :src="api.staticUrl(v.final) + '?t=' + ts" controls></video>
          <div style="margin-top:6px">
            <a :href="api.staticUrl(v.final)" download><button class="btn small">⬇ 下载</button></a>
          </div>
          <div class="muted" style="margin-top:6px">{{ v.script?.caption }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { api } from './api'

const props = defineProps({ jid: String })
const emit = defineEmits(['back'])

const data = ref(null)
const tab = ref('scripts')
const producing = ref(false)
const savingId = ref('')
const logs = ref([])
const ts = ref(0)
let ws = null, timer = null

const scriptReady = computed(() => data.value?.videos.every(v => v.script))
const hasFinal = computed(() => data.value?.videos.some(v => v.final))
const finalVideos = computed(() => (data.value?.videos || []).filter(v => v.final))

function langName(l) { return { en: '英语', ja: '日语', zh: '中文' }[l] || l }
function stCls(status, stage) {
  const order = ['pending', 'script_done', 'producing_scene', 'producing_clip', 'producing_voice', 'merging', 'done']
  const stageMap = { script: 1, scene: 2, clip: 3, voice: 4 }
  if (status === 'failed') return 'bad'
  if (status === 'done') return 'ok'
  const cur = order.indexOf(status)
  return cur >= stageMap[stage] ? 'ok' : cur === stageMap[stage] - 1 ? 'run' : 'info'
}
function sceneImgs(v) {
  if (!v.script) return []
  return v.script.shots.map((s, i) => s.type === 'scene' ? api.staticUrl(`jobs/${props.jid}/${v.id}/scene${i}.png`) + '?t=' + ts.value : null).filter(Boolean)
}

async function load() {
  data.value = await api.getJob(props.jid)
  producing.value = data.value.job.status === 'running'
}
async function saveScript(v) {
  savingId.value = v.id
  try { await api.saveScript(v.id, JSON.parse(JSON.stringify(v.script))) } catch (e) { alert(e.message) }
  savingId.value = ''
}
async function regenScript(v) { await api.regenScript(v.id) }
async function reproduce(v) { await api.reproduce(v.id) }
async function produce() {
  await api.produce(props.jid)
  producing.value = true
  tab.value = 'monitor'
}

function connectWs() {
  ws = new WebSocket(api.wsUrl(props.jid))
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data)
    const t = new Date().toLocaleTimeString()
    if (m.type === 'video') logs.value.push(`${t} [${m.video}] ${m.stage}: ${m.status}${m.shot !== undefined ? ' 镜头' + (m.shot + 1) : ''}${m.error ? ' ' + m.error.slice(0, 120) : ''}`)
    else if (m.type === 'stage') logs.value.push(`${t} 阶段 ${m.stage}: ${m.status}`)
    else if (m.type === 'job') { logs.value.push(`${t} 任务: ${m.status}`); producing.value = false }
    if (m.status === 'done') { ts.value = Date.now(); load() }
  }
  ws.onclose = () => setTimeout(connectWs, 3000)
}

onMounted(async () => { await load(); connectWs(); timer = setInterval(load, 15000) })
onUnmounted(() => { ws?.close(); clearInterval(timer) })
</script>
