<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { ArrowLeft, Calendar, Clock, Filter, Location, Medal, Refresh, Search, Trophy } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api, { errorMessage } from '../api'

const router = useRouter()
const loading = ref(false)
const latest = ref<any[]>([])
const results = ref<any[]>([])
const schedules = ref<any[]>([])
const rankings = ref<any[]>([])
const meets = ref<any[]>([])
const selectedMeetId = ref<number | null>(null)
const basketballData = ref<any>(null)
const volleyballData = ref<any>(null)
const tableTennisData = ref<any>(null)
const activeTtEventId = ref<number | null>(null)
const activeEvent = ref<number | null>(null)
const lastUpdated = ref<Date | null>(null)
const chartEl = ref<HTMLElement>()
let chart: echarts.ECharts | null = null
let pollTimer: number | undefined
const filters = reactive({ gender: '', stage: '', college: '' })
const settings = reactive({ results_page_name: '赛事成绩中心', short_name: '校园运动会赛事成绩管理系统', logo_text: '跃', footer: '校园运动会赛事组委会 · 数据以终审发布为准' })
const stageLabel: Record<string,string> = { HEAT: '初赛', SEMIFINAL: '晋级赛', FINAL: '决赛' }
const competitionStatusLabel: Record<string,string> = { NORMAL: '正常完赛', DNS: '未出赛', DNF: '未完赛', DQ: '取消资格', NM: '无有效成绩' }

const displayedResults = computed(() => activeEvent.value ? results.value.filter(item => item.event_id === activeEvent.value) : results.value)
const eventName = computed(() => displayedResults.value[0]?.event_name || '全部已发布成绩')
const basketballPlayoffMatches = computed(() => {
  if (!basketballData.value?.matches) return []
  return basketballData.value.matches.filter((m: any) => ['SEMIFINAL', 'THIRD_PLACE', 'FINAL'].includes(m.stage_type))
})
const volleyballPlayoffMatches = computed(() => {
  if (!volleyballData.value?.matches) return []
  return volleyballData.value.matches.filter((m: any) => ['SEMIFINAL', 'THIRD_PLACE', 'FINAL'].includes(m.stage_type))
})
const currentTtEvent = computed(() => {
  if (!tableTennisData.value?.available_events) return null
  return tableTennisData.value.available_events.find((e: any) => e.id === activeTtEventId.value) || tableTennisData.value.available_events[0]
})
const currentTtMatches = computed(() => {
  if (!tableTennisData.value?.matches || !currentTtEvent.value) return []
  return tableTennisData.value.matches.filter((m: any) => m.event_id === currentTtEvent.value.id)
})
const currentTtStandings = computed(() => {
  if (!tableTennisData.value?.standings_by_event || !currentTtEvent.value) return { group_a: [], group_b: [] }
  return tableTennisData.value.standings_by_event[String(currentTtEvent.value.id)] || { group_a: [], group_b: [] }
})
const currentTtPlayoffMatches = computed(() => {
  return currentTtMatches.value.filter((m: any) => ['SEMIFINAL', 'THIRD_PLACE', 'FINAL'].includes(m.stage_type))
})

function formatDate(value: string) {
  if (!value) return '待定'
  return new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}
function formatTime(value: string) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(new Date(value))
}
function formatScore(row: any) {
  const detail = row.rope_detail
  if (!detail) return `${row.raw_value ?? '—'} ${row.unit || ''}`
  if (row.event_code === 'ROPE_SYNC') {
    return detail.completed_target ? `完成30次 · ${detail.elapsed_seconds} 秒` : `未完成 · ${detail.completed_count} 次`
  }
  return `${detail.completed_count ?? row.raw_value} 次`
}

async function loadData(silent = false) {
  if (!silent) loading.value = true
  try {
    const [settingRes, meetRes] = await Promise.all([api.get('/public/settings'), api.get('/public/meets')])
    Object.assign(settings, settingRes.data)
    meets.value = meetRes.data
    const queryMeetId = Number(router.currentRoute.value.query?.meet_id)
    if (queryMeetId && meets.value.some(meet => meet.id === queryMeetId)) {
      selectedMeetId.value = queryMeetId
    } else if (!selectedMeetId.value || !meets.value.some(meet => meet.id === selectedMeetId.value)) {
      selectedMeetId.value = meets.value[0]?.id || null
    }
    if (!selectedMeetId.value) {
      latest.value = []
      results.value = []
      schedules.value = []
      rankings.value = []
      basketballData.value = null
      volleyballData.value = null
      tableTennisData.value = null
      return
    }
    const meetParams = { meet_id: selectedMeetId.value }
    const params = { ...Object.fromEntries(Object.entries(filters).filter(([, value]) => value)), ...meetParams }
    const [latestRes, resultRes, scheduleRes, rankRes, bballRes, vballRes, ttRes] = await Promise.all([
      api.get('/public/latest-results', { params: meetParams }), api.get('/public/results', { params }), api.get('/public/schedules', { params: meetParams }), api.get('/public/college-rankings', { params: meetParams }),
      api.get('/public/basketball', { params: meetParams }).catch(() => ({ data: { has_tournament: false } })),
      api.get('/public/volleyball', { params: meetParams }).catch(() => ({ data: { has_tournament: false } })),
      api.get('/public/table-tennis', { params: meetParams }).catch(() => ({ data: { has_tournament: false } }))
    ])
    latest.value = latestRes.data
    results.value = resultRes.data
    schedules.value = scheduleRes.data
    rankings.value = rankRes.data
    basketballData.value = bballRes.data?.has_tournament ? bballRes.data : null
    volleyballData.value = vballRes.data?.has_tournament ? vballRes.data : null
    tableTennisData.value = ttRes.data?.has_tournament ? ttRes.data : null
    if (tableTennisData.value?.available_events?.length && !activeTtEventId.value) {
      activeTtEventId.value = tableTennisData.value.available_events[0].id
    }
    lastUpdated.value = new Date()
    await nextTick()
    renderChart()
  } catch (error) {
    if (!silent) ElMessage.error(errorMessage(error))
  } finally { loading.value = false }
}

function renderChart() {
  if (!chartEl.value) return
  chart ||= echarts.init(chartEl.value)
  chart.setOption({
    grid: { left: 12, right: 20, top: 16, bottom: 10, containLabel: true },
    xAxis: { type: 'value', splitLine: { lineStyle: { color: '#f1f5f9' } }, axisLabel: { color: '#64748b' } },
    yAxis: { type: 'category', inverse: true, data: rankings.value.slice(0, 6).map(item => item.college), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: '#0f172a', width: 100, overflow: 'truncate' } },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    series: [{ type: 'bar', data: rankings.value.slice(0, 6).map(item => Number(item.points)), barWidth: 14, itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [{ offset: 0, color: '#2563eb' }, { offset: 1, color: '#60a5fa' }]), borderRadius: [0, 6, 6, 0] }, label: { show: true, position: 'right', color: '#10b981', fontWeight: 700 } }],
  })
}
function chooseEvent(id: number) { activeEvent.value = id; document.querySelector('.full-table')?.scrollIntoView({ behavior: 'smooth' }) }
function resetFilters() { Object.assign(filters, { gender: '', stage: '', college: '' }); activeEvent.value = null; loadData() }
function changeMeet() { activeEvent.value = null; activeTtEventId.value = null; loadData() }

onMounted(() => {
  loadData()
  pollTimer = window.setInterval(() => loadData(true), 30000)
  window.addEventListener('resize', () => chart?.resize())
})
onBeforeUnmount(() => { if (pollTimer) clearInterval(pollTimer); chart?.dispose() })
</script>

<template>
  <main class="results-page" v-loading="loading">
    <!-- 实时成绩顶栏 -->
    <header class="topbar">
      <div class="public-brand">
        <div class="brand-mark">{{ settings.logo_text }}</div>
        <div><b>{{ settings.short_name }}</b><span>RESULTS CENTER</span></div>
      </div>
      <el-select v-model="selectedMeetId" class="public-meet-select" placeholder="选择运动会" @change="changeMeet">
        <el-option v-for="meet in meets" :key="meet.id" :label="`${meet.name}（${meet.edition}）`" :value="meet.id"/>
      </el-select>
      <nav><a href="#latest">最新发布</a><a href="#ranking">团体总分</a><a href="#schedule">赛程安排</a></nav>
      <button class="login-link" @click="router.push('/login')"><el-icon><ArrowLeft /></el-icon> 返回登录</button>
    </header>

    <!-- 实时成绩主视图 -->
    <section class="hero">
      <div class="hero-aurora"></div>
      <div class="hero-content">
        <span class="live-badge"><i class="live-pulse-dot"></i> RESULTS LIVE</span>
        <h1 class="hero-art-title">{{ settings.results_page_name }}</h1>
        <p>每一份成绩均经项目裁判登记、复核与体育部终审后秒级发布</p>
        <div class="update-line">
          <el-icon><Refresh /></el-icon> 实时同步时间 {{ lastUpdated ? formatTime(lastUpdated.toISOString()) : '正在连接' }} · 每 30 秒自动刷新
        </div>
      </div>
      
      <!-- 右侧 3D 悬浮荣誉金牌勋章卡片 -->
      <div class="hero-medal-card">
        <div class="medal-gold-ring">🏆</div>
        <div>
          <span>OFFICIAL VERIFIED</span>
          <strong>荣耀见证 · 公平竞技</strong>
        </div>
      </div>
    </section>

    <div class="content-wrap">
      <!-- 1. 最新发布成绩卡片网格 -->
      <section id="latest" class="section-block">
        <div class="section-header">
          <div><span class="eyebrow">LATEST RELEASES</span><h2>最新发布成绩</h2><p>按赛事终审发布时间秒级更新</p></div>
          <el-button class="refresh-btn" :icon="Refresh" circle @click="loadData()" />
        </div>
        <div class="latest-grid" v-if="latest.length">
          <article v-for="card in latest" :key="`${card.event_id}-${card.round_id}`" class="result-card panel" @click="chooseEvent(card.event_id)">
            <div class="card-top">
              <span class="event-tag">{{ card.gender_group === 'MALE' ? '男子组' : card.gender_group === 'FEMALE' ? '女子组' : '混合组' }} · {{ card.round_name || stageLabel[card.stage] || card.stage }}</span>
              <time>{{ formatDate(card.published_at) }}</time>
            </div>
            <h3>{{ card.event_name }}</h3>
            <!-- 精美 Podiums 前三名领奖台 -->
            <div class="podium-list">
              <div v-for="person in card.top_three" :key="person.id" :class="['podium-row', `rank-${person.rank}`]">
                <span :class="['rank-badge', `rank-${person.rank}`]">
                  {{ person.rank === 1 ? '🥇 1' : person.rank === 2 ? '🥈 2' : person.rank === 3 ? '🥉 3' : person.rank }}
                </span>
                <div class="person-meta">
                  <strong>{{ person.name }}</strong>
                  <small>{{ person.college }}</small>
                </div>
                <b class="score-number">{{ formatScore(person) }}</b>
              </div>
            </div>
            <button class="card-action">查看完整成绩单 <span class="arrow">→</span></button>
          </article>
        </div>
        <div v-else class="empty-state panel">暂无已终审发布的成绩数据</div>
      </section>

      <!-- 1.5 🏀 篮球联赛专属专区 (A/B组循环赛积分榜 · 胜2分负1分 & 争夺前四名) -->
      <section v-if="basketballData" class="section-block" style="margin-top:28px">
        <div class="section-header">
          <div>
            <span class="eyebrow">BASKETBALL TOURNAMENT</span>
            <h2>🏀 {{ basketballData.event_name }} · 国家体委审定两阶段赛制</h2>
            <p>第一阶段 A/B 组单循环积分榜（胜积2分 · 负积1分 · 弃权0分）与第二阶段交叉决赛</p>
          </div>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px">
          <!-- A 组积分榜 -->
          <div class="panel" style="padding:18px">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
              <strong style="color:var(--apple-blue);font-size:15px">🔵 A 组单循环积分榜</strong>
              <span style="font-size:12px;color:#8e8e93">前 2 名晋级半决赛</span>
            </div>
            <div class="ranking-table">
              <div v-for="item in basketballData.standings.group_a" :key="item.team_id" class="ranking-row">
                <span :class="['rank-badge', `rank-${item.rank}`]">{{ item.rank <= 2 ? '⭐ ' + item.rank : item.rank }}</span>
                <strong class="college-name">{{ item.college }}</strong>
                <span style="font-size:12px;color:#666;margin:0 10px">{{ item.won }}胜 {{ item.lost }}负</span>
                <b class="score-number" style="color:var(--apple-blue)">{{ item.points }} 分</b>
              </div>
            </div>
          </div>

          <!-- B 组积分榜 -->
          <div class="panel" style="padding:18px">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
              <strong style="color:var(--apple-orange);font-size:15px">🟠 B 组单循环积分榜</strong>
              <span style="font-size:12px;color:#8e8e93">前 2 名晋级半决赛</span>
            </div>
            <div class="ranking-table">
              <div v-for="item in basketballData.standings.group_b" :key="item.team_id" class="ranking-row">
                <span :class="['rank-badge', `rank-${item.rank}`]">{{ item.rank <= 2 ? '⭐ ' + item.rank : item.rank }}</span>
                <strong class="college-name">{{ item.college }}</strong>
                <span style="font-size:12px;color:#666;margin:0 10px">{{ item.won }}胜 {{ item.lost }}负</span>
                <b class="score-number" style="color:var(--apple-orange)">{{ item.points }} 分</b>
              </div>
            </div>
          </div>
        </div>

        <!-- 淘汰决赛对阵比分 -->
        <div v-if="basketballPlayoffMatches.length" class="panel" style="padding:18px">
          <div style="margin-bottom:12px"><strong style="font-size:15px">🏆 第二阶段：争夺前四名决胜赛况</strong></div>
          <div style="display:grid;grid-template-columns:repeat(4, 1fr);gap:14px">
            <div v-for="m in basketballPlayoffMatches" :key="m.id" style="background:#fcfcfd;border:1px solid rgba(0,0,0,0.06);border-radius:10px;padding:12px">
              <div style="font-size:11px;font-weight:700;color:var(--apple-blue);margin-bottom:6px">{{ m.match_name }}</div>
              <div style="display:flex;justify-content:space-between;align-items:center;padding:3px 6px;border-radius:4px" :style="m.winner_team_id===m.home_team_id?'background:rgba(52,199,89,0.15);font-weight:700':''">
                <span>{{ m.home_college }}</span>
                <b style="font-family:var(--font-mono)">{{ m.home_score !== null ? m.home_score : '—' }}</b>
              </div>
              <div style="display:flex;justify-content:space-between;align-items:center;padding:3px 6px;border-radius:4px" :style="m.winner_team_id===m.away_team_id?'background:rgba(52,199,89,0.15);font-weight:700':''">
                <span>{{ m.away_college }}</span>
                <b style="font-family:var(--font-mono)">{{ m.away_score !== null ? m.away_score : '—' }}</b>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 1.6 🏐 排球联赛专属大屏专区 (A/B组循环赛4/2/1/0积分榜 · 三局两胜25分制 & 女生≥2人 & 交叉决赛争夺前四名) -->
      <section v-if="volleyballData" class="section-block" style="margin-top:28px">
        <div class="section-header">
          <div>
            <span class="eyebrow">VOLLEYBALL TOURNAMENT</span>
            <h2>🏐 {{ volleyballData.event_name }} · 国家体委审定两阶段赛制</h2>
            <p>第一阶段 A/B 组单循环积分榜（胜4分 · 负(1:2)2分 · 负(0:2)1分 · 弃权0分）与第二阶段交叉决赛（争夺全国前四名）</p>
          </div>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px">
          <!-- A 组排球积分榜 -->
          <div class="panel" style="padding:18px">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
              <strong style="color:var(--apple-blue);font-size:15px">🔵 A 组单循环积分榜 (胜4分/1:2负2分/0:2负1分)</strong>
              <span style="font-size:12px;color:#8e8e93">前 2 名晋级半决赛</span>
            </div>
            <div class="ranking-table">
              <div v-for="item in volleyballData.standings.group_a" :key="item.team_id" class="ranking-row">
                <span :class="['rank-badge', `rank-${item.rank}`]">{{ item.rank <= 2 ? '⭐ ' + item.rank : item.rank }}</span>
                <strong class="college-name">{{ item.college }}</strong>
                <span style="font-size:11px;color:#666;margin:0 6px">{{ item.won }}胜{{ item.lost }}负 | C值:{{ item.set_ratio }}</span>
                <b class="score-number" style="color:var(--apple-purple)">{{ item.points }} 分</b>
              </div>
            </div>
          </div>

          <!-- B 组排球积分榜 -->
          <div class="panel" style="padding:18px">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
              <strong style="color:var(--apple-orange);font-size:15px">🟠 B 组单循环积分榜 (胜4分/1:2负2分/0:2负1分)</strong>
              <span style="font-size:12px;color:#8e8e93">前 2 名晋级半决赛</span>
            </div>
            <div class="ranking-table">
              <div v-for="item in volleyballData.standings.group_b" :key="item.team_id" class="ranking-row">
                <span :class="['rank-badge', `rank-${item.rank}`]">{{ item.rank <= 2 ? '⭐ ' + item.rank : item.rank }}</span>
                <strong class="college-name">{{ item.college }}</strong>
                <span style="font-size:11px;color:#666;margin:0 6px">{{ item.won }}胜{{ item.lost }}负 | C值:{{ item.set_ratio }}</span>
                <b class="score-number" style="color:var(--apple-purple)">{{ item.points }} 分</b>
              </div>
            </div>
          </div>
        </div>

        <!-- 排球淘汰决赛对阵比分 -->
        <div v-if="volleyballPlayoffMatches.length" class="panel" style="padding:18px">
          <div style="margin-bottom:12px"><strong style="font-size:15px">🏆 第二阶段：排球交叉淘汰决胜赛况 (争夺前四名)</strong></div>
          <div style="display:grid;grid-template-columns:repeat(4, 1fr);gap:14px">
            <div v-for="m in volleyballPlayoffMatches" :key="m.id" style="background:#fcfcfd;border:1px solid rgba(0,0,0,0.06);border-radius:10px;padding:12px">
              <div style="font-size:11px;font-weight:700;color:var(--apple-purple);margin-bottom:6px">{{ m.match_name }}</div>
              <div style="display:flex;justify-content:space-between;align-items:center;padding:3px 6px;border-radius:4px" :style="m.winner_team_id===m.home_team_id?'background:rgba(52,199,89,0.15);font-weight:700':''">
                <span>{{ m.home_college }}</span>
                <b style="font-family:var(--font-mono)">{{ m.home_score !== null ? `${m.home_score}局` : '—' }}</b>
              </div>
              <div style="display:flex;justify-content:space-between;align-items:center;padding:3px 6px;border-radius:4px" :style="m.winner_team_id===m.away_team_id?'background:rgba(52,199,89,0.15);font-weight:700':''">
                <span>{{ m.away_college }}</span>
                <b style="font-family:var(--font-mono)">{{ m.away_score !== null ? `${m.away_score}局` : '—' }}</b>
              </div>
              <div v-if="m.sets_summary" style="font-size:10px;color:#8e8e93;margin-top:4px">
                局分: {{ m.sets_summary }}
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 1.7 🏓 乒乓球赛事实时大屏专区 (混合团体5盘打满·胜2负1弃权0分 & 男/女单打前3局后5局动态切换) -->
      <section v-if="tableTennisData" class="section-block" style="margin-top:28px">
        <div class="section-header" style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:14px">
          <div>
            <span class="eyebrow">TABLE TENNIS TOURNAMENT</span>
            <h2>🏓 {{ currentTtEvent?.name || '乒乓球赛事' }} · 国家体委最新规程</h2>
            <p>混合团体赛（3男2女/打满5场/积分2-1-0/最好第二晋级）· 男/女单打（种子回避/前3局后5局动态切换）</p>
          </div>
          <!-- 切换乒乓球子项目 (混合团体 / 男单 / 女单) -->
          <div v-if="tableTennisData.available_events?.length > 1" style="display:flex;gap:8px">
            <button
              v-for="ev in tableTennisData.available_events"
              :key="ev.id"
              :class="['filter-chip', { active: activeTtEventId === ev.id }]"
              @click="activeTtEventId = ev.id"
              style="padding:6px 14px;border-radius:20px;border:1px solid rgba(0,0,0,0.1);cursor:pointer;font-weight:600;font-size:13px"
              :style="activeTtEventId === ev.id ? 'background:#007aff;color:#fff;border-color:#007aff' : 'background:#fff;color:#1c1c1e'"
            >
              {{ ev.name }}
            </button>
          </div>
        </div>

        <!-- A. 混合团体赛展示 -->
        <template v-if="currentTtEvent?.event_type === 'TEAM'">
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px">
            <!-- A 组积分榜 -->
            <div class="panel" style="padding:18px">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
                <strong style="color:var(--apple-blue);font-size:15px">🔵 A 组单循环积分榜 (胜2分·负1分·打满5场)</strong>
                <span style="font-size:12px;color:#8e8e93">第1名+成绩最好第2名出线</span>
              </div>
              <div class="ranking-table">
                <div v-for="item in currentTtStandings.group_a" :key="item.team_id" class="ranking-row">
                  <span :class="['rank-badge', `rank-${item.rank}`]">{{ item.rank === 1 ? '⭐ 1' : item.rank }}</span>
                  <strong class="college-name">{{ item.college }}</strong>
                  <span style="font-size:11px;color:#666;margin:0 6px">{{ item.won }}胜{{ item.lost }}负 | 净胜盘:{{ item.rubber_diff }} | 局比:{{ item.set_ratio }}</span>
                  <b class="score-number" style="color:var(--apple-blue)">{{ item.points }} 分</b>
                </div>
              </div>
            </div>

            <!-- B 组积分榜 -->
            <div class="panel" style="padding:18px">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
                <strong style="color:var(--apple-orange);font-size:15px">🟠 B 组单循环积分榜 (胜2分·负1分·打满5场)</strong>
                <span style="font-size:12px;color:#8e8e93">第1名+成绩最好第2名出线</span>
              </div>
              <div class="ranking-table">
                <div v-for="item in currentTtStandings.group_b" :key="item.team_id" class="ranking-row">
                  <span :class="['rank-badge', `rank-${item.rank}`]">{{ item.rank === 1 ? '⭐ 1' : item.rank }}</span>
                  <strong class="college-name">{{ item.college }}</strong>
                  <span style="font-size:11px;color:#666;margin:0 6px">{{ item.won }}胜{{ item.lost }}负 | 净胜盘:{{ item.rubber_diff }} | 局比:{{ item.set_ratio }}</span>
                  <b class="score-number" style="color:var(--apple-orange)">{{ item.points }} 分</b>
                </div>
              </div>
            </div>
          </div>

          <!-- 混合团体淘汰决胜赛况 -->
          <div v-if="currentTtPlayoffMatches.length" class="panel" style="padding:18px">
            <div style="margin-bottom:12px"><strong style="font-size:15px">🏆 第二阶段：混合团体交叉半决赛与总决赛 (打满5场争夺前四名)</strong></div>
            <div style="display:grid;grid-template-columns:repeat(4, 1fr);gap:14px">
              <div v-for="m in currentTtPlayoffMatches" :key="m.id" style="background:#fcfcfd;border:1px solid rgba(0,0,0,0.06);border-radius:10px;padding:12px">
                <div style="font-size:11px;font-weight:700;color:var(--apple-blue);margin-bottom:6px">{{ m.match_name }}</div>
                <div style="display:flex;justify-content:space-between;align-items:center;padding:3px 6px;border-radius:4px" :style="m.winner_team_id===m.home_team_id?'background:rgba(52,199,89,0.15);font-weight:700':''">
                  <span>{{ m.home_college }}</span>
                  <b style="font-family:var(--font-mono)">{{ m.home_score !== null ? `${m.home_score}盘` : '—' }}</b>
                </div>
                <div style="display:flex;justify-content:space-between;align-items:center;padding:3px 6px;border-radius:4px" :style="m.winner_team_id===m.away_team_id?'background:rgba(52,199,89,0.15);font-weight:700':''">
                  <span>{{ m.away_college }}</span>
                  <b style="font-family:var(--font-mono)">{{ m.away_score !== null ? `${m.away_score}盘` : '—' }}</b>
                </div>
                <div v-if="m.sets_summary" style="font-size:10px;color:#8e8e93;margin-top:4px">
                  盘分明细: {{ m.sets_summary }}
                </div>
              </div>
            </div>
          </div>
        </template>

        <!-- B. 单打比赛展示 (男单 / 女单) -->
        <template v-else>
          <div class="panel" style="padding:18px">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
              <strong style="font-size:15px">🏆 单打淘汰赛实时对阵（前期三局两胜 · 进入八强五局三胜制）</strong>
              <el-tag size="small" type="success">11分制 · 领先2分获胜</el-tag>
            </div>
            <div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(260px, 1fr));gap:12px">
              <div v-for="m in currentTtMatches" :key="m.id" style="background:#fcfcfd;border:1px solid rgba(0,0,0,0.06);border-radius:10px;padding:12px">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                  <span style="font-size:11px;font-weight:700;color:var(--apple-blue)">{{ m.match_name }}</span>
                  <el-tag size="small" :type="m.best_of===5?'danger':'primary'">{{ m.best_of===5?'5局3胜':'3局2胜' }}</el-tag>
                </div>
                <div style="display:flex;justify-content:space-between;align-items:center;padding:3px 6px;border-radius:4px" :style="m.winner_student_id===m.home_student_id?'background:rgba(52,199,89,0.15);font-weight:700':''">
                  <span>{{ m.home_student_name }} <small style="color:#8e8e93">({{ m.home_college }})</small></span>
                  <b style="font-family:var(--font-mono)">{{ m.home_score !== null ? `${m.home_score}局` : '—' }}</b>
                </div>
                <div style="display:flex;justify-content:space-between;align-items:center;padding:3px 6px;border-radius:4px" :style="m.winner_student_id===m.away_student_id?'background:rgba(52,199,89,0.15);font-weight:700':''">
                  <span>{{ m.away_student_name }} <small style="color:#8e8e93">({{ m.away_college }})</small></span>
                  <b style="font-family:var(--font-mono)">{{ m.away_score !== null ? `${m.away_score}局` : '—' }}</b>
                </div>
                <div v-if="m.sets_summary" style="font-size:10px;color:#8e8e93;margin-top:4px">
                  局分: {{ m.sets_summary }}
                </div>
              </div>
            </div>
          </div>
        </template>
      </section>

      <!-- 2. 学院团体总分榜 -->
      <section id="ranking" class="ranking-layout">
        <div class="panel ranking-panel">
          <div class="panel-heading">
            <div><span class="eyebrow">TEAM STANDINGS</span><h2>学院团体总分榜</h2></div>
            <el-icon class="head-icon"><Trophy /></el-icon>
          </div>
          <div class="ranking-table">
            <div v-for="item in rankings" :key="item.college" :class="['ranking-row', { 'top-three': item.rank <= 3 }]">
              <span :class="['rank-badge', `rank-${item.rank}`]">{{ item.rank <= 3 ? (item.rank === 1 ? '🥇 1' : item.rank === 2 ? '🥈 2' : '🥉 3') : item.rank }}</span>
              <strong class="college-name">{{ item.college }}</strong>
              <div class="medals-count">
                <span v-if="item.gold">🥇 {{ item.gold }}</span>
                <span v-if="item.silver">🥈 {{ item.silver }}</span>
                <span v-if="item.bronze">🥉 {{ item.bronze }}</span>
              </div>
              <b class="score-number total-points">{{ item.points }} 分</b>
            </div>
          </div>
        </div>
        <div class="panel chart-panel">
          <div class="panel-heading">
            <div><span class="eyebrow">POINTS OVERVIEW</span><h2>积分对比数据</h2></div>
            <el-icon class="head-icon"><Medal /></el-icon>
          </div>
          <div ref="chartEl" class="chart"></div>
        </div>
      </section>

      <!-- 3. 已发布赛程 -->
      <section id="schedule" class="section-block">
        <div class="section-header">
          <div><span class="eyebrow">UPCOMING EVENTS</span><h2>官方发布赛程</h2><p>请参赛运动员按检录时间提前到达比赛场地</p></div>
        </div>
        <div class="schedule-strip">
          <article v-for="item in schedules" :key="item.id" class="schedule-card panel">
            <div class="date-box">
              <b>{{ new Date(item.competition_at).getDate() }}</b>
              <span>{{ new Date(item.competition_at).getMonth() + 1 }}月</span>
            </div>
            <div class="schedule-info">
              <strong>{{ item.event_name }} · {{ item.round_name }}</strong>
              <p><el-icon><Clock /></el-icon> 比赛：{{ formatDate(item.competition_at) }} · 检录：{{ formatDate(item.check_in_at) }}</p>
              <p><el-icon><Location /></el-icon> {{ item.venue }} · {{ item.heat }}</p>
            </div>
            <span class="schedule-status-chip"><i></i>{{ item.status === 'NOT_STARTED' ? '未开始' : item.status }}</span>
          </article>
        </div>
      </section>

      <!-- 4. 全量成绩查询表格 -->
      <section class="full-table panel">
        <div class="table-toolbar">
          <div><span class="eyebrow">OFFICIAL RESULTS</span><h2>{{ eventName }}</h2></div>
          <div class="filters">
            <el-select v-model="filters.gender" placeholder="全部组别" clearable style="width:120px"><el-option label="男子组" value="MALE"/><el-option label="女子组" value="FEMALE"/><el-option label="混合组" value="MIXED"/></el-select>
            <el-select v-model="filters.stage" placeholder="全部轮次" clearable style="width:120px"><el-option label="初赛" value="HEAT"/><el-option label="晋级赛" value="SEMIFINAL"/><el-option label="决赛" value="FINAL"/></el-select>
            <el-input v-model="filters.college" placeholder="按学院查询" :prefix-icon="Search" clearable style="width:160px"/>
            <el-button type="primary" :icon="Filter" @click="loadData()">筛选</el-button>
            <el-button @click="resetFilters">重置</el-button>
          </div>
        </div>
        <el-table :data="displayedResults" stripe size="large" empty-text="暂无符合条件的已发布成绩">
          <el-table-column label="名次" width="90">
            <template #default="scope">
              <span :class="['rank-badge', `rank-${scope.row.rank}`]">{{ scope.row.rank || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="event_name" label="比赛项目" min-width="160"/>
          <el-table-column label="轮次" width="100"><template #default="scope">{{ scope.row.round_name || stageLabel[scope.row.stage] || scope.row.stage }}</template></el-table-column>
          <el-table-column prop="name" label="姓名/代表队" width="140"/>
          <el-table-column prop="student_no" label="学号" width="140"/>
          <el-table-column prop="college" label="所属学院" min-width="160"/>
          <el-table-column label="成绩" min-width="140">
            <template #default="scope">
              <b class="score-number" style="font-size:15px;color:#0f172a">
                {{ formatScore(scope.row) }}
              </b>
            </template>
          </el-table-column>
          <el-table-column label="比赛状态" width="110"><template #default="scope">{{ competitionStatusLabel[scope.row.competition_status] || scope.row.competition_status }}</template></el-table-column>
          <el-table-column label="积分" width="90"><template #default="scope"><b>{{ scope.row.points }}</b></template></el-table-column>
          <el-table-column label="发布时间" width="160"><template #default="scope">{{ formatDate(scope.row.published_at) }}</template></el-table-column>
        </el-table>
      </section>
    </div>

    <!-- 页脚 -->
    <footer class="public-footer">
      <div class="public-brand">
        <div class="brand-mark">{{ settings.logo_text }}</div>
        <div><b>{{ settings.short_name }}</b><span>RESULTS CENTER</span></div>
      </div>
      <p>{{ settings.footer }}</p>
    </footer>
  </main>
</template>

<style scoped>
.results-page {
  min-height: 100vh;
  background: var(--bg-page);
  color: var(--ink-primary);
}

/* 顶部导航栏 Topbar */
.topbar {
  height: 70px;
  padding: 0 max(24px, calc((100vw - 1240px) / 2));
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  position: sticky;
  top: 0;
  z-index: 50;
}

.public-brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-mark {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #007aff, #0051a8);
  color: #ffffff;
  font-size: 22px;
  font-weight: 900;
  box-shadow: 0 4px 12px rgba(0, 122, 255, 0.3);
}

.public-brand > div:last-child {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.public-brand b {
  font-size: 15px;
  font-weight: 800;
  letter-spacing: -0.01em;
}

.public-brand span {
  font-size: 10px;
  letter-spacing: 0.2em;
  color: #8e8e93;
  font-weight: 700;
}

.topbar nav {
  display: flex;
  gap: 36px;
  font-size: 14px;
  font-weight: 600;
  color: #8e8e93;
}

.public-meet-select {
  width: min(300px, 24vw);
}

.topbar nav a {
  transition: color 0.2s ease;
}

.topbar nav a:hover {
  color: #007aff;
}

.login-link {
  border: 1px solid rgba(0, 122, 255, 0.3);
  background: rgba(0, 122, 255, 0.08);
  color: #007aff;
  padding: 8px 18px;
  border-radius: 9999px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  font-size: 13px;
  transition: all 0.2s ease;
}

.login-link:hover {
  background: rgba(0, 122, 255, 0.15);
  transform: translateY(-1px);
}

/* 主视图背景 */
.hero {
  min-height: 320px;
  position: relative;
  overflow: hidden;
  color: #ffffff;
  background: radial-gradient(circle at 75% 20%, #1e1b4b 0%, #0f172a 60%, #090d16 100%);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 40px max(24px, calc((100vw - 1240px) / 2));
}

.hero-aurora {
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at 20% 50%, rgba(56, 189, 248, 0.15), transparent 50%),
              radial-gradient(circle at 80% 80%, rgba(245, 158, 11, 0.12), transparent 50%);
  pointer-events: none;
}

.hero-content {
  position: relative;
  z-index: 2;
  max-width: 650px;
}

.live-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.1em;
  color: #34d399;
  background: rgba(52, 211, 153, 0.12);
  padding: 5px 14px;
  border-radius: 9999px;
  border: 1px solid rgba(52, 211, 153, 0.25);
  margin-bottom: 16px;
}

.live-pulse-dot {
  width: 7px;
  height: 7px;
  background: #34d399;
  border-radius: 50%;
  box-shadow: 0 0 10px #34d399;
  animation: pulse-live 1.5s ease-in-out infinite;
}

@keyframes pulse-live {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.5); opacity: 0.4; }
}

.hero-art-title {
  margin: 0;
  font-size: clamp(32px, 3.6vw, 48px);
  font-weight: 900;
  letter-spacing: -0.02em;
  background: linear-gradient(135deg, #ffffff 0%, #fbbf24 60%, #ffffff 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.hero-content p {
  margin: 12px 0 0;
  font-size: 1rem;
  color: #94a3b8;
  line-height: 1.6;
}

.update-line {
  margin-top: 20px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #64748b;
}

/* 右侧 3D 荣誉金牌勋章 */
.hero-medal-card {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 24px;
  background: rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 22px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
  animation: float-medal 6s ease-in-out infinite alternate;
}

@keyframes float-medal {
  0% { transform: translateY(0); }
  100% { transform: translateY(-10px); }
}

.medal-gold-ring {
  width: 52px;
  height: 52px;
  border-radius: 16px;
  background: linear-gradient(135deg, #f59e0b, #d97706);
  color: #ffffff;
  display: grid;
  place-items: center;
  font-size: 26px;
  box-shadow: 0 0 25px rgba(245, 158, 11, 0.4);
}

.hero-medal-card span {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: #fbbf24;
}

.hero-medal-card strong {
  display: block;
  font-size: 15px;
  font-weight: 700;
  color: #ffffff;
  margin-top: 2px;
}

/* 主内容容器 */
.content-wrap {
  max-width: 1280px;
  margin: 0 auto;
  padding: 36px 24px 60px;
}

.section-block {
  margin-bottom: 44px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.section-header h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 800;
  color: #0f172a;
}

.section-header p {
  margin: 4px 0 0;
  font-size: 13px;
  color: #64748b;
}

.refresh-btn {
  background: #ffffff !important;
  border-color: #e2e8f0 !important;
  color: #64748b !important;
}

.refresh-btn:hover {
  color: #2563eb !important;
  border-color: #bfdbfe !important;
}

/* 1. 最新发布成绩 Grid */
.latest-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

.result-card {
  padding: 22px;
  background: #ffffff;
  border-radius: 18px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.03);
  display: flex;
  flex-direction: column;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.result-card:hover {
  transform: translateY(-4px);
  border-color: #bfdbfe;
  box-shadow: 0 12px 32px rgba(37, 99, 235, 0.08);
}

.card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.event-tag {
  font-size: 11px;
  font-weight: 700;
  color: #2563eb;
  background: #eff6ff;
  padding: 4px 10px;
  border-radius: 9999px;
}

.card-top time {
  font-size: 12px;
  color: #94a3b8;
}

.result-card h3 {
  margin: 0 0 16px;
  font-size: 18px;
  font-weight: 800;
  color: #0f172a;
}

/* Podiums 榜单列表 */
.podium-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 18px;
}

.podium-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 12px;
  background: #f8fafc;
  border: 1px solid #f1f5f9;
}

/* 金银铜高光 Podiums */
.podium-row.rank-1 {
  background: linear-gradient(135deg, #fffbeb, #fef3c7);
  border-color: #fde68a;
}

.podium-row.rank-2 {
  background: linear-gradient(135deg, #f8fafc, #f1f5f9);
  border-color: #e2e8f0;
}

.podium-row.rank-3 {
  background: linear-gradient(135deg, #fff7ed, #ffedd5);
  border-color: #fed7aa;
}

.rank-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 800;
  background: #e2e8f0;
  color: #475467;
}

.rank-badge.rank-1 { background: #f59e0b; color: #ffffff; box-shadow: 0 2px 8px rgba(245, 158, 11, 0.4); }
.rank-badge.rank-2 { background: #64748b; color: #ffffff; }
.rank-badge.rank-3 { background: #d97706; color: #ffffff; }

.person-meta {
  display: flex;
  flex-direction: column;
  flex: 1;
}

.person-meta strong {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}

.person-meta small {
  font-size: 11px;
  color: #64748b;
}

.card-action {
  margin-top: auto;
  background: transparent;
  border: none;
  color: #2563eb;
  font-size: 13px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  padding: 0;
}

.card-action .arrow {
  transition: transform 0.2s ease;
}

.result-card:hover .card-action .arrow {
  transform: translateX(4px);
}

/* 2. 学院团体总分榜 Layout */
.ranking-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 44px;
}

.ranking-panel, .chart-panel {
  padding: 24px;
  background: #ffffff;
  border-radius: 18px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.03);
}

.panel-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.panel-heading h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 800;
  color: #0f172a;
}

.head-icon {
  font-size: 24px;
  color: #2563eb;
}

.ranking-table {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ranking-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-radius: 10px;
  background: #f8fafc;
}

.ranking-row.top-three {
  background: #eff6ff;
}

.college-name {
  flex: 1;
  font-size: 14px;
  color: #0f172a;
}

.medals-count {
  display: flex;
  gap: 8px;
  font-size: 12px;
}

.total-points {
  font-size: 16px;
  color: #2563eb;
}

.chart {
  height: 320px;
  width: 100%;
}

/* 3. 赛程列表 Strip */
.schedule-strip {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.schedule-card {
  padding: 18px;
  background: #ffffff;
  border-radius: 14px;
  border: 1px solid #e2e8f0;
  display: flex;
  align-items: center;
  gap: 14px;
}

.date-box {
  width: 48px;
  height: 48px;
  flex-basis: 48px;
  border-radius: 10px;
  background: #eff6ff;
  color: #2563eb;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.date-box b {
  font-size: 18px;
  line-height: 1;
}

.date-box span {
  font-size: 10px;
  margin-top: 2px;
}

.schedule-info {
  flex: 1;
}

.schedule-info strong {
  font-size: 14px;
  color: #0f172a;
}

.schedule-info p {
  margin: 3px 0 0;
  font-size: 12px;
  color: #64748b;
  display: flex;
  align-items: center;
  gap: 4px;
}

.schedule-status-chip {
  font-size: 11px;
  color: #10b981;
  background: #ecfdf5;
  padding: 4px 8px;
  border-radius: 6px;
  font-weight: 600;
}

/* 4. 全量表格 */
.full-table {
  padding: 24px;
  background: #ffffff;
  border-radius: 18px;
  border: 1px solid #e2e8f0;
}

.table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.table-toolbar h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 800;
}

.filters {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* 页脚 */
.public-footer {
  padding: 40px 24px;
  background: #ffffff;
  border-top: 1px solid #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  max-width: 1280px;
  margin: 0 auto;
}

.public-footer p {
  font-size: 0.8125rem;
  opacity: 0.6;
}

@media (max-width: 980px) {
  .latest-grid, .ranking-layout, .schedule-strip {
    grid-template-columns: 1fr;
  }
  .hero-medal-card {
    display: none;
  }
  .table-toolbar {
    align-items: flex-start;
    flex-direction: column;
    gap: 16px;
  }
  .filters {
    flex-wrap: wrap;
  }
  .topbar nav {
    display: none;
  }
}
</style>
