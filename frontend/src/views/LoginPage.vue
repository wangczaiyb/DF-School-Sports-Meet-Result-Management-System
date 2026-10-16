<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowRight, Lock, Monitor, School, Trophy, User, View, Hide, Medal, Check } from '@element-plus/icons-vue'
import api, { errorMessage } from '../api'
import { useAuthStore, type LoginKind } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const showPassword = ref(false)
const capsLock = ref(false)
const registerVisible = ref(false)
const settings = reactive({
  system_name: '校园运动会赛事成绩管理系统',
  short_name: '校园运动会赛事成绩管理系统',
  login_heading: '让每一次冲刺，都被准确记录',
  login_subtitle: '赛事编排、成绩审核与荣誉发布，一站式协同完成',
  primary_color: '#246BFD',
  logo_text: '跃',
})
const form = reactive({ kind: 'developer' as LoginKind, username: 'developer01', password: 'Dev123456!' })
const registerForm = reactive({ student_no: '', name: '' })

const roleOptions = [
  { value: 'developer', label: '开发人员', icon: Monitor, hint: '系统维护与全局管理' },
  { value: 'admin', label: '管理人员', icon: School, hint: '赛事组织与成绩审核' },
  { value: 'student', label: '学生', icon: User, hint: '查看我的赛程与成绩' },
] as const
const activeRole = computed(() => roleOptions.find(item => item.value === form.kind)!)

function selectRole(kind: LoginKind) {
  form.kind = kind
  if (kind === 'developer') Object.assign(form, { username: 'developer01', password: 'Dev123456!' })
  if (kind === 'admin') Object.assign(form, { username: 'admin0001', password: 'Admin123456!' })
  if (kind === 'student') Object.assign(form, { username: '26001001', password: 'DF26001001' })
}

async function submit() {
  if (!form.username || !form.password) return ElMessage.warning('请输入账号和密码')
  loading.value = true
  try {
    await auth.login(form.kind, form.username.trim(), form.password)
    ElMessage.success(`欢迎回来，${auth.user.display_name}`)
    router.push('/app')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

async function registerStudent() {
  registerForm.student_no = registerForm.student_no.trim()
  if (!/^[0-9]{8}$/.test(registerForm.student_no)) return ElMessage.warning('学号必须为8位数字')
  try {
    await api.post('/auth/student-register', registerForm)
    ElMessage.success('账号激活成功，可用初始密码直接登录，不强制修改密码')
    registerVisible.value = false
    selectRole('student')
    form.username = registerForm.student_no
    form.password = `DF${registerForm.student_no}`
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

function forgotPassword() {
  ElMessage.info(form.kind === 'student' ? '请联系开发人员重置密码，默认重置后为 DF + 完整学号。' : '请联系系统开发人员或有账号管理权限的负责人重置密码。')
}

onMounted(async () => {
  try {
    Object.assign(settings, (await api.get('/public/settings')).data)
    document.documentElement.style.setProperty('--brand', settings.primary_color)
    document.title = settings.system_name
  } catch { /* 后端启动前保留默认品牌内容 */ }
})
</script>

<template>
  <main class="login-page" :style="{ '--login-brand': settings.primary_color }">
    <section class="brand-side">
      <!-- 动态极光运动跑道 SVG 动画背景 -->
      <svg class="track-svg" viewBox="0 0 800 800" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path class="track-line line-1" d="M -100 200 C 200 100, 500 500, 900 200" stroke="url(#grad1)" stroke-width="2.5" />
        <path class="track-line line-2" d="M -100 400 C 300 200, 400 700, 900 300" stroke="url(#grad2)" stroke-width="2" />
        <path class="track-line line-3" d="M -100 600 C 100 300, 600 200, 900 600" stroke="url(#grad3)" stroke-width="3" />
        <defs>
          <linearGradient id="grad1" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.8"/>
            <stop offset="50%" stop-color="#818cf8" stop-opacity="0.5"/>
            <stop offset="100%" stop-color="#fbbf24" stop-opacity="0"/>
          </linearGradient>
          <linearGradient id="grad2" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#34d399" stop-opacity="0.9"/>
            <stop offset="100%" stop-color="#60a5fa" stop-opacity="0.1"/>
          </linearGradient>
          <linearGradient id="grad3" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#fbbf24" stop-opacity="0.8"/>
            <stop offset="100%" stop-color="#f43f5e" stop-opacity="0.1"/>
          </linearGradient>
        </defs>
      </svg>

      <!-- 动态运动发光能量浮球 -->
      <div class="speed-orb orb-a"></div>
      <div class="speed-orb orb-b"></div>
      <div class="speed-orb orb-c"></div>

      <!-- 半透明无缝运动图标流轮播轨道 (Kinetic Glass Sports Icon Carousel Streams) -->
      <div class="sports-stream-wrap">
        <!-- 上层跑道：从右向左流畅轮播 -->
        <div class="stream-track track-left">
          <div class="stream-group">
            <div class="glass-icon-node">🏃</div>
            <div class="glass-icon-node">🏀</div>
            <div class="glass-icon-node">⚽</div>
            <div class="glass-icon-node">🏐</div>
            <div class="glass-icon-node">🎾</div>
            <div class="glass-icon-node">🏸</div>
            <div class="glass-icon-node">🏓</div>
            <div class="glass-icon-node">🏊</div>
          </div>
          <!-- 重复组实现无缝对接 循环 -->
          <div class="stream-group" aria-hidden="true">
            <div class="glass-icon-node">🏃</div>
            <div class="glass-icon-node">🏀</div>
            <div class="glass-icon-node">⚽</div>
            <div class="glass-icon-node">🏐</div>
            <div class="glass-icon-node">🎾</div>
            <div class="glass-icon-node">🏸</div>
            <div class="glass-icon-node">🏓</div>
            <div class="glass-icon-node">🏊</div>
          </div>
        </div>

        <!-- 下层跑道：从左向右反向无缝轮播 -->
        <div class="stream-track track-right">
          <div class="stream-group">
            <div class="glass-icon-node">🚴</div>
            <div class="glass-icon-node">🏋️</div>
            <div class="glass-icon-node">🤺</div>
            <div class="glass-icon-node">🏹</div>
            <div class="glass-icon-node">⏱️</div>
            <div class="glass-icon-node">🏆</div>
            <div class="glass-icon-node">🥇</div>
            <div class="glass-icon-node">🎯</div>
          </div>
          <!-- 重复组实现无缝对接 循环 -->
          <div class="stream-group" aria-hidden="true">
            <div class="glass-icon-node">🚴</div>
            <div class="glass-icon-node">🏋️</div>
            <div class="glass-icon-node">🤺</div>
            <div class="glass-icon-node">🏹</div>
            <div class="glass-icon-node">⏱️</div>
            <div class="glass-icon-node">🏆</div>
            <div class="glass-icon-node">🥇</div>
            <div class="glass-icon-node">🎯</div>
          </div>
        </div>
      </div>

      <header class="brand-header">
        <div class="brand-mark">{{ settings.logo_text }}</div>
        <div><strong>{{ settings.short_name }}</strong><span>赛事管理</span></div>
      </header>

      <div class="brand-copy">
        <div class="brand-kicker"><span class="kicker-pulse"></span> 赛事动态</div>
        <h1 class="art-title">{{ settings.login_heading }}</h1>
        <p>{{ settings.login_subtitle }}</p>
        <div class="flow-strip">
          <div class="step-node active"><el-icon><Check /></el-icon><span>分权登记</span></div>
          <i class="flow-line"></i>
          <div class="step-node active"><el-icon><Check /></el-icon><span>逐级审核</span></div>
          <i class="flow-line"></i>
          <div class="step-node active"><el-icon><Check /></el-icon><span>终审发布</span></div>
        </div>
      </div>

      <!-- 动态 3D 浮空运动金牌面板 -->
      <div class="stadium-card card-3d">
        <div class="pulse-ring"><el-icon><Medal /></el-icon></div>
        <div><span>赛事数据实时归档</span><strong>准确 · 公平 · 可追溯</strong></div>
      </div>

      <footer>校园赛事数字化管理 · 数据以终审发布为准</footer>
    </section>

    <section class="form-side">
      <div class="mobile-brand"><div class="brand-mark">{{ settings.logo_text }}</div><b>{{ settings.short_name }}</b></div>
      <div class="login-card">
        <div class="card-heading">
          <span class="eyebrow">WELCOME BACK</span>
          <h2>登录赛事工作台</h2>
          <p>请选择与你账号匹配的身份入口</p>
        </div>
        <div class="role-tabs">
          <button v-for="role in roleOptions" :key="role.value" :class="{ active: form.kind === role.value }" @click="selectRole(role.value)">
            <el-icon><component :is="role.icon" /></el-icon><span>{{ role.label }}</span>
          </button>
        </div>
        <div class="role-hint"><component :is="activeRole.icon" /><span>{{ activeRole.hint }}</span></div>
        <form @submit.prevent="submit">
          <label>账号</label>
          <div class="input-wrap"><el-icon><User /></el-icon><input v-model="form.username" autocomplete="username" :placeholder="form.kind === 'student' ? '请输入学号' : '请输入用户名'" /></div>
          <label>密码</label>
          <div class="input-wrap"><el-icon><Lock /></el-icon><input v-model="form.password" :type="showPassword ? 'text' : 'password'" autocomplete="current-password" placeholder="请输入密码" @keyup="capsLock = $event.getModifierState('CapsLock')" /><button type="button" class="eye" @click="showPassword = !showPassword"><el-icon><component :is="showPassword ? Hide : View" /></el-icon></button></div>
          <transition name="fade"><div v-if="capsLock" class="caps-tip">Caps Lock 已开启，请注意大小写</div></transition>
          <div class="form-meta"><button v-if="form.kind === 'student'" type="button" @click="registerVisible = true">学生账号激活</button><span v-else>连续输错 5 次将锁定 15 分钟</span><button type="button" @click="forgotPassword">忘记密码？</button></div>
          <el-button class="login-button" type="primary" native-type="submit" :loading="loading">进入系统 <el-icon><ArrowRight /></el-icon></el-button>
        </form>
        <div class="divider"><span>无需登录</span></div>
        <button class="public-button" @click="router.push('/results')"><el-icon><Trophy /></el-icon><span>查看赛事成绩</span><el-icon><ArrowRight /></el-icon></button>
      </div>
      <p class="security-note"><span class="status-dot"></span>账号权限与全部操作记录均由服务器安全保存</p>
    </section>

    <el-dialog v-model="registerVisible" title="激活学生账号" width="420px">
      <el-form label-position="top">
        <el-form-item label="学号"><el-input v-model="registerForm.student_no" maxlength="8" inputmode="numeric" placeholder="例如24000001（24级），须与名单一致" /></el-form-item>
        <el-form-item label="姓名"><el-input v-model="registerForm.name" placeholder="请输入真实姓名" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="registerVisible = false">取消</el-button><el-button type="primary" @click="registerStudent">核验并激活</el-button></template>
    </el-dialog>
  </main>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(520px, 1.08fr) minmax(520px, 0.92fr);
  background: var(--bg-page);
}

.brand-side {
  position: relative;
  overflow: hidden;
  padding: 48px 6vw;
  color: #ffffff;
  background: linear-gradient(135deg, #0b193c 0%, #1e3a8a 50%, var(--login-brand) 100%);
  display: flex;
  flex-direction: column;
}

.brand-side::after {
  content: '';
  position: absolute;
  inset: 0;
  background-image: 
    radial-gradient(rgba(255, 255, 255, 0.1) 1px, transparent 1px),
    linear-gradient(to right, rgba(255, 255, 255, 0.05) 1px, transparent 1px);
  background-size: 32px 32px;
  mask-image: linear-gradient(to bottom, #000 60%, transparent 100%);
  opacity: 0.6;
}

/* ==========================================================================
   艺术级运动动效 (Artistic Motion Athletic Styling)
   ========================================================================== */

.brand-side {
  position: relative;
  overflow: hidden;
  padding: 48px 6vw;
  color: #ffffff;
  background: radial-gradient(circle at 10% 20%, #1e3a8a 0%, #0b1329 80%);
  display: flex;
  flex-direction: column;
}

/* SVG 跑道动画 */
.track-svg {
  position: absolute;
  inset: -100px;
  width: calc(100% + 200px);
  height: calc(100% + 200px);
  z-index: 1;
  pointer-events: none;
  opacity: 0.7;
}

.track-line {
  stroke-dasharray: 20 10;
  animation: dash-flow 35s linear infinite;
}

.line-1 { animation-duration: 30s; }
.line-2 { animation-duration: 45s; animation-direction: reverse; }
.line-3 { animation-duration: 25s; }

@keyframes dash-flow {
  0% { stroke-dashoffset: 1000; }
  100% { stroke-dashoffset: 0; }
}

/* 动态运动发光球 */
.speed-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(50px);
  pointer-events: none;
  z-index: 1;
  opacity: 0.4;
  animation: orb-float 12s ease-in-out infinite alternate;
}

/* 半透明无缝运动图标流轮播轨道 (Kinetic Glass Sports Icon Carousel Streams) */
.sports-stream-wrap {
  position: absolute;
  inset: -10% -20%;
  pointer-events: none;
  z-index: 2;
  display: flex;
  flex-direction: column;
  justify-content: space-around;
  transform: rotate(-10deg);
  opacity: 0.75;
}

.stream-track {
  display: flex;
  width: max-content;
  pointer-events: auto;
}

.track-left {
  animation: stream-scroll-left 32s linear infinite;
}

.track-right {
  animation: stream-scroll-right 36s linear infinite;
}

.track-left:hover, .track-right:hover {
  animation-play-state: paused;
}

.stream-group {
  display: flex;
  gap: 28px;
  padding-right: 28px;
}

.glass-icon-node {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(14px) saturate(180%);
  -webkit-backdrop-filter: blur(14px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.22);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.4);
  display: grid;
  place-items: center;
  font-size: 24px;
  opacity: 0.65;
  cursor: pointer;
  user-select: none;
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.glass-icon-node:hover {
  opacity: 1;
  background: rgba(255, 255, 255, 0.28);
  border-color: rgba(255, 255, 255, 0.7);
  transform: scale(1.3) translateY(-6px);
  box-shadow: 0 16px 36px rgba(0, 0, 0, 0.35), 0 0 30px rgba(56, 189, 248, 0.7);
}

@keyframes stream-scroll-left {
  0% { transform: translateX(0); }
  100% { transform: translateX(-50%); }
}

@keyframes stream-scroll-right {
  0% { transform: translateX(-50%); }
  100% { transform: translateX(0); }
}

.orb-a {
  width: 320px;
  height: 320px;
  top: -80px;
  right: -60px;
  background: radial-gradient(circle, #2563eb, transparent);
}

.orb-b {
  width: 400px;
  height: 400px;
  bottom: -100px;
  left: -80px;
  background: radial-gradient(circle, #0284c7, transparent);
  animation-duration: 16s;
  animation-delay: -4s;
}

.orb-c {
  width: 250px;
  height: 250px;
  top: 40%;
  left: 30%;
  background: radial-gradient(circle, #d97706, transparent);
  opacity: 0.25;
  animation-duration: 20s;
}

@keyframes orb-float {
  0% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(40px, -30px) scale(1.15); }
  100% { transform: translate(-30px, 30px) scale(0.9); }
}

.brand-header, .brand-copy, .stadium-card, .brand-side footer {
  position: relative;
  z-index: 3;
}

.brand-header {
  display: flex;
  align-items: center;
  gap: 16px;
}

.brand-mark {
  width: 52px;
  height: 52px;
  border-radius: 16px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #ffffff, #e0f2fe);
  color: #0284c7;
  font-size: 26px;
  font-weight: 900;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.3), 0 0 20px rgba(56, 189, 248, 0.4);
}

.brand-header div:last-child {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.brand-header strong {
  font-size: 20px;
  font-weight: 800;
  letter-spacing: -0.01em;
}

.brand-header span {
  font-size: 10px;
  letter-spacing: 0.25em;
  opacity: 0.75;
  font-weight: 700;
}

.brand-copy {
  margin: auto 0;
  max-width: 660px;
  padding-bottom: 30px;
}

.brand-kicker {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-weight: 800;
  letter-spacing: 0.16em;
  font-size: 11px;
  color: #38bdf8;
  background: rgba(56, 189, 248, 0.12);
  padding: 6px 16px;
  border-radius: 9999px;
  border: 1px solid rgba(56, 189, 248, 0.3);
  backdrop-filter: blur(10px);
}

.kicker-pulse {
  width: 8px;
  height: 8px;
  background: #38bdf8;
  border-radius: 50%;
  box-shadow: 0 0 12px #38bdf8;
  animation: pulse-dot 1.8s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.6); opacity: 0.5; }
}

/* 艺术艺术感流光标题 */
.art-title {
  font-size: clamp(38px, 4.2vw, 64px);
  line-height: 1.12;
  letter-spacing: -0.035em;
  font-weight: 900;
  margin: 22px 0;
  max-width: 650px;
  background: linear-gradient(120deg, #ffffff 0%, #93c5fd 35%, #fbbf24 70%, #ffffff 100%);
  background-size: 200% auto;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: shine 8s linear infinite;
}

@keyframes shine {
  to { background-position: 200% center; }
}

.brand-copy p {
  margin: 0;
  max-width: 540px;
  font-size: 1.0625rem;
  line-height: 1.7;
  opacity: 0.85;
  font-weight: 400;
}

.flow-strip {
  margin-top: 36px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.step-node {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 700;
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(12px);
  padding: 8px 16px;
  border-radius: 9999px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transition: all 0.3s ease;
}

.step-node:hover {
  background: rgba(255, 255, 255, 0.2);
  transform: translateY(-2px);
}

.step-node .el-icon {
  color: #34d399;
}

.flow-line {
  width: 24px;
  height: 2px;
  background: linear-gradient(90deg, rgba(52, 211, 153, 0.8), rgba(255, 255, 255, 0.2));
}

/* 3D 浮空运动金牌面板 */
.stadium-card.card-3d {
  width: fit-content;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 22px;
  background: rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 20px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.25);
  animation: float-3d 6s ease-in-out infinite alternate;
}

@keyframes float-3d {
  0% { transform: translateY(0) rotate(0deg); }
  100% { transform: translateY(-10px) rotate(1deg); }
}

.pulse-ring {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: linear-gradient(135deg, #f59e0b, #d97706);
  color: #ffffff;
  display: grid;
  place-items: center;
  font-size: 22px;
  box-shadow: 0 0 20px rgba(245, 158, 11, 0.5);
  position: relative;
}

.pulse-ring::after {
  content: '';
  position: absolute;
  inset: -4px;
  border-radius: 18px;
  border: 2px solid rgba(245, 158, 11, 0.6);
  animation: pulse-ring-expand 2s cubic-bezier(0.215, 0.61, 0.355, 1) infinite;
}

@keyframes pulse-ring-expand {
  0% { transform: scale(0.9); opacity: 1; }
  100% { transform: scale(1.3); opacity: 0; }
}

.pulse {
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, rgba(52, 211, 153, 0.25), rgba(16, 185, 129, 0.4));
  color: #34d399;
  border-radius: 14px;
  font-size: 20px;
  box-shadow: 0 0 15px rgba(52, 211, 153, 0.3);
}

.stadium-card div:last-child {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.stadium-card span {
  font-size: 11px;
  opacity: 0.75;
  letter-spacing: 0.02em;
}

.stadium-card strong {
  font-size: 14px;
  font-weight: 700;
}

.brand-side footer {
  margin-top: 30px;
  font-size: 12px;
  opacity: 0.55;
  letter-spacing: 0.02em;
}

/* 跑道微光边线 */
.track {
  position: absolute;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 50%;
  transform: rotate(-18deg);
  z-index: 1;
  pointer-events: none;
}

.track-one { width: 950px; height: 360px; left: -180px; bottom: -120px; }
.track-two { width: 760px; height: 280px; left: -80px; bottom: -78px; }
.track-three { width: 570px; height: 200px; left: 20px; bottom: -35px; }

.light {
  position: absolute;
  width: 420px;
  height: 420px;
  background: radial-gradient(circle, rgba(56, 189, 248, 0.3), transparent 65%);
  border-radius: 50%;
  pointer-events: none;
}

.light-a { right: -100px; top: -100px; }
.light-b { left: 15%; bottom: -180px; }

/* 右侧登录表单 */
.form-side {
  background: var(--bg-page);
  padding: 40px 5vw;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}

.login-card {
  width: min(460px, 100%);
  padding: 40px 42px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-xl);
  background: #ffffff;
  box-shadow: var(--shadow-xl), 0 0 0 1px rgba(255, 255, 255, 0.8) inset;
}

.card-heading h2 {
  margin: 10px 0 6px;
  font-size: 1.75rem;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: var(--ink-primary);
}

.card-heading p {
  margin: 0;
  color: var(--muted);
  font-size: 0.875rem;
}

.role-tabs {
  margin-top: 26px;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  padding: 6px;
  background: var(--bg-subtle);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-subtle);
}

.role-tabs button {
  border: 0;
  background: transparent;
  color: var(--muted);
  padding: 12px 6px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  font-size: 0.75rem;
  font-weight: 600;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.role-tabs button:hover {
  color: var(--ink-primary);
}

.role-tabs button.active {
  background: #ffffff;
  color: var(--login-brand);
  box-shadow: var(--shadow-sm), 0 2px 8px rgba(37, 99, 235, 0.12);
  font-weight: 700;
}

.role-tabs .el-icon {
  font-size: 20px;
}

.role-hint {
  margin: 16px 0 20px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--login-brand);
  font-size: 0.8125rem;
  font-weight: 600;
  background: var(--brand-soft);
  padding: 8px 14px;
  border-radius: 8px;
}

.role-hint svg {
  width: 15px;
  height: 15px;
}

form label {
  display: block;
  font-size: 0.8125rem;
  color: var(--ink-secondary);
  font-weight: 700;
  margin: 16px 0 8px;
}

.input-wrap {
  height: 46px;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  background: #ffffff;
  display: flex;
  align-items: center;
  padding: 0 14px;
  gap: 12px;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.input-wrap:focus-within {
  border-color: var(--login-brand);
  box-shadow: 0 0 0 4px var(--brand-soft);
}

.input-wrap > .el-icon {
  color: var(--muted-light);
  font-size: 18px;
}

.input-wrap input {
  flex: 1;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--ink-primary);
  font-size: 0.9375rem;
}

.eye {
  border: 0;
  background: transparent;
  color: var(--muted-light);
  cursor: pointer;
  padding: 4px;
  display: grid;
  place-items: center;
  transition: color 0.15s ease;
}

.eye:hover {
  color: var(--ink-primary);
}

.caps-tip {
  margin-top: 8px;
  color: #d97706;
  font-size: 0.75rem;
  font-weight: 600;
}

.form-meta {
  margin: 18px 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--muted);
  font-size: 0.8125rem;
}

.form-meta button {
  border: 0;
  background: transparent;
  color: var(--login-brand);
  padding: 0;
  cursor: pointer;
  font-weight: 600;
}

.form-meta button:hover {
  text-decoration: underline;
}

.login-button {
  width: 100%;
  height: 48px;
  border-radius: var(--radius-md);
  font-weight: 700;
  font-size: 0.9375rem;
}

.login-button .el-icon {
  margin-left: 8px;
}

.divider {
  display: flex;
  align-items: center;
  gap: 14px;
  margin: 26px 0 18px;
  color: var(--muted-light);
  font-size: 0.75rem;
  font-weight: 600;
}

.divider::before, .divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--border-light);
}

.public-button {
  width: 100%;
  height: 46px;
  padding: 0 18px;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  background: #ffffff;
  color: var(--ink-primary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  box-shadow: var(--shadow-sm);
}

.public-button:hover {
  border-color: var(--login-brand);
  color: var(--login-brand);
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

.public-button span {
  flex: 1;
  text-align: left;
  margin-left: 12px;
  font-weight: 700;
  font-size: 0.875rem;
}

.security-note {
  font-size: 0.75rem;
  color: var(--muted);
  margin: 24px 0 0;
  display: flex;
  align-items: center;
}

.mobile-brand {
  display: none;
}

.fade-enter-active, .fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

@media (max-width: 980px) {
  .login-page {
    grid-template-columns: 1fr;
    background: var(--bg-page);
  }
  .brand-side {
    display: none;
  }
  .form-side {
    min-height: 100vh;
    padding: 24px;
  }
  .mobile-brand {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 24px;
  }
  .mobile-brand .brand-mark {
    width: 44px;
    height: 44px;
    font-size: 22px;
  }
  .login-card {
    padding: 32px 28px;
  }
}
</style>
