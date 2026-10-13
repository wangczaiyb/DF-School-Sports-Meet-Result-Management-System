<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Aim, Calendar, CirclePlus, DataAnalysis, Document, Download, EditPen, Fold, Grid, Lock,
  Menu as MenuIcon, Medal, Operation, Refresh, Search, Setting, SwitchButton, Tickets, Trophy, User,
  UserFilled, UploadFilled, View, ArrowRight, ChatDotRound, Cpu
} from '@element-plus/icons-vue'
import api, { errorMessage } from '../api'
import { useAuthStore } from '../stores/auth'
import AiCenter from './ai/AiCenter.vue'
import AiCopilotDrawer from './ai/AiCopilotDrawer.vue'
import RopeTableTools from './RopeTableTools.vue'

const router = useRouter()
const auth = useAuthStore()
const active = ref('overview')
const collapsed = ref(false)
const loading = ref(false)
const aiDrawerVisible = ref(false)
const summary = reactive<any>({})
const settings = reactive<any>({ system_name: '校园运动会赛事成绩管理系统', short_name: '校园运动会赛事成绩管理系统', logo_text: '跃', primary_color: '#007aff', login_heading: '', results_page_name: '', footer: '' })
const accounts = ref<any[]>([])
const quotas = reactive<any>({})
const meets = ref<any[]>([])
const events = ref<any[]>([])
const myEvents = ref<any[]>([])
const managers = ref<any[]>([])
const permissions = ref<any[]>([])
const scoringModels = ref<any[]>([])
const schedules = ref<any[]>([])
const scheduleRounds = ref<any[]>([])
const results = ref<any[]>([])
const registrations = ref<any[]>([])
const rounds = ref<any[]>([])
const students = ref<any[]>([])
const rosterImporting = ref(false)
const collegeTeams = ref<any[]>([])
const eventRosterItems = ref<any[]>([])
const eventRosterCandidates = ref<any[]>([])
const eventRosterRounds = ref<any[]>([])
const eventRosterEventId = ref<number | null>(null)
const eventRosterRoundId = ref<number | null>(null)
const rosterTab = ref('event')
const teamMeetId = ref<number | null>(null)
const teamEventFilterId = ref<number | null>(null)
const teamSearchKeyword = ref('')
const logs = ref<any[]>([])
const studentProfile = reactive<any>({})
const studentEvents = ref<any[]>([])
const studentResults = ref<any[]>([])
const selectedEventId = ref<number | null>(null)
const selectedResultRoundId = ref<number | null>(null)
const selectedResultIds = ref<number[]>([])
const accountDialog = ref(false)
const accountEditingId = ref<number | null>(null)
const meetEditingId = ref<number | null>(null)
const eventEditingId = ref<number | null>(null)
const studentRosterEditingId = ref<number | null>(null)
const collegeTeamEditingId = ref<number | null>(null)
const modelEditingId = ref<number | null>(null)
const permissionEditingId = ref<number | null>(null)
const scheduleEditingId = ref<number | null>(null)
const resultEditingId = ref<number | null>(null)
const meetDialog = ref(false)
const eventDialog = ref(false)
const modelDialog = ref(false)
const permissionDialog = ref(false)
const scheduleDialog = ref(false)
const resultDialog = ref(false)
const studentRosterDialog = ref(false)
const collegeTeamDialog = ref(false)
const registrationDialog = ref(false)
const registrationEditDialog = ref(false)
const changePasswordDialog = ref(false)
const accountForm = reactive<any>({ username: '', display_name: '', password: '', role: 'SCORER', department: '体育部', employee_no: '', phone: '' })
const meetForm = reactive<any>({ name: '', edition: String(new Date().getFullYear()), start_date: '', end_date: '', status: 'PREPARING', public_visible: true })
const meetSaving = ref(false)
const eventForm = reactive<any>({ meet_id: null, code: '', name: '', gender_group: 'MALE', participant_group: 'STUDENT', event_type: 'INDIVIDUAL', result_unit: '秒', sort_direction: 'ASC', stage: 'FINAL', qualification_count: 0, scoring_places: 8, points_multiplier: 1 })
const eventSaving = ref(false)
const modelForm = reactive<any>({ name: '', description: '', places: 8, pointsText: '9,7,6,5,4,3,2,1', individual_multiplier: 1, relay_multiplier: 2, team_multiplier: 2, status: 'DRAFT' })
const permissionForm = reactive<any>({ user_id: null, event_id: null, can_schedule: false, can_score: false, can_review: false, can_export: false })
const scheduleForm = reactive<any>({ event_id: null, round_id: null, competition_at: '', check_in_at: '', venue: '', heat: '', notes: '', status: 'NOT_STARTED', published: true })
const resultForm = reactive<any>({ event_id: null, round_id: null, registration_id: null, raw_value: null, competition_status: 'NORMAL', notes: '', modification_reason: '' })
const studentRosterForm = reactive<any>({ student_no: '', name: '', gender: '男', college: '', major: '', class_name: '' })
const collegeTeamForm = reactive<any>({ meet_id: null, event_id: null, college: '', team_name: '', leader_name: '', leader_phone: '', notes: '' })
const registrationParticipantIds = ref<number[]>([])
const registrationBatchForm = reactive<any>({ heat: '第1组', status: 'REGISTERED' })
const registrationEditForm = reactive<any>({ id: null, bib_no: '', heat: '', lane: '', status: 'REGISTERED' })
const passwordForm = reactive({ current_password: '', new_password: '', confirm_password: '' })

const role = computed(() => auth.user?.role || '')
const roleLabel: Record<string,string> = { DEVELOPER: '开发人员', SPORTS_TEACHER: '体育部老师', REFEREE: '裁判员', SCORER: '计分员', REFEREE_SCORER: '裁判兼计分员', STUDENT: '学生' }
const pageTitle = computed(() => navItems.value.find(item => item.key === active.value)?.label || '系统概览')

// 为不同组件分配主题背景色
const navItems = computed(() => {
  const base = [{ key: 'overview', label: role.value === 'STUDENT' ? '我的首页' : '系统概览', icon: Grid, color: 'blue' }]
  if (role.value === 'STUDENT') return [...base, { key: 'student-events', label: '我的赛事', icon: Calendar, color: 'orange' }, { key: 'student-results', label: '我的成绩', icon: Medal, color: 'purple' }]
  if (role.value === 'DEVELOPER') base.push({ key: 'accounts', label: '账号管理', icon: UserFilled, color: 'blue' }, { key: 'settings', label: '系统配置', icon: Setting, color: 'gray' }, { key: 'ai-center', label: 'AI 智能中心', icon: Cpu, color: 'purple' })
  if (['DEVELOPER','SPORTS_TEACHER'].includes(role.value)) base.push({ key: 'events', label: '赛事与项目', icon: Trophy, color: 'orange' }, { key: 'rosters', label: '名单录入', icon: User, color: 'teal' }, { key: 'basketball', label: '篮球赛制', icon: Aim, color: 'orange' }, { key: 'volleyball', label: '排球赛制', icon: Aim, color: 'purple' }, { key: 'table-tennis', label: '乒乓球赛制', icon: Medal, color: 'teal' }, { key: 'rope', label: '跳绳赛制', icon: Operation, color: 'green' }, { key: 'models', label: '计分模型', icon: DataAnalysis, color: 'purple' }, { key: 'permissions', label: '项目权限', icon: Lock, color: 'red' })
  else base.push({ key: 'my-events', label: '我的项目', icon: Aim, color: 'orange' }, { key: 'rope', label: '跳绳赛制', icon: Operation, color: 'green' })
  base.push({ key: 'schedules', label: '赛程管理', icon: Calendar, color: 'green' }, { key: 'results', label: '成绩工作台', icon: Tickets, color: 'blue' })
  if (role.value === 'DEVELOPER') base.push({ key: 'logs', label: '操作日志', icon: Document, color: 'gray' })
  return base
})
const canCreateBusiness = computed(() => ['DEVELOPER','SPORTS_TEACHER'].includes(role.value))

// 🚩 多届次运动会绑定与联动
const selectedMeetId = ref<number | null>(null)
const currentMeet = computed(() => meets.value.find((m: any) => m.id === selectedMeetId.value) || meets.value[0])

function onSelectedMeetChange() {
  teamMeetId.value = selectedMeetId.value
  if (active.value === 'basketball') {
    basketballEventId.value = basketballEvents.value[0]?.id || null
    loadBasketballData()
  } else if (active.value === 'volleyball') {
    volleyballEventId.value = volleyballEvents.value[0]?.id || null
    loadVolleyballData()
  } else if (active.value === 'table-tennis') {
    ttTeamEventId.value = ttTeamEvents.value[0]?.id || null
    ttMsEventId.value = ttMsEvents.value[0]?.id || null
    ttWsEventId.value = ttWsEvents.value[0]?.id || null
    loadTableTennisData()
  } else if (active.value === 'rope') {
    loadRopeData()
  } else if (active.value === 'rosters') {
    loadCollegeTeams()
  }
}

async function quickGenerateTeamsForCurrentMeet() {
  const targetMeetId = selectedMeetId.value || teamMeetId.value || (meets.value[0]?.id || null)
  if (!targetMeetId) return ElMessage.warning('请选择运动会届次')
  try {
    const { data } = await api.post('/sports-teacher/college-teams/generate', { meet_id: targetMeetId })
    ElMessage.success(`成功为该届运动会生成 ${data.created} 所学院代表队！`)
    if (active.value === 'basketball') await loadBasketballData()
    else if (active.value === 'volleyball') await loadVolleyballData()
    else if (active.value === 'table-tennis') await loadTableTennisData()
    else if (active.value === 'rope') await loadRopeData()
    else if (active.value === 'rosters') await loadCollegeTeams()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

// 🏀 篮球赛制模块变量
const basketballEventId = ref<number | null>(null)
const basketballEvents = computed(() => {
  return events.value.filter((e: any) => 
    (!selectedMeetId.value || e.meet_id === selectedMeetId.value) &&
    (e.name.includes('篮球') || (e.code && (e.code.startsWith('BB') || e.code === 'MBB')))
  )
})
const basketballMatches = ref<any[]>([])
const basketballStandings = reactive<any>({ group_a: [], group_b: [] })
const basketballTeamsData = reactive<any>({ registered_teams: [], registered_team_ids: [], all_available_teams: [] })
const basketballAddTeamsDialog = ref(false)
const selectedBasketballTeamIds = ref<number[]>([])
const basketballCreateEventDialog = ref(false)
const basketballCreateEventForm = reactive<any>({ meet_id: null, name: '男子五人制篮球赛', code: 'BB_2026', gender_group: 'MALE' })

const basketballMatchDialog = ref(false)
const basketballMatchForm = reactive<any>({ id: null, home_team_name: '', away_team_name: '', home_score: 0, away_score: 0, court_venue: '', match_time: '' })

async function loadBasketballData() {
  await ensureEvents()
  if (!basketballEventId.value || !basketballEvents.value.some((e: any) => e.id === basketballEventId.value)) {
    const preferred = basketballEvents.value.find((e: any) => e.name.includes('篮球') || e.code === 'MBB') || basketballEvents.value[0]
    basketballEventId.value = preferred ? preferred.id : null
  }
  if (!basketballEventId.value) {
    basketballMatches.value = []
    Object.assign(basketballStandings, { group_a: [], group_b: [] })
    Object.assign(basketballTeamsData, { registered_teams: [], registered_team_ids: [], all_available_teams: [] })
    return
  }
  try {
    const [mRes, sRes, tRes] = await Promise.all([
      api.get('/sports-teacher/basketball/matches', { params: { event_id: basketballEventId.value } }),
      api.get('/sports-teacher/basketball/standings', { params: { event_id: basketballEventId.value } }),
      api.get('/sports-teacher/basketball/teams', { params: { event_id: basketballEventId.value } }),
    ])
    basketballMatches.value = mRes.data
    Object.assign(basketballStandings, sRes.data)
    Object.assign(basketballTeamsData, tRes.data)
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

function openCreateBasketballEventDialog() {
  const rand = Math.floor(Math.random() * 900) + 100
  basketballCreateEventForm.meet_id = selectedMeetId.value || (meets.value[0]?.id || null)
  basketballCreateEventForm.name = '男子五人制篮球赛'
  basketballCreateEventForm.code = `BB_${rand}`
  basketballCreateEventForm.gender_group = 'MALE'
  basketballCreateEventDialog.value = true
}

function openAddBasketballTeamsDialog() {
  selectedBasketballTeamIds.value = [...(basketballTeamsData.registered_team_ids || [])]
  basketballAddTeamsDialog.value = true
}

async function submitAddBasketballTeams() {
  if (!basketballEventId.value) return ElMessage.warning('请选择篮球项目')
  if (!selectedBasketballTeamIds.value.length) return ElMessage.warning('请至少选择一支参赛代表队')
  try {
    const { data } = await api.post('/sports-teacher/basketball/add-teams', {
      event_id: basketballEventId.value,
      team_ids: selectedBasketballTeamIds.value,
    })
    ElMessage.success(data.message)
    basketballAddTeamsDialog.value = false
    await loadBasketballData()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

async function submitQuickCreateBasketballEvent() {
  try {
    const { data } = await api.post('/sports-teacher/basketball/quick-create-event', basketballCreateEventForm)
    ElMessage.success(data.message)
    basketballCreateEventDialog.value = false
    events.value = (await api.get('/sports-teacher/events')).data
    if (basketballCreateEventForm.meet_id) selectedMeetId.value = basketballCreateEventForm.meet_id
    basketballEventId.value = data.event.id
    await loadBasketballData()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

async function autoGenerateBasketballGroups() {
  if (!basketballEventId.value) return ElMessage.warning('请选择篮球比赛项目')
  if (!basketballTeamsData.registered_teams || basketballTeamsData.registered_teams.length < 4) {
    return ElMessage.warning('参赛队伍不足4支，请先点击【👥 录入参赛队伍】选择学院代表队！')
  }
  try {
    const { data } = await api.post('/sports-teacher/basketball/groups/auto-generate', { event_id: basketballEventId.value })
    ElMessage.success(data.message)
    await loadBasketballData()
  } catch (e) { ElMessage.error(errorMessage(e)) }
}

function openEditBasketballMatch(m: any) {
  Object.assign(basketballMatchForm, {
    id: m.id,
    home_team_name: m.home_team_name,
    away_team_name: m.away_team_name,
    home_score: m.home_score !== null ? m.home_score : 80,
    away_score: m.away_score !== null ? m.away_score : 75,
    court_venue: m.court_venue || '篮球馆1号场',
    match_time: m.match_time || ''
  })
  basketballMatchDialog.value = true
}

async function saveBasketballMatch() {
  try {
    await api.put(`/sports-teacher/basketball/matches/${basketballMatchForm.id}`, basketballMatchForm)
    ElMessage.success('单场比分已录入，小组赛积分已实时计算（胜2分负1分）')
    basketballMatchDialog.value = false
    await loadBasketballData()
  } catch (e) { ElMessage.error(errorMessage(e)) }
}

async function advanceBasketballToFinals() {
  if (!basketballEventId.value) return
  try {
    const { data } = await api.post('/sports-teacher/basketball/advance-to-finals', { event_id: basketballEventId.value })
    ElMessage.success(data.message)
    await loadBasketballData()
  } catch (e) { ElMessage.error(errorMessage(e)) }
}

async function generateBasketballFinals() {
  if (!basketballEventId.value) return
  try {
    const { data } = await api.post('/sports-teacher/basketball/generate-finals', { event_id: basketballEventId.value })
    ElMessage.success(data.message)
    await loadBasketballData()
  } catch (e) { ElMessage.error(errorMessage(e)) }
}

async function finalizeBasketballResults() {
  if (!basketballEventId.value) return
  try {
    const { data } = await api.post('/sports-teacher/basketball/finalize-results', { event_id: basketballEventId.value })
    ElMessage.success(data.message)
    await loadBasketballData()
  } catch (e) { ElMessage.error(errorMessage(e)) }
}

// 🏐 排球赛制模块变量
const volleyballEventId = ref<number | null>(null)
const volleyballEvents = computed(() => {
  return events.value.filter((e: any) => 
    (!selectedMeetId.value || e.meet_id === selectedMeetId.value) &&
    (e.name.includes('排球') || (e.code && (e.code.startsWith('VB') || e.code === 'MVB')))
  )
})
const volleyballMatches = ref<any[]>([])
const volleyballStandings = reactive<any>({ group_a: [], group_b: [] })
const volleyballTeamsData = reactive<any>({ registered_teams: [], registered_team_ids: [], all_available_teams: [] })
const volleyballAddTeamsDialog = ref(false)
const selectedVolleyballTeamIds = ref<number[]>([])
const volleyballCreateEventDialog = ref(false)
const volleyballCreateEventForm = reactive<any>({ meet_id: null, name: '男女混合排球赛', code: 'VB_2026', gender_group: 'MIXED' })

function openCreateVolleyballEventDialog() {
  const rand = Math.floor(Math.random() * 900) + 100
  volleyballCreateEventForm.meet_id = selectedMeetId.value || (meets.value[0]?.id || null)
  volleyballCreateEventForm.name = '男女混合排球赛'
  volleyballCreateEventForm.code = `VB_${rand}`
  volleyballCreateEventForm.gender_group = 'MIXED'
  volleyballCreateEventDialog.value = true
}

async function submitQuickCreateVolleyballEvent() {
  try {
    const { data } = await api.post('/sports-teacher/volleyball/quick-create-event', volleyballCreateEventForm)
    ElMessage.success(data.message)
    volleyballCreateEventDialog.value = false
    events.value = (await api.get('/sports-teacher/events')).data
    if (volleyballCreateEventForm.meet_id) selectedMeetId.value = volleyballCreateEventForm.meet_id
    volleyballEventId.value = data.event.id
    await loadVolleyballData()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

const volleyballMatchDialog = ref(false)
const volleyballMatchForm = reactive<any>({
  id: null,
  home_team_name: '',
  away_team_name: '',
  home_team_id: null,
  away_team_id: null,
  set1_home: 25,
  set1_away: 18,
  set2_home: 25,
  set2_away: 20,
  set3_home: 0,
  set3_away: 0,
  need_third_set: false,
  is_forfeit: false,
  forfeit_team_id: null,
  court_venue: '排球馆1号场',
  match_time: '',
  notes: '',
})

// 👥 代表队队员阵容管理变量 (女生不低于2人规则 & 3男2女规程 & 阵容自由维护)
const teamMembersDialog = ref(false)
const currentManagingTeam = reactive<any>({
  id: null,
  meet_id: null,
  meet_name: '',
  event_id: null,
  event_name: '',
  college: '',
  team_name: '',
  leader_name: '',
  leader_phone: '',
  total_members: 0,
  male_count: 0,
  female_count: 0,
  female_rule_passed: false,
  female_rule_tip: '',
})
const currentTeamMembers = ref<any[]>([])
const availableCandidates = ref<any[]>([])
const selectedCandidateIds = ref<number[]>([])
const newMemberRole = ref('队员')
const memberRolePresets = ['队长', '主力', '副攻', '二传', '接应', '自由人', '男单1', '男单2', '男单3', '女单1', '女单2', '队员']

async function openTeamMembersManager(team: any) {
  currentManagingTeam.id = team.id
  currentManagingTeam.meet_id = team.meet_id
  currentManagingTeam.meet_name = team.meet_name || ''
  currentManagingTeam.event_id = team.event_id || null
  currentManagingTeam.event_name = team.event_name || '全能/通用代表队'
  currentManagingTeam.college = team.college
  currentManagingTeam.team_name = team.team_name || `${team.college}代表队`
  currentManagingTeam.leader_name = team.leader_name || ''
  currentManagingTeam.leader_phone = team.leader_phone || ''
  selectedCandidateIds.value = []
  newMemberRole.value = '队员'
  teamMembersDialog.value = true
  await reloadTeamMembersData(team.id)
}

async function reloadTeamMembersData(teamId: number) {
  try {
    const [mRes, cRes] = await Promise.all([
      api.get(`/sports-teacher/college-teams/${teamId}/members`),
      api.get(`/sports-teacher/college-teams/${teamId}/available-candidates`),
    ])
    Object.assign(currentManagingTeam, {
      total_members: mRes.data.total_members,
      male_count: mRes.data.male_count,
      female_count: mRes.data.female_count,
      female_rule_passed: mRes.data.female_rule_passed,
      female_rule_tip: mRes.data.female_rule_tip,
    })
    currentTeamMembers.value = mRes.data.members
    availableCandidates.value = cRes.data
    selectedCandidateIds.value = []
    if (active.value === 'rosters') {
      loadCollegeTeams()
    }
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

async function addTeamMembersBatch() {
  if (!selectedCandidateIds.value.length) return ElMessage.warning('请勾选要加入代表队的学生队员')
  try {
    const { data } = await api.post(`/sports-teacher/college-teams/${currentManagingTeam.id}/members/batch`, {
      student_ids: selectedCandidateIds.value,
      role_title: newMemberRole.value,
    })
    ElMessage.success(data.message)
    await reloadTeamMembersData(currentManagingTeam.id)
    if (active.value === 'volleyball') await loadVolleyballData()
    if (active.value === 'basketball') await loadBasketballData()
    if (active.value === 'table-tennis') await loadTableTennisData()
    if (active.value === 'rope') await loadRopeData()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

async function updateTeamMemberRole(member: any, roleTitle: string) {
  try {
    await api.put(`/sports-teacher/college-teams/${currentManagingTeam.id}/members/${member.id}`, {
      role_title: roleTitle,
      is_starter: member.is_starter,
    })
    ElMessage.success('队内角色已更新')
    await reloadTeamMembersData(currentManagingTeam.id)
    if (active.value === 'volleyball') await loadVolleyballData()
    if (active.value === 'basketball') await loadBasketballData()
    if (active.value === 'table-tennis') await loadTableTennisData()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

async function toggleTeamMemberStarter(member: any) {
  try {
    await api.put(`/sports-teacher/college-teams/${currentManagingTeam.id}/members/${member.id}`, {
      role_title: member.role_title,
      is_starter: !member.is_starter,
    })
    ElMessage.success('首发状态已切换')
    await reloadTeamMembersData(currentManagingTeam.id)
    if (active.value === 'volleyball') await loadVolleyballData()
    if (active.value === 'basketball') await loadBasketballData()
    if (active.value === 'table-tennis') await loadTableTennisData()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

async function deleteTeamMember(member: any) {
  try {
    await ElMessageBox.confirm(`确定将队员“${member.name} (${member.gender})”从代表队中移除吗？`, '移除队员', { type: 'warning' })
    await api.delete(`/sports-teacher/college-teams/${currentManagingTeam.id}/members/${member.id}`)
    ElMessage.success('队员已移除')
    await reloadTeamMembersData(currentManagingTeam.id)
    if (active.value === 'volleyball') await loadVolleyballData()
    if (active.value === 'basketball') await loadBasketballData()
    if (active.value === 'table-tennis') await loadTableTennisData()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(errorMessage(e))
  }
}

async function loadVolleyballData() {
  await ensureEvents()
  if (!volleyballEventId.value || !volleyballEvents.value.some((e: any) => e.id === volleyballEventId.value)) {
    const preferred = volleyballEvents.value.find((e: any) => e.name.includes('排球') || e.code === 'MVB' || (e.code && e.code.startsWith('VB'))) || volleyballEvents.value[0]
    volleyballEventId.value = preferred ? preferred.id : null
  }
  if (!volleyballEventId.value) {
    volleyballMatches.value = []
    Object.assign(volleyballStandings, { group_a: [], group_b: [] })
    Object.assign(volleyballTeamsData, { registered_teams: [], registered_team_ids: [], all_available_teams: [] })
    return
  }
  try {
    const [mRes, sRes, tRes] = await Promise.all([
      api.get('/sports-teacher/volleyball/matches', { params: { event_id: volleyballEventId.value } }),
      api.get('/sports-teacher/volleyball/standings', { params: { event_id: volleyballEventId.value } }),
      api.get('/sports-teacher/volleyball/teams', { params: { event_id: volleyballEventId.value } }),
    ])
    volleyballMatches.value = mRes.data
    Object.assign(volleyballStandings, sRes.data)
    Object.assign(volleyballTeamsData, tRes.data)
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

function openAddVolleyballTeamsDialog() {
  selectedVolleyballTeamIds.value = [...(volleyballTeamsData.registered_team_ids || [])]
  volleyballAddTeamsDialog.value = true
}

async function submitAddVolleyballTeams() {
  if (!volleyballEventId.value) return ElMessage.warning('请选择排球项目')
  if (!selectedVolleyballTeamIds.value.length) return ElMessage.warning('请至少选择一支参赛代表队')
  try {
    const { data } = await api.post('/sports-teacher/volleyball/add-teams', {
      event_id: volleyballEventId.value,
      team_ids: selectedVolleyballTeamIds.value,
    })
    ElMessage.success(data.message)
    volleyballAddTeamsDialog.value = false
    await loadVolleyballData()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

async function autoGenerateVolleyballGroups() {
  if (!volleyballEventId.value) return ElMessage.warning('请选择排球比赛项目')
  if (!volleyballTeamsData.registered_teams || volleyballTeamsData.registered_teams.length < 4) {
    return ElMessage.warning('参赛队伍不足4支，请先点击【👥 录入参赛队伍】选择学院代表队！')
  }
  try {
    const { data } = await api.post('/sports-teacher/volleyball/groups/auto-generate', { event_id: volleyballEventId.value })
    ElMessage.success(data.message)
    await loadVolleyballData()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

function openEditVolleyballMatch(m: any) {
  const sets = m.sets_detail || []
  const s1 = sets[0] || { home: 25, away: 18 }
  const s2 = sets[1] || { home: 25, away: 20 }
  const s3 = sets[2] || { home: 0, away: 0 }
  const has3rd = sets.length >= 3 || (s1.home > s1.away && s2.away > s2.home) || (s1.away > s1.home && s2.home > s2.away)
  Object.assign(volleyballMatchForm, {
    id: m.id,
    home_team_name: m.home_team_name,
    away_team_name: m.away_team_name,
    home_team_id: m.home_team_id,
    away_team_id: m.away_team_id,
    set1_home: s1.home,
    set1_away: s1.away,
    set2_home: s2.home,
    set2_away: s2.away,
    set3_home: s3.home || 15,
    set3_away: s3.away || 13,
    need_third_set: has3rd,
    is_forfeit: m.status === 'FORFEIT' || !!m.forfeit_team_id,
    forfeit_team_id: m.forfeit_team_id || m.away_team_id,
    court_venue: m.court_venue || '排球馆1号场',
    match_time: m.match_time || '',
    notes: m.notes || '',
  })
  volleyballMatchDialog.value = true
}

async function saveVolleyballMatch() {
  try {
    let payload: any = {
      court_venue: volleyballMatchForm.court_venue,
      match_time: volleyballMatchForm.match_time,
      notes: volleyballMatchForm.notes,
    }
    if (volleyballMatchForm.is_forfeit) {
      payload.is_forfeit = true
      payload.forfeit_team_id = volleyballMatchForm.forfeit_team_id
    } else {
      const sets = [
        { home: Number(volleyballMatchForm.set1_home), away: Number(volleyballMatchForm.set1_away) },
        { home: Number(volleyballMatchForm.set2_home), away: Number(volleyballMatchForm.set2_away) },
      ]
      if (volleyballMatchForm.need_third_set) {
        sets.push({ home: Number(volleyballMatchForm.set3_home), away: Number(volleyballMatchForm.set3_away) })
      }
      payload.sets_detail = sets
    }
    await api.put(`/sports-teacher/volleyball/matches/${volleyballMatchForm.id}`, payload)
    ElMessage.success('排球比分已录入，实时排球积分榜已更新（胜4分，1:2负2分，0:2负1分，弃权0分）')
    volleyballMatchDialog.value = false
    await loadVolleyballData()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

async function advanceVolleyballToFinals() {
  if (!volleyballEventId.value) return
  try {
    const { data } = await api.post('/sports-teacher/volleyball/advance-to-finals', { event_id: volleyballEventId.value })
    ElMessage.success(data.message)
    await loadVolleyballData()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

async function generateVolleyballFinals() {
  if (!volleyballEventId.value) return
  try {
    const { data } = await api.post('/sports-teacher/volleyball/generate-finals', { event_id: volleyballEventId.value })
    ElMessage.success(data.message)
    await loadVolleyballData()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

async function finalizeVolleyballResults() {
  if (!volleyballEventId.value) return
  try {
    const { data } = await api.post('/sports-teacher/volleyball/finalize-results', { event_id: volleyballEventId.value })
    ElMessage.success(data.message)
    await loadVolleyballData()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

// 🏓 乒乓球赛制模块
const ttTab = ref<'team' | 'ms' | 'ws'>('team')

// 混合团体赛
const ttTeamEventId = ref<number | null>(null)
const ttTeamEvents = computed(() => {
  return events.value.filter((e: any) => 
    (!selectedMeetId.value || e.meet_id === selectedMeetId.value) &&
    e.name.includes('乒乓') && (e.event_type === 'TEAM' || e.code === 'TT_TEAM' || e.code?.startsWith('TT_TEAM'))
  )
})
const ttTeamMatches = ref<any[]>([])
const ttTeamStandings = reactive<any>({ groups: { group_a: [], group_b: [] }, best_second: null })
const ttTeamStatusData = reactive<any>({ all_compliant: false, total_teams: 0, compliant_count: 0, teams: [] })
const ttTeamTeamsData = reactive<any>({ registered_teams: [], registered_team_ids: [], all_available_teams: [] })
const ttTeamAddTeamsDialog = ref(false)
const selectedTtTeamIds = ref<number[]>([])
const ttCreateEventDialog = ref(false)
const ttCreateEventForm = reactive<any>({ meet_id: null, category: 'TEAM', name: '乒乓球混合团体赛', code: 'TT_TEAM' })

const ttTeamMatchDialog = ref(false)
const ttTeamMatchForm = reactive<any>({
  id: null,
  home_team_name: '',
  away_team_name: '',
  home_team_id: null,
  away_team_id: null,
  court_venue: '乒乓球馆1号台',
  match_time: '',
  notes: '',
  is_forfeit: false,
  forfeit_team_id: null,
  rubbers: [
    { order: 1, type: 'MALE_SINGLES', name: '男单1', home_player_name: '', away_player_name: '', home_score: 2, away_score: 0, set1_home: 11, set1_away: 8, set2_home: 11, set2_away: 9, set3_home: 0, set3_away: 0, need_third_set: false },
    { order: 2, type: 'FEMALE_SINGLES', name: '女单1', home_player_name: '', away_player_name: '', home_score: 2, away_score: 0, set1_home: 11, set1_away: 8, set2_home: 11, set2_away: 9, set3_home: 0, set3_away: 0, need_third_set: false },
    { order: 3, type: 'MALE_SINGLES', name: '男单2', home_player_name: '', away_player_name: '', home_score: 2, away_score: 0, set1_home: 11, set1_away: 8, set2_home: 11, set2_away: 9, set3_home: 0, set3_away: 0, need_third_set: false },
    { order: 4, type: 'FEMALE_SINGLES', name: '女单2', home_player_name: '', away_player_name: '', home_score: 0, away_score: 2, set1_home: 8, set1_away: 11, set2_home: 9, set2_away: 11, set3_home: 0, set3_away: 0, need_third_set: false },
    { order: 5, type: 'MALE_SINGLES', name: '男单3', home_player_name: '', away_player_name: '', home_score: 2, away_score: 1, set1_home: 11, set1_away: 6, set2_home: 8, set2_away: 11, set3_home: 11, set3_away: 7, need_third_set: true },
  ],
})

// 单打（男单 / 女单）
const ttMsEventId = ref<number | null>(null)
const ttWsEventId = ref<number | null>(null)
const ttMsEvents = computed(() => {
  return events.value.filter((e: any) => 
    (!selectedMeetId.value || e.meet_id === selectedMeetId.value) &&
    e.name.includes('乒乓') && e.gender_group === 'MALE' && e.event_type === 'INDIVIDUAL'
  )
})
const ttWsEvents = computed(() => {
  return events.value.filter((e: any) => 
    (!selectedMeetId.value || e.meet_id === selectedMeetId.value) &&
    e.name.includes('乒乓') && e.gender_group === 'FEMALE' && e.event_type === 'INDIVIDUAL'
  )
})
const ttCurrentSinglesEventId = computed({
  get() { return ttTab.value === 'ms' ? ttMsEventId.value : ttWsEventId.value },
  set(val) {
    if (ttTab.value === 'ms') ttMsEventId.value = val
    else ttWsEventId.value = val
  }
})
const ttCurrentSinglesEvents = computed(() => ttTab.value === 'ms' ? ttMsEvents.value : ttWsEvents.value)

const ttSinglesAthletesData = reactive<any>({ athletes: [], college_counts: {}, total_athletes: 0 })
const ttSinglesMatches = ref<any[]>([])
const ttSinglesAddAthletesDialog = ref(false)
const selectedTtAthleteIds = ref<number[]>([])

const ttSinglesMatchDialog = ref(false)
const ttSinglesMatchForm = reactive<any>({
  id: null,
  home_student_name: '',
  away_student_name: '',
  home_college: '',
  away_college: '',
  home_student_id: null,
  away_student_id: null,
  best_of: 3,
  court_venue: '乒乓球馆1号台',
  match_time: '',
  notes: '',
  sets: [
    { set: 1, home: 11, away: 8 },
    { set: 2, home: 11, away: 9 },
    { set: 3, home: 0, away: 0 },
    { set: 4, home: 0, away: 0 },
    { set: 5, home: 0, away: 0 },
  ],
})

async function loadTableTennisData() {
  await ensureEvents()
  if (ttTab.value === 'team') {
    if (!ttTeamEventId.value || !ttTeamEvents.value.some((e: any) => e.id === ttTeamEventId.value)) {
      const preferred = ttTeamEvents.value.find((e: any) => e.code === 'TT_TEAM' || e.name.includes('团体')) || ttTeamEvents.value[0]
      ttTeamEventId.value = preferred ? preferred.id : null
    }
    if (!ttTeamEventId.value) {
      ttTeamMatches.value = []
      Object.assign(ttTeamStandings, { groups: { group_a: [], group_b: [] }, best_second: null })
      Object.assign(ttTeamStatusData, { all_compliant: false, total_teams: 0, compliant_count: 0, teams: [] })
      Object.assign(ttTeamTeamsData, { registered_teams: [], registered_team_ids: [], all_available_teams: [] })
      return
    }
    try {
      const [mRes, sRes, tRes, stRes] = await Promise.all([
        api.get('/sports-teacher/table-tennis/team/matches', { params: { event_id: ttTeamEventId.value } }),
        api.get('/sports-teacher/table-tennis/team/standings', { params: { event_id: ttTeamEventId.value } }),
        api.get('/sports-teacher/table-tennis/team/teams', { params: { event_id: ttTeamEventId.value } }),
        api.get('/sports-teacher/table-tennis/team/status', { params: { event_id: ttTeamEventId.value } }),
      ])
      ttTeamMatches.value = mRes.data
      Object.assign(ttTeamStandings, sRes.data)
      Object.assign(ttTeamTeamsData, tRes.data)
      Object.assign(ttTeamStatusData, stRes.data)
    } catch (e) {
      ElMessage.error(errorMessage(e))
    }
  } else {
    const targetEventId = ttCurrentSinglesEventId.value
    if (!targetEventId || !ttCurrentSinglesEvents.value.some((e: any) => e.id === targetEventId)) {
      const preferred = ttCurrentSinglesEvents.value[0]
      if (ttTab.value === 'ms') ttMsEventId.value = preferred ? preferred.id : null
      else ttWsEventId.value = preferred ? preferred.id : null
    }
    const currentId = ttCurrentSinglesEventId.value
    if (!currentId) {
      ttSinglesMatches.value = []
      Object.assign(ttSinglesAthletesData, { athletes: [], college_counts: {}, total_athletes: 0 })
      return
    }
    try {
      const [aRes, mRes] = await Promise.all([
        api.get('/sports-teacher/table-tennis/singles/athletes', { params: { event_id: currentId } }),
        api.get('/sports-teacher/table-tennis/singles/matches', { params: { event_id: currentId } }),
      ])
      Object.assign(ttSinglesAthletesData, aRes.data)
      ttSinglesMatches.value = mRes.data
    } catch (e) {
      ElMessage.error(errorMessage(e))
    }
  }
}

// 混合团体方法
function openAddTtTeamsDialog() {
  selectedTtTeamIds.value = [...(ttTeamTeamsData.registered_team_ids || [])]
  ttTeamAddTeamsDialog.value = true
}

async function submitAddTtTeams() {
  if (!ttTeamEventId.value) return ElMessage.warning('请选择混合团体项目')
  if (!selectedTtTeamIds.value.length) return ElMessage.warning('请至少选择一支参赛代表队')
  try {
    const { data } = await api.post('/sports-teacher/table-tennis/team/add-teams', {
      event_id: ttTeamEventId.value,
      team_ids: selectedTtTeamIds.value,
    })
    ElMessage.success(data.message)
    ttTeamAddTeamsDialog.value = false
    await loadTableTennisData()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

function onTtCategoryChange(cat: string) {
  ttCreateEventForm.category = cat
  const randNum = Math.floor(Math.random() * 900) + 100
  if (cat === 'TEAM') {
    ttCreateEventForm.name = '乒乓球混合团体赛'
    ttCreateEventForm.code = `TT_TEAM_${randNum}`
  } else if (cat === 'MS') {
    ttCreateEventForm.name = '男子乒乓球单打'
    ttCreateEventForm.code = `TT_MS_${randNum}`
  } else {
    ttCreateEventForm.name = '女子乒乓球单打'
    ttCreateEventForm.code = `TT_WS_${randNum}`
  }
}

function openCreateTtEventDialog(presetCategory?: 'TEAM' | 'MS' | 'WS') {
  const cat = presetCategory || (ttTab.value === 'team' ? 'TEAM' : (ttTab.value === 'ms' ? 'MS' : 'WS'))
  onTtCategoryChange(cat)
  if (!ttCreateEventForm.meet_id && meets.value.length) {
    ttCreateEventForm.meet_id = meets.value[0].id
  }
  ttCreateEventDialog.value = true
}

async function submitQuickCreateTtEvent() {
  try {
    const { data } = await api.post('/sports-teacher/table-tennis/quick-create-event', ttCreateEventForm)
    ElMessage.success(data.message)
    ttCreateEventDialog.value = false
    events.value = (await api.get('/sports-teacher/events')).data
    if (ttCreateEventForm.category === 'TEAM') {
      ttTab.value = 'team'
      ttTeamEventId.value = data.event.id
    } else if (ttCreateEventForm.category === 'MS') {
      ttTab.value = 'ms'
      ttMsEventId.value = data.event.id
    } else {
      ttTab.value = 'ws'
      ttWsEventId.value = data.event.id
    }
    await loadTableTennisData()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

async function autoGenerateTtTeamGroups() {
  if (!ttTeamEventId.value) return ElMessage.warning('请选择乒乓球混合团体项目')
  try {
    const { data } = await api.post('/sports-teacher/table-tennis/team/groups/auto-generate', { event_id: ttTeamEventId.value })
    ElMessage.success(data.message)
    await loadTableTennisData()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

function openEditTtTeamMatch(m: any) {
  const rubbers = (m.team_rubber_detail && m.team_rubber_detail.length === 5)
    ? m.team_rubber_detail.map((r: any) => {
        const s = r.sets || []
        const s1 = s[0] || { home: 11, away: 8 }
        const s2 = s[1] || { home: 11, away: 9 }
        const s3 = s[2] || { home: 0, away: 0 }
        const has3 = s.length >= 3 || (s1.home > s1.away && s2.away > s2.home) || (s1.away > s1.home && s2.home > s2.away)
        return {
          order: r.order,
          type: r.type,
          name: r.name,
          home_player_name: r.home_player_name || '',
          away_player_name: r.away_player_name || '',
          home_score: r.home_score !== undefined ? r.home_score : 2,
          away_score: r.away_score !== undefined ? r.away_score : 0,
          set1_home: s1.home,
          set1_away: s1.away,
          set2_home: s2.home,
          set2_away: s2.away,
          set3_home: s3.home || 11,
          set3_away: s3.away || 9,
          need_third_set: has3,
        }
      })
    : [
        { order: 1, type: 'MALE_SINGLES', name: '男单1', home_player_name: '', away_player_name: '', home_score: 2, away_score: 0, set1_home: 11, set1_away: 8, set2_home: 11, set2_away: 9, set3_home: 0, set3_away: 0, need_third_set: false },
        { order: 2, type: 'FEMALE_SINGLES', name: '女单1', home_player_name: '', away_player_name: '', home_score: 2, away_score: 0, set1_home: 11, set1_away: 8, set2_home: 11, set2_away: 9, set3_home: 0, set3_away: 0, need_third_set: false },
        { order: 3, type: 'MALE_SINGLES', name: '男单2', home_player_name: '', away_player_name: '', home_score: 2, away_score: 0, set1_home: 11, set1_away: 8, set2_home: 11, set2_away: 9, set3_home: 0, set3_away: 0, need_third_set: false },
        { order: 4, type: 'FEMALE_SINGLES', name: '女单2', home_player_name: '', away_player_name: '', home_score: 0, away_score: 2, set1_home: 8, set1_away: 11, set2_home: 9, set2_away: 11, set3_home: 0, set3_away: 0, need_third_set: false },
        { order: 5, type: 'MALE_SINGLES', name: '男单3', home_player_name: '', away_player_name: '', home_score: 2, away_score: 1, set1_home: 11, set1_away: 6, set2_home: 8, set2_away: 11, set3_home: 11, set3_away: 7, need_third_set: true },
      ]

  Object.assign(ttTeamMatchForm, {
    id: m.id,
    home_team_name: m.home_team_name,
    away_team_name: m.away_team_name,
    home_team_id: m.home_team_id,
    away_team_id: m.away_team_id,
    court_venue: m.court_venue || '乒乓球馆1号台',
    match_time: m.match_time || '',
    notes: m.notes || '',
    is_forfeit: m.status === 'FORFEIT' || !!m.forfeit_team_id,
    forfeit_team_id: m.forfeit_team_id || m.away_team_id,
    rubbers,
  })
  ttTeamMatchDialog.value = true
}

async function saveTtTeamMatch() {
  try {
    let payload: any = {
      court_venue: ttTeamMatchForm.court_venue,
      match_time: ttTeamMatchForm.match_time,
      notes: ttTeamMatchForm.notes,
    }
    if (ttTeamMatchForm.is_forfeit) {
      payload.is_forfeit = true
      payload.forfeit_team_id = ttTeamMatchForm.forfeit_team_id
    } else {
      const rubbers = ttTeamMatchForm.rubbers.map((r: any) => {
        const s = [
          { home: Number(r.set1_home), away: Number(r.set1_away) },
          { home: Number(r.set2_home), away: Number(r.set2_away) },
        ]
        if (r.need_third_set) {
          s.push({ home: Number(r.set3_home), away: Number(r.set3_away) })
        }
        let hWins = 0
        let aWins = 0
        s.forEach(st => {
          if (st.home > st.away) hWins++
          else if (st.away > st.home) aWins++
        })
        return {
          order: r.order,
          type: r.type,
          name: r.name,
          home_player_name: r.home_player_name,
          away_player_name: r.away_player_name,
          home_score: hWins,
          away_score: aWins,
          sets: s,
        }
      })
      payload.team_rubber_detail = rubbers
    }
    await api.put(`/sports-teacher/table-tennis/team/matches/${ttTeamMatchForm.id}`, payload)
    ElMessage.success('混合团体赛比分已录入，打满五盘积分榜已更新（胜2分，负1分，弃权0分）')
    ttTeamMatchDialog.value = false
    await loadTableTennisData()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

async function advanceTtTeamToFinals() {
  if (!ttTeamEventId.value) return
  try {
    const { data } = await api.post('/sports-teacher/table-tennis/team/advance-to-finals', { event_id: ttTeamEventId.value })
    ElMessage.success(data.message)
    await loadTableTennisData()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

async function generateTtTeamFinals() {
  if (!ttTeamEventId.value) return
  try {
    const { data } = await api.post('/sports-teacher/table-tennis/team/generate-finals', { event_id: ttTeamEventId.value })
    ElMessage.success(data.message)
    await loadTableTennisData()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

async function finalizeTtTeamResults() {
  if (!ttTeamEventId.value) return
  try {
    const { data } = await api.post('/sports-teacher/table-tennis/team/finalize-results', { event_id: ttTeamEventId.value })
    ElMessage.success(data.message)
    await loadTableTennisData()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

// 单打方法
function openAddTtSinglesAthletesDialog() {
  selectedTtAthleteIds.value = (ttSinglesAthletesData.athletes || []).map((a: any) => a.student_id)
  ttSinglesAddAthletesDialog.value = true
}

async function submitAddTtSinglesAthletes() {
  const currentId = ttCurrentSinglesEventId.value
  if (!currentId) return ElMessage.warning('请选择单打项目')
  if (!selectedTtAthleteIds.value.length) return ElMessage.warning('请至少选择一名参赛运动员')
  try {
    const { data } = await api.post('/sports-teacher/table-tennis/singles/add-athletes', {
      event_id: currentId,
      student_ids: selectedTtAthleteIds.value,
    })
    ElMessage.success(data.message)
    ttSinglesAddAthletesDialog.value = false
    await loadTableTennisData()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

async function autoGenerateTtSinglesDraw() {
  const currentId = ttCurrentSinglesEventId.value
  if (!currentId) return ElMessage.warning('请选择单打比赛项目')
  try {
    const { data } = await api.post('/sports-teacher/table-tennis/singles/draw', { event_id: currentId })
    ElMessage.success(data.message)
    await loadTableTennisData()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

function openEditTtSinglesMatch(m: any) {
  const sets = m.sets_detail || []
  const bestOf = m.best_of || 3
  const targetCount = bestOf === 5 ? 5 : 3
  const formSets = []
  for (let i = 0; i < targetCount; i++) {
    const st = sets[i] || { home: i < (bestOf === 5 ? 3 : 2) ? 11 : 0, away: i < (bestOf === 5 ? 3 : 2) ? (i === 1 ? 11 : 8) : 0 }
    formSets.push({ set: i + 1, home: st.home !== undefined ? st.home : 11, away: st.away !== undefined ? st.away : 8 })
  }
  Object.assign(ttSinglesMatchForm, {
    id: m.id,
    home_student_name: m.home_student_name,
    away_student_name: m.away_student_name,
    home_college: m.home_college,
    away_college: m.away_college,
    home_student_id: m.home_student_id,
    away_student_id: m.away_student_id,
    best_of: bestOf,
    court_venue: m.court_venue || '乒乓球馆1号台',
    match_time: m.match_time || '',
    notes: m.notes || '',
    sets: formSets,
  })
  ttSinglesMatchDialog.value = true
}

async function saveTtSinglesMatch() {
  try {
    const payload = {
      court_venue: ttSinglesMatchForm.court_venue,
      match_time: ttSinglesMatchForm.match_time,
      notes: ttSinglesMatchForm.notes,
      sets_detail: ttSinglesMatchForm.sets.map((st: any) => ({
        set: st.set,
        home: Number(st.home),
        away: Number(st.away),
      })),
    }
    await api.put(`/sports-teacher/table-tennis/singles/matches/${ttSinglesMatchForm.id}`, payload)
    ElMessage.success('单打比赛比分已保存！')
    ttSinglesMatchDialog.value = false
    await loadTableTennisData()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

async function advanceTtSinglesNextRound(currentStage: string) {
  const currentId = ttCurrentSinglesEventId.value
  if (!currentId) return
  try {
    const { data } = await api.post('/sports-teacher/table-tennis/singles/advance-next-round', {
      event_id: currentId,
      current_stage: currentStage,
    })
    ElMessage.success(data.message)
    await loadTableTennisData()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

async function finalizeTtSinglesResults() {
  const currentId = ttCurrentSinglesEventId.value
  if (!currentId) return
  try {
    const { data } = await api.post('/sports-teacher/table-tennis/singles/finalize-results', { event_id: currentId })
    ElMessage.success(data.message)
    await loadTableTennisData()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

function formatDate(value: string) { return value ? new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(value)) : '—' }
function eventName(id: number | null | undefined) {
  if (id == null) return '未选择项目'
  return events.value.find(item => item.id === id)?.name || myEvents.value.find(item => item.event?.id === id)?.event?.name || `项目 #${id}`
}
function meetName(id: number | null | undefined) {
  const meet = meets.value.find(item => item.id === id)
  return meet ? `${meet.name}（${meet.edition}）` : `运动会 #${id}`
}
function userName(id: number) { return managers.value.find(item => item.id === id)?.display_name || `账号 #${id}` }
const tagType = (state: string) => ({ ACTIVE: 'success', FROZEN: 'danger', PUBLISHED: 'success', REVIEWED: 'primary', SUBMITTED: 'warning', RETURNED: 'danger', DRAFT: 'info', ENABLED: 'success', DISABLED: 'info' } as any)[state] || 'info'

async function loadBase() {
  const [settingRes, summaryRes] = await Promise.all([api.get('/public/settings'), api.get('/dashboard/summary')])
  Object.assign(settings, settingRes.data); Object.assign(summary, summaryRes.data)
}
async function loadActive() {
  loading.value = true
  try {
    if (active.value === 'accounts') { const { data } = await api.get('/developer/accounts', { params: { page_size: 100 } }); accounts.value = data.items; Object.assign(quotas, data.quotas) }
    if (active.value === 'settings') Object.assign(settings, (await api.get('/developer/settings')).data)
    if (active.value === 'events') { const [m,e] = await Promise.all([api.get('/sports-teacher/meets'), api.get('/sports-teacher/events')]); meets.value=m.data; events.value=e.data }
    if (active.value === 'rosters') await loadRosterData()
    if (active.value === 'basketball') await loadBasketballData()
    if (active.value === 'volleyball') await loadVolleyballData()
    if (active.value === 'table-tennis') await loadTableTennisData()
    if (active.value === 'rope') await loadRopeData()
    if (active.value === 'models') scoringModels.value = (await api.get('/sports-teacher/scoring-models')).data
    if (active.value === 'permissions') { const [p,e,m] = await Promise.all([api.get('/sports-teacher/permissions'),api.get('/sports-teacher/events'),api.get('/sports-teacher/managers')]); permissions.value=p.data; events.value=e.data; managers.value=m.data }
    if (active.value === 'my-events') myEvents.value = (await api.get('/admin/my-events')).data
    if (active.value === 'schedules') { schedules.value=(await api.get('/admin/schedules')).data; await ensureEvents() }
    if (active.value === 'results') { await ensureEvents(); if (!selectedEventId.value) selectedEventId.value = availableEvents.value[0]?.id || null; await loadResults() }
    if (active.value === 'logs') logs.value=(await api.get('/developer/audit-logs')).data.items
    if (active.value.startsWith('student') || (active.value==='overview' && role.value==='STUDENT')) { const [p,e,r]=await Promise.all([api.get('/student/me'),api.get('/student/my-events'),api.get('/student/my-results')]); Object.assign(studentProfile,p.data);studentEvents.value=e.data;studentResults.value=r.data }
  } catch(error) { ElMessage.error(errorMessage(error)) } finally { loading.value=false }
}
async function ensureEvents() {
  if (canCreateBusiness.value) {
    if (!meets.value.length) meets.value = (await api.get('/sports-teacher/meets')).data
    if (!events.value.length) events.value = (await api.get('/sports-teacher/events')).data
  } else {
    if (!meets.value.length) meets.value = (await api.get('/sports-teacher/meets').catch(() => ({ data: [] }))).data
    if (!myEvents.value.length) myEvents.value = (await api.get('/admin/my-events')).data
  }
  if (!selectedMeetId.value && meets.value.length) {
    selectedMeetId.value = meets.value[0].id
  }
  if (!teamMeetId.value && meets.value.length) {
    teamMeetId.value = meets.value[0].id
  }
}
const availableEvents = computed(() => canCreateBusiness.value ? events.value : myEvents.value.map(item=>item.event))
const schedulableEvents = computed(() => canCreateBusiness.value ? events.value : myEvents.value.filter(item=>item.permissions?.can_schedule).map(item=>item.event))
const canScheduleAny = computed(() => schedulableEvents.value.length > 0)
function canScheduleEvent(eventId:number){return canCreateBusiness.value||!!myEvents.value.find(item=>item.event?.id===eventId)?.permissions?.can_schedule}
const selectedEvent = computed(() => availableEvents.value.find(item => item.id === selectedEventId.value))
const selectedIsTeam = computed(() => ['TEAM','RELAY'].includes(selectedEvent.value?.event_type))
const selectedAssignment = computed(() => myEvents.value.find(item => item.event?.id === selectedEventId.value))
const canScoreSelected = computed(() => canCreateBusiness.value || !!selectedAssignment.value?.permissions?.can_score)
const canReviewSelected = computed(() => canCreateBusiness.value || !!selectedAssignment.value?.permissions?.can_review)
const canExportSelected = computed(() => canCreateBusiness.value || !!selectedAssignment.value?.permissions?.can_export)
const rosterEvent = computed(() => events.value.find(item => item.id === eventRosterEventId.value))
const rosterIsTeam = computed(() => ['TEAM','RELAY'].includes(rosterEvent.value?.event_type))
const eventTypeLabel: Record<string,string> = { INDIVIDUAL: '个人项目', RELAY: '接力项目', TEAM: '团体项目' }
const genderLabel: Record<string,string> = { MALE: '男子组', FEMALE: '女子组', MIXED: '混合组' }
const stageLabel: Record<string,string> = { HEAT: '初赛', SEMIFINAL: '晋级赛', FINAL: '决赛' }
const resultStateLabel: Record<string,string> = { DRAFT: '草稿', SUBMITTED: '待审核', REVIEWED: '已审核', RETURNED: '已退回', PUBLISHED: '已发布' }
const competitionStatusLabel: Record<string,string> = { NORMAL: '正常完赛', DNS: '未出赛', DNF: '未完赛', DQ: '取消资格', NM: '无有效成绩' }
const registrationStatusLabel: Record<string,string> = { REGISTERED: '已报名', CHECKED_IN: '已检录', ALTERNATE: '候补', ABSENT: '缺席', WITHDRAWN: '退赛' }
const meetStatusLabel: Record<string,string> = { PREPARING: '筹备中', REGISTRATION: '报名中', COMPETING: '比赛中', FINISHED: '已结束' }
const scheduleStatusLabel: Record<string,string> = { NOT_STARTED: '未开始', CHECK_IN: '检录中', IN_PROGRESS: '进行中', COMPLETED: '已完成', CANCELLED: '已取消' }
const resultRegistrations = computed(() => registrations.value.filter(item => item.round_id === resultForm.round_id && !['WITHDRAWN','ABSENT','ALTERNATE'].includes(item.status)))

const eventsForTeamMeet = computed(() => {
  return events.value.filter((e: any) => !teamMeetId.value || e.meet_id === teamMeetId.value)
})

const distinctColleges = computed(() => {
  const defaults = ['信息工程学院', '机电工程学院', '外国语学院', '食品工程学院', '艺术设计学院', '建筑工程学院', '人文学院', '经济管理学院']
  try {
    const configured = JSON.parse(settings.participating_colleges || 'null')
    if (Array.isArray(configured) && configured.every((college: any) => typeof college === 'string')) return configured
  } catch { /* 使用学校默认学院 */ }
  return defaults
})

const filteredCollegeTeams = computed(() => {
  return collegeTeams.value.filter((t: any) => {
    if (teamMeetId.value && t.meet_id !== teamMeetId.value) return false
    if (teamEventFilterId.value === -1) {
      if (t.event_id) return false
    } else if (teamEventFilterId.value) {
      if (t.event_id !== teamEventFilterId.value) return false
    }
    if (teamSearchKeyword.value) {
      const kw = teamSearchKeyword.value.trim().toLowerCase()
      const matchCollege = (t.college || '').toLowerCase().includes(kw)
      const matchName = (t.team_name || '').toLowerCase().includes(kw)
      const matchLeader = (t.leader_name || '').toLowerCase().includes(kw)
      if (!matchCollege && !matchName && !matchLeader) return false
    }
    return true
  })
})

async function loadCollegeTeams() {
  const params: any = {}
  if (teamMeetId.value) params.meet_id = teamMeetId.value
  if (teamEventFilterId.value && teamEventFilterId.value !== -1) params.event_id = teamEventFilterId.value
  const res = await api.get('/sports-teacher/college-teams', { params })
  collegeTeams.value = res.data
}
async function loadEventRoster() {
  if (!eventRosterEventId.value) { eventRosterItems.value=[];eventRosterCandidates.value=[];return }
  const { data } = await api.get('/sports-teacher/event-registrations', { params: { event_id: eventRosterEventId.value, round_id: eventRosterRoundId.value || undefined } })
  eventRosterRounds.value = data.rounds
  if (eventRosterRoundId.value !== data.selected_round_id) eventRosterRoundId.value = data.selected_round_id
  eventRosterItems.value = data.items; eventRosterCandidates.value = data.candidates
}
async function loadRosterData() {
  const [meetRes, eventRes, studentRes] = await Promise.all([api.get('/sports-teacher/meets'), api.get('/sports-teacher/events'), api.get('/sports-teacher/students', { params: { page_size: 500 } })])
  meets.value = meetRes.data; events.value = eventRes.data; students.value = studentRes.data.items
  if (!teamMeetId.value && meets.value.length) teamMeetId.value = meets.value[0].id
  if (!eventRosterEventId.value && events.value.length) eventRosterEventId.value = events.value[0].id
  await Promise.all([loadCollegeTeams(), loadEventRoster()])
}

function openCreateAccount(){accountEditingId.value=null;Object.assign(accountForm,{username:'',display_name:'',password:'',role:'SCORER',department:'体育部',employee_no:'',phone:''});accountDialog.value=true}
function openEditAccount(row:any){accountEditingId.value=row.id;Object.assign(accountForm,{username:row.username,display_name:row.display_name,password:'',role:row.role,department:row.department||'',employee_no:row.employee_no||'',phone:row.phone||''});accountDialog.value=true}
async function saveAccount() { try { const payload={...accountForm};if(!accountEditingId.value&&payload.role==='STUDENT')payload.password=`DF${payload.username}`;if(!payload.password)delete payload.password;if(accountEditingId.value)await api.put(`/developer/accounts/${accountEditingId.value}`,payload);else await api.post('/developer/accounts',payload);ElMessage.success(accountEditingId.value?'账号修改成功':'账号创建成功');accountDialog.value=false;loadActive() } catch(e){ElMessage.error(errorMessage(e))} }
async function toggleFreeze(row:any) { try { if(row.status==='ACTIVE'){ const {value}=await ElMessageBox.prompt('请填写冻结原因','冻结账号',{inputPlaceholder:'例如：岗位调整'});await api.post(`/developer/accounts/${row.id}/freeze`,{reason:value}) } else await api.post(`/developer/accounts/${row.id}/unfreeze`);ElMessage.success('账号状态已更新');loadActive() } catch(e:any){if(e!=='cancel')ElMessage.error(errorMessage(e))} }
async function forceLogout(row:any) { try { await api.post(`/developer/accounts/${row.id}/force-logout`);ElMessage.success('已强制退出') } catch(e){ElMessage.error(errorMessage(e))} }
async function resetAccountPassword(row:any){try{if(row.role==='STUDENT'){await ElMessageBox.confirm('恢复为 DF + 完整学号。','重置密码');await api.post(`/developer/accounts/${row.id}/reset-password`,{})}else{const {value}=await ElMessageBox.prompt('输入至少8位新密码','重置密码',{inputType:'password',inputValidator:(v)=>v.length>=8||'密码至少8位'});await api.post(`/developer/accounts/${row.id}/reset-password`,{password:value})}ElMessage.success('密码已重置')}catch(e:any){if(e!=='cancel')ElMessage.error(errorMessage(e))}}
async function saveSettings() { try { const values={system_name:settings.system_name,short_name:settings.short_name,logo_text:settings.logo_text,primary_color:settings.primary_color,login_heading:settings.login_heading,results_page_name:settings.results_page_name,footer:settings.footer};await api.put('/developer/settings',{values});ElMessage.success('系统配置已保存') } catch(e){ElMessage.error(errorMessage(e))} }
function openMeetEditor(row?:any){const editing=!!row?.id;meetEditingId.value=editing?row.id:null;Object.assign(meetForm,editing?{name:row.name,edition:row.edition,start_date:row.start_date,end_date:row.end_date,status:row.status,public_visible:row.public_visible}:{name:'',edition:String(new Date().getFullYear()),start_date:'',end_date:'',status:'PREPARING',public_visible:true});meetDialog.value=true}
async function saveMeet() {
  const payload = { ...meetForm, name: String(meetForm.name || '').trim(), edition: String(meetForm.edition || '').trim() }
  if (!payload.name || !payload.edition || !payload.start_date || !payload.end_date) return ElMessage.warning('请完整填写运动会名称、年度/届次和比赛日期')
  if (payload.end_date < payload.start_date) return ElMessage.warning('结束日期不能早于开始日期')
  if (meetSaving.value) return
  meetSaving.value = true
  try {
    const { data } = meetEditingId.value
      ? await api.put(`/sports-teacher/meets/${meetEditingId.value}`, payload)
      : await api.post('/sports-teacher/meets', payload)
    selectedMeetId.value = data.id
    ElMessage.success(meetEditingId.value ? '运动会已更新' : '运动会已创建；现在可以为它添加比赛项目')
    meetDialog.value = false
    await loadActive()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  } finally {
    meetSaving.value = false
  }
}
async function deleteMeet(row:any){try{await ElMessageBox.confirm(`确定删除“${row.name} ${row.edition}”吗？`,'删除运动会',{type:'warning'});await api.delete(`/sports-teacher/meets/${row.id}`);ElMessage.success('已删除');loadActive()}catch(e:any){if(e!=='cancel')ElMessage.error(errorMessage(e))}}
function openEventEditor(row?:any){const editing=!!row?.id;eventEditingId.value=editing?row.id:null;Object.assign(eventForm,editing?{meet_id:row.meet_id,code:row.code,name:row.name,gender_group:row.gender_group,participant_group:row.participant_group,event_type:row.event_type,result_unit:row.result_unit,sort_direction:row.sort_direction,stage:row.stage,qualification_count:row.qualification_count,scoring_places:row.scoring_places,points_multiplier:row.points_multiplier}:{meet_id:selectedMeetId.value||meets.value[0]?.id||null,code:'',name:'',gender_group:'MALE',participant_group:'STUDENT',event_type:'INDIVIDUAL',result_unit:'秒',sort_direction:'ASC',stage:'FINAL',qualification_count:8,scoring_places:8,points_multiplier:1});eventDialog.value=true}
async function saveEvent() {
  const payload = { ...eventForm, code: String(eventForm.code || '').trim(), name: String(eventForm.name || '').trim() }
  if (!payload.meet_id || !payload.code || !payload.name) return ElMessage.warning('请选择所属运动会并填写项目编号和项目名称')
  if (eventSaving.value) return
  eventSaving.value = true
  try {
    if (eventEditingId.value) await api.put(`/sports-teacher/events/${eventEditingId.value}`, payload)
    else await api.post('/sports-teacher/events', payload)
    Object.assign(eventForm, { code: payload.code, name: payload.name })
    ElMessage.success(eventEditingId.value ? '比赛项目已更新' : '比赛项目已创建')
    eventDialog.value = false
    await loadActive()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  } finally {
    eventSaving.value = false
  }
}
async function deleteEvent(row:any){try{await ElMessageBox.confirm(`确定删除项目“${row.name}”吗？`,'删除比赛项目',{type:'warning'});await api.delete(`/sports-teacher/events/${row.id}`);ElMessage.success('已删除');loadActive()}catch(e:any){if(e!=='cancel')ElMessage.error(errorMessage(e))}}
async function importRoster(options:any) {
  if (rosterImporting.value) return
  rosterImporting.value = true
  const formData = new FormData()
  formData.append('file', options.file)
  const endpoint = role.value === 'DEVELOPER' ? '/developer/students/import' : '/sports-teacher/students/import'
  try {
    const { data } = await api.post(endpoint, formData, { timeout: role.value === 'DEVELOPER' ? 0 : 15000 })
    ElMessage.success(role.value === 'DEVELOPER'
      ? `新增资料 ${data.created} 人，注册账号 ${data.registered} 个，跳过已注册或重复记录 ${data.skipped} 条`
      : `导入完成：新增 ${data.created} 人，跳过 ${data.skipped} 条`)
    options.onSuccess(data)
    await loadActive()
  } catch(e) {
    ElMessage.error(errorMessage(e))
    options.onError(e)
  } finally {
    rosterImporting.value = false
  }
}
async function downloadRosterTemplate() {
  try {
    const endpoint = role.value === 'DEVELOPER' ? '/developer/students/template' : '/sports-teacher/students/template'
    const response = await api.get(endpoint, { responseType: 'blob' })
    const url = URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = url
    link.download = role.value === 'DEVELOPER' ? '学生账号花名册模板.xlsx' : '学生参赛名单模板.xlsx'
    link.click()
    URL.revokeObjectURL(url)
  } catch(e) { ElMessage.error(errorMessage(e)) }
}
function openStudentRoster(row?:any){const editing=!!row?.id;studentRosterEditingId.value=editing?row.id:null;Object.assign(studentRosterForm,editing?{student_no:row.student_no,name:row.name,gender:row.gender,college:row.college,major:row.major,class_name:row.class_name}:{student_no:'',name:'',gender:'男',college:'',major:'',class_name:''});studentRosterDialog.value=true}
async function saveStudentRoster(){
  if (!studentRosterForm.student_no || !studentRosterForm.name || !studentRosterForm.college || !studentRosterForm.major || !studentRosterForm.class_name) return ElMessage.warning('请完整填写学号、姓名、学院、专业和班级')
  try{if(studentRosterEditingId.value)await api.put(`/sports-teacher/students/${studentRosterEditingId.value}`,studentRosterForm);else await api.post('/sports-teacher/students',studentRosterForm);ElMessage.success('学生资料已更新');studentRosterDialog.value=false;await loadRosterData()}catch(e){ElMessage.error(errorMessage(e))}
}
async function deleteStudentRoster(row:any){try{await ElMessageBox.confirm(`确定删除学生“${row.name}”吗？`,'删除学生',{type:'warning'});await api.delete(`/sports-teacher/students/${row.id}`);ElMessage.success('已删除');await loadRosterData()}catch(e:any){if(e!=='cancel')ElMessage.error(errorMessage(e))}}

function openCollegeTeam(row?:any){
  const editing = !!row?.id
  collegeTeamEditingId.value = editing ? row.id : null
  const defaultEventId = (teamEventFilterId.value && teamEventFilterId.value !== -1) ? teamEventFilterId.value : null
  Object.assign(collegeTeamForm, editing ? {
    meet_id: row.meet_id,
    event_id: row.event_id || null,
    college: row.college,
    team_name: row.team_name || '',
    leader_name: row.leader_name || '',
    leader_phone: row.leader_phone || '',
    notes: row.notes || '',
  } : {
    meet_id: teamMeetId.value || selectedMeetId.value || (meets.value[0]?.id || null),
    event_id: defaultEventId,
    college: '',
    team_name: '',
    leader_name: '',
    leader_phone: '',
    notes: '',
  })
  collegeTeamDialog.value = true
}

function onCollegeTeamCollegeOrEventChange() {
  if (!collegeTeamEditingId.value) {
    const selectedEv = events.value.find((e: any) => e.id === collegeTeamForm.event_id)
    const suffix = selectedEv ? `${selectedEv.name}队` : '代表队'
    if (collegeTeamForm.college) {
      collegeTeamForm.team_name = `${collegeTeamForm.college}${suffix}`
    }
  }
}

async function saveCollegeTeam(){
  if (!collegeTeamForm.meet_id) return ElMessage.warning('请选择所属运动会')
  if (!collegeTeamForm.college) return ElMessage.warning('请选择或填写学院名称')
  try{
    if(collegeTeamEditingId.value) await api.put(`/sports-teacher/college-teams/${collegeTeamEditingId.value}`,collegeTeamForm);
    else await api.post('/sports-teacher/college-teams',collegeTeamForm);
    ElMessage.success(collegeTeamEditingId.value ? '代表队信息已更新' : '代表队已成功创建');
    collegeTeamDialog.value=false;
    teamMeetId.value=collegeTeamForm.meet_id;
    await loadCollegeTeams()
  }catch(e){ElMessage.error(errorMessage(e))}
}

async function deleteCollegeTeam(row:any){
  try{
    await ElMessageBox.confirm(`确定删除代表队“${row.team_name}”吗？`,'删除代表队',{type:'warning'});
    await api.delete(`/sports-teacher/college-teams/${row.id}`);
    ElMessage.success('已删除');
    await loadCollegeTeams()
  }catch(e:any){if(e!=='cancel')ElMessage.error(errorMessage(e))}
}

async function generateCollegeTeams(){
  if(!teamMeetId.value) return ElMessage.warning('请选择运动会届次')
  const targetEventId = (teamEventFilterId.value && teamEventFilterId.value !== -1) ? teamEventFilterId.value : null
  const targetEvent = events.value.find((e: any) => e.id === targetEventId)
  const tip = targetEvent ? `【${targetEvent.name}】` : '本届运动会'
  try{
    const {data}=await api.post('/sports-teacher/college-teams/generate',{meet_id:teamMeetId.value, event_id: targetEventId});
    ElMessage.success(data.message || `成功为${tip}批量生成学院代表队！`);
    await loadCollegeTeams()
  }catch(e){ElMessage.error(errorMessage(e))}
}
function openRegistrationDialog(){if(!eventRosterEventId.value)return ElMessage.warning('请先选择比赛项目');registrationParticipantIds.value=[];Object.assign(registrationBatchForm,{heat:'第1组',status:'REGISTERED'});registrationDialog.value=true}
async function addEventRegistrations(){if(!registrationParticipantIds.value.length)return ElMessage.warning('请选择参赛对象');try{const {data}=await api.post('/sports-teacher/event-registrations/batch',{event_id:eventRosterEventId.value,round_id:eventRosterRoundId.value,participant_ids:registrationParticipantIds.value,...registrationBatchForm});ElMessage.success(`已加入 ${data.created} 项`);registrationDialog.value=false;await loadEventRoster()}catch(e){ElMessage.error(errorMessage(e))}}
function openRegistrationEditor(row:any){Object.assign(registrationEditForm,{id:row.id,bib_no:row.bib_no||'',heat:row.heat||'',lane:row.lane||'',status:row.status});registrationEditDialog.value=true}
async function updateEventRegistration(){try{const payload={bib_no:registrationEditForm.bib_no,heat:registrationEditForm.heat,lane:registrationEditForm.lane,status:registrationEditForm.status};await api.put(`/sports-teacher/event-registrations/${registrationEditForm.id}`,payload);ElMessage.success('参赛信息已更新');registrationEditDialog.value=false;await loadEventRoster()}catch(e){ElMessage.error(errorMessage(e))}}
async function removeEventRegistration(row:any){try{await ElMessageBox.confirm(`从该项目名单中移除“${row.participant.name}”？`,'移除参赛者',{type:'warning'});await api.delete(`/sports-teacher/event-registrations/${row.id}`);ElMessage.success('已移除');await loadEventRoster()}catch(e){ElMessage.error(errorMessage(e))}}
async function autoSeedRoster(){if(!eventRosterEventId.value||!eventRosterRoundId.value)return;try{const {value}=await ElMessageBox.prompt('每组道次数（2—12）','自动分组排道',{inputValue:'8',inputValidator:(v)=>Number(v)>=2&&Number(v)<=12||'请输入2—12'});const {data}=await api.post('/sports-teacher/event-registrations/seed',{event_id:eventRosterEventId.value,round_id:eventRosterRoundId.value,lanes_per_heat:Number(value)});ElMessage.success(data.message);await loadEventRoster()}catch(e:any){if(e!=='cancel')ElMessage.error(errorMessage(e))}}
async function advanceRoster() {
  const current = eventRosterRounds.value.find((r: any) => r.id === eventRosterRoundId.value)
  const currentSeq = Number((current as any)?.sequence || 0)
  const next = eventRosterRounds.value.find((r: any) => Number((r as any).sequence) === currentSeq + 1)
  if (!next) return ElMessage.warning('决赛之后没有下一轮')
  try {
    const first = await ElMessageBox.prompt(`根据本轮名次，生成${next.name}晋级名单。请输入晋级人数：`,'晋级名单',{inputValue:String(rosterEvent.value?.qualification_count||8),inputValidator:(v)=>Number(v)>0||'大于0'})
    const { data } = await api.post('/sports-teacher/event-registrations/advance', { event_id: eventRosterEventId.value, from_round_id: eventRosterRoundId.value, to_round_id: next.id, count: Number(first.value), alternates: 0 })
    ElMessage.success(data.message); eventRosterRoundId.value = next.id; await loadEventRoster()
  } catch (e: any) { if (e !== 'cancel') ElMessage.error(errorMessage(e)) }
}
async function exportRoster(){if(!eventRosterEventId.value||!eventRosterRoundId.value)return;try{const response=await api.get('/sports-teacher/event-registrations/export',{params:{event_id:eventRosterEventId.value,round_id:eventRosterRoundId.value},responseType:'blob'});const url=URL.createObjectURL(response.data);const a=document.createElement('a');a.href=url;a.download=`${rosterEvent.value?.name}_分组表.xlsx`;a.click();URL.revokeObjectURL(url)}catch(e){ElMessage.error(errorMessage(e))}}
function openModelEditor(row?:any){const editing=!!row?.id;modelEditingId.value=editing?row.id:null;Object.assign(modelForm,editing?{name:row.name,description:row.description||'',places:row.points.length,pointsText:row.points.join(','),individual_multiplier:row.individual_multiplier,relay_multiplier:row.relay_multiplier,team_multiplier:row.team_multiplier,status:row.status}:{name:'',description:'',places:8,pointsText:'9,7,6,5,4,3,2,1',individual_multiplier:1,relay_multiplier:2,team_multiplier:2,status:'DRAFT'});modelDialog.value=true}
async function saveModel() { try { const points=modelForm.pointsText.split(',').map((item:string)=>Number(item.trim()));const payload={...modelForm,places:points.length,points,pointsText:undefined};if(modelEditingId.value)await api.put(`/sports-teacher/scoring-models/${modelEditingId.value}`,payload);else await api.post('/sports-teacher/scoring-models',payload);ElMessage.success('计分模型已保存');modelDialog.value=false;loadActive() } catch(e){ElMessage.error(errorMessage(e))} }
async function deleteModel(row:any){try{await ElMessageBox.confirm(`确定删除“${row.name}”吗？`,'删除计分模型',{type:'warning'});await api.delete(`/sports-teacher/scoring-models/${row.id}`);ElMessage.success('已删除');loadActive()}catch(e:any){if(e!=='cancel')ElMessage.error(errorMessage(e))}}
async function copyModel(row:any) { try { await api.post(`/sports-teacher/scoring-models/${row.id}/copy`);ElMessage.success('已复制版本');loadActive() }catch(e){ElMessage.error(errorMessage(e))} }
async function toggleModel(row:any) { try { await api.post(`/sports-teacher/scoring-models/${row.id}/enable`);ElMessage.success('模型状态已更新');loadActive() }catch(e){ElMessage.error(errorMessage(e))} }
async function savePermission() { try { await api.put('/sports-teacher/permissions',permissionForm);ElMessage.success('权限已保存');permissionDialog.value=false;loadActive() }catch(e){ElMessage.error(errorMessage(e))} }
function openPermissionEditor(row?:any){const editing=!!row?.id;permissionEditingId.value=editing?row.id:null;Object.assign(permissionForm,editing?{user_id:row.user_id,event_id:row.event_id,can_schedule:row.can_schedule,can_score:row.can_score,can_review:row.can_review,can_export:row.can_export}:{user_id:null,event_id:null,can_schedule:false,can_score:false,can_review:false,can_export:false});permissionDialog.value=true}
async function deletePermission(row:any){try{await ElMessageBox.confirm('确定删除此条操作权限？','删除权限',{type:'warning'});await api.delete(`/sports-teacher/permissions/${row.id}`);ElMessage.success('已删除');loadActive()}catch(e:any){if(e!=='cancel')ElMessage.error(errorMessage(e))}}
async function loadScheduleRounds(){if(!scheduleForm.event_id){scheduleRounds.value=[];return}try{scheduleRounds.value=(await api.get('/admin/registrations',{params:{event_id:scheduleForm.event_id}})).data.rounds;if(!scheduleRounds.value.some(r=>r.id===scheduleForm.round_id))scheduleForm.round_id=scheduleRounds.value[0]?.id||null}catch(e){ElMessage.error(errorMessage(e))}}
async function openScheduleDialog(row?:any){if(!schedulableEvents.value.length)return ElMessage.warning('暂无可管理赛程的项目');const editing=!!row?.id;scheduleEditingId.value=editing?row.id:null;Object.assign(scheduleForm,editing?{event_id:row.event_id,round_id:row.round_id,competition_at:row.competition_at,check_in_at:row.check_in_at||'',venue:row.venue,heat:row.heat||'',notes:row.notes||'',status:row.status,published:row.published}:{event_id:schedulableEvents.value[0].id,round_id:null,competition_at:'',check_in_at:'',venue:'',heat:'',notes:'',status:'NOT_STARTED',published:true});await loadScheduleRounds();scheduleDialog.value=true}
async function saveSchedule() {
  if (!scheduleForm.event_id || !scheduleForm.round_id || !scheduleForm.competition_at || !scheduleForm.venue) return ElMessage.warning('请选择项目、轮次、比赛时间并填写场地')
  if (scheduleForm.check_in_at && scheduleForm.check_in_at > scheduleForm.competition_at) return ElMessage.warning('检录时间不能晚于比赛时间')
  try { if(scheduleEditingId.value)await api.put(`/admin/schedules/${scheduleEditingId.value}`,scheduleForm);else await api.post('/admin/schedules',scheduleForm);ElMessage.success('赛程已保存');scheduleDialog.value=false;loadActive() }catch(e){ElMessage.error(errorMessage(e))}
}
async function deleteSchedule(row:any){try{await ElMessageBox.confirm(`确定删除“${eventName(row.event_id)}”赛程？`,'删除赛程',{type:'warning'});await api.delete(`/admin/schedules/${row.id}`);ElMessage.success('已删除');loadActive()}catch(e:any){if(e!=='cancel')ElMessage.error(errorMessage(e))}}
async function loadResults() {
  if (!selectedEventId.value) { results.value=[]; return }
  try {
    const reg = (await api.get('/admin/registrations', { params: { event_id: selectedEventId.value } })).data
    registrations.value = reg.items
    rounds.value = reg.rounds
    if (!selectedResultRoundId.value || !rounds.value.some(r => r.id === selectedResultRoundId.value)) {
      const selected = events.value.find((event: any) => event.id === selectedEventId.value)
      const preferred = selected?.code?.startsWith('ROPE_') ? rounds.value.find((round: any) => round.stage === 'FINAL') : rounds.value[0]
      selectedResultRoundId.value = preferred?.id || null
    }
    results.value = (await api.get('/admin/results', { params: { event_id: selectedEventId.value, round_id: selectedResultRoundId.value || undefined } })).data
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

// 🪢 跳绳团体赛制
const ropeData = reactive<any>({ meet: null, events: [] })
const ropeEventId = ref<number | null>(null)
const ropeLineupDialog = ref(false)
const ropeLineupSaving = ref(false)
const ropeLineupTeam = ref<any>(null)
const ropeLineupForm = reactive<any>({ event_id: null, college_team_id: null, jumper_ids: [], turner_ids: [] })
const selectedRopeEvent = computed(() => ropeData.events.find((event: any) => event.id === ropeEventId.value) || ropeData.events[0] || null)
const ropeLineupMembers = computed(() => ropeLineupTeam.value?.members || [])
const ropeEntryJumpers = computed(() => {
  const team = ropeData.events.find((event: any) => event.id === resultForm.event_id)?.teams.find((item: any) => item.registration_id === resultForm.registration_id)
  return (team?.lineup || []).filter((member: any) => member.role === 'JUMPER')
    .sort((a: any, b: any) => Number(a.gender !== '男') - Number(b.gender !== '男') || a.sequence - b.sequence)
})

async function loadRopeData() {
  await ensureEvents()
  if (!canCreateBusiness.value) {
    meets.value = (await api.get('/admin/rope/meets')).data
    if (!meets.value.some((meet: any) => meet.id === selectedMeetId.value)) selectedMeetId.value = meets.value[0]?.id || null
  }
  if (!selectedMeetId.value && meets.value.length) selectedMeetId.value = meets.value[0].id
  if (!selectedMeetId.value) {
    Object.assign(ropeData, { meet: null, events: [] })
    return
  }
  const { data } = await api.get(canCreateBusiness.value ? '/sports-teacher/rope/status' : '/admin/rope/status', { params: { meet_id: selectedMeetId.value } })
  Object.assign(ropeData, data)
  if (!ropeEventId.value || !data.events.some((event: any) => event.id === ropeEventId.value)) {
    ropeEventId.value = data.events[0]?.id || null
  }
}

async function initializeRopeEvents() {
  if (!selectedMeetId.value) return ElMessage.warning('请先选择运动会')
  try {
    const { data } = await api.post('/sports-teacher/rope/initialize', { meet_id: selectedMeetId.value })
    events.value = (await api.get('/sports-teacher/events')).data
    ElMessage.success(data.message)
    await loadRopeData()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

function openRopeLineup(team: any) {
  if (!selectedRopeEvent.value) return
  ropeLineupTeam.value = team
  Object.assign(ropeLineupForm, {
    event_id: selectedRopeEvent.value.id,
    college_team_id: team.team_id,
    jumper_ids: team.lineup.filter((member: any) => member.role === 'JUMPER').sort((a: any, b: any) => a.sequence - b.sequence).map((member: any) => member.student_id),
    turner_ids: team.lineup.filter((member: any) => member.role === 'TURNER').sort((a: any, b: any) => a.sequence - b.sequence).map((member: any) => member.student_id),
  })
  ropeLineupDialog.value = true
}

async function saveRopeLineup() {
  if (ropeLineupSaving.value) return
  ropeLineupSaving.value = true
  try {
    const members = [
      ...ropeLineupForm.jumper_ids.map((studentId: number, index: number) => ({ student_id: studentId, role: 'JUMPER', sequence: index + 1 })),
      ...ropeLineupForm.turner_ids.map((studentId: number, index: number) => ({ student_id: studentId, role: 'TURNER', sequence: index + 1 })),
    ]
    const { data } = await api.put('/sports-teacher/rope/lineups', {
      event_id: ropeLineupForm.event_id,
      college_team_id: ropeLineupForm.college_team_id,
      members,
    })
    ElMessage.success(data.message)
    ropeLineupDialog.value = false
    await loadRopeData()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  } finally {
    ropeLineupSaving.value = false
  }
}

function goToRopeRoster() {
  teamMeetId.value = selectedMeetId.value
  rosterTab.value = 'team'
  active.value = 'rosters'
}

function goToRopeResults(event = selectedRopeEvent.value) {
  if (!event) return
  selectedEventId.value = event.id
  selectedResultRoundId.value = event.round_id
  active.value = 'results'
}

function ropeResultText(row: any) {
  const detail = row.rope_detail
  if (!detail) return `${row.raw_value ?? '—'} ${row.unit || ''}`
  if (row.event_code === 'ROPE_SYNC') {
    return detail.completed_target ? `完成30次 · ${detail.elapsed_seconds} 秒` : `未完成 · ${detail.completed_count} 次`
  }
  return `${detail.completed_count ?? row.raw_value} 次`
}

// 🪢 跳绳专用录入辅助数据
const ropeHelper = reactive({
  isRopeSingle: false,
  isRopeSync: false,
  isRopeFig8: false,
  maleScores: [0, 0, 0, 0, 0],
  femaleScores: [0, 0, 0, 0, 0],
  syncCompleted: true,
  syncTime: 0,
  syncCompletedCount: 0,
  fig8Count: 0,
})

const ropeSingleTotal = computed(() => {
  const mSum = ropeHelper.maleScores.reduce((a, b) => a + (Number(b) || 0), 0)
  const fSum = ropeHelper.femaleScores.reduce((a, b) => a + (Number(b) || 0), 0)
  return mSum + fSum
})

function applyRopeSingleTotal() {
  resultForm.raw_value = ropeSingleTotal.value
  const mList = ropeHelper.maleScores.map((v, i) => `男${i+1}:${v}`).join(',')
  const fList = ropeHelper.femaleScores.map((v, i) => `女${i+1}:${v}`).join(',')
  resultForm.notes = `前单跳 10人明细: [${mList}] [${fList}] | 10人总次数: ${ropeSingleTotal.value}次`
  ElMessage.success(`已自动计算并填入 10 人团体总次数: ${ropeSingleTotal.value} 次`)
}

function applyRopeSync() {
  if (ropeHelper.syncCompleted) {
    resultForm.raw_value = Number(ropeHelper.syncTime) || 30.0
    resultForm.notes = `5分钟内完成30次有效跳动，用时 ${resultForm.raw_value} 秒`
  } else {
    const done = Number(ropeHelper.syncCompletedCount) || 0
    resultForm.raw_value = Number((1000 + (30 - done)).toFixed(2))
    resultForm.notes = `5分钟未完成30次任务，实际完成有效跳动 ${done} 次`
  }
}

function openResultEntry(row?:any){
  const editing=!!row?.id;
  resultEditingId.value=editing?row.id:null;
  Object.assign(resultForm,editing?{event_id:row.event_id,round_id:row.round_id,registration_id:row.registration_id,raw_value:row.raw_value,competition_status:row.competition_status,notes:row.notes||'',modification_reason:'',published_at:row.published_at}:{event_id:selectedEventId.value,round_id:selectedResultRoundId.value||rounds.value[0]?.id||null,registration_id:null,raw_value:null,competition_status:'NORMAL',notes:'',modification_reason:'',published_at:null});
  
  // 检查是否属于跳绳项目
  const ev = availableEvents.value.find((e: any) => e.id === (row?.event_id || selectedEventId.value))
  ropeHelper.isRopeSingle = !!ev && (ev.code === 'ROPE_SINGLE' || ev.name.includes('前单跳'))
  ropeHelper.isRopeSync = !!ev && (ev.code === 'ROPE_SYNC' || ev.name.includes('集体单摇'))
  ropeHelper.isRopeFig8 = !!ev && (ev.code === 'ROPE_FIG8' || ev.name.includes('8') || ev.name.includes('环绕'))
  ropeHelper.maleScores = [0, 0, 0, 0, 0]
  ropeHelper.femaleScores = [0, 0, 0, 0, 0]
  ropeHelper.syncCompleted = true
  ropeHelper.syncTime = 0
  ropeHelper.syncCompletedCount = 0
  ropeHelper.fig8Count = 0
  const detail = row?.rope_detail
  if (ropeHelper.isRopeSingle && detail?.individual_counts?.length === 10) {
    ropeHelper.maleScores = detail.individual_counts.slice(0, 5).map(Number)
    ropeHelper.femaleScores = detail.individual_counts.slice(5, 10).map(Number)
  } else if (ropeHelper.isRopeSync && detail) {
    ropeHelper.syncCompleted = detail.completed_target !== false
    ropeHelper.syncTime = Number(detail.elapsed_seconds || 0)
    ropeHelper.syncCompletedCount = Number(detail.completed_count || 0)
  } else if (ropeHelper.isRopeSync && row?.raw_value) {
    ropeHelper.syncCompleted = Number(row.raw_value) < 1000
    ropeHelper.syncTime = ropeHelper.syncCompleted ? Number(row.raw_value) : 0
    ropeHelper.syncCompletedCount = ropeHelper.syncCompleted ? 30 : Math.max(0, 30 - Math.round(Number(row.raw_value) - 1000))
  } else if (ropeHelper.isRopeFig8) {
    ropeHelper.fig8Count = Number(detail?.completed_count ?? row?.raw_value ?? 0)
  }

  resultDialog.value=true
}
async function saveResult(){
  if (!resultForm.round_id) return ElMessage.warning('请选择比赛轮次')
  if (!resultForm.registration_id) return ElMessage.warning('请选择参赛队伍或运动员')
  try{
    if (ropeHelper.isRopeSingle || ropeHelper.isRopeSync || ropeHelper.isRopeFig8) {
      const payload: any = {
        event_id: resultForm.event_id,
        round_id: resultForm.round_id,
        registration_id: resultForm.registration_id,
        notes: resultForm.notes || null,
        modification_reason: resultForm.modification_reason || null,
      }
      if (ropeHelper.isRopeSingle) payload.individual_counts = [...ropeHelper.maleScores, ...ropeHelper.femaleScores].map(Number)
      if (ropeHelper.isRopeSync) {
        payload.completed_target = ropeHelper.syncCompleted
        if (ropeHelper.syncCompleted) payload.elapsed_seconds = Number(ropeHelper.syncTime)
        else payload.completed_count = Number(ropeHelper.syncCompletedCount)
      }
      if (ropeHelper.isRopeFig8) payload.completed_count = Number(ropeHelper.fig8Count)
      await api.put('/admin/rope/results', payload)
    } else {
      await api.put('/admin/results',resultForm)
    }
    ElMessage.success('成绩草稿已保存');
    resultDialog.value=false;
    loadResults()
  }catch(e){ElMessage.error(errorMessage(e))}
}
async function deleteResult(row:any){try{await ElMessageBox.confirm(`确定删除“${row.name}”的成绩草稿？`,'删除成绩',{type:'warning'});await api.delete(`/admin/results/${row.id}`);ElMessage.success('已删除');loadResults()}catch(e:any){if(e!=='cancel')ElMessage.error(errorMessage(e))}}
async function resultAction(action:'submit'|'review'|'publish'|'unpublish',approve=true){if(!selectedResultIds.value.length)return ElMessage.warning('请勾选成绩');try{const body={result_ids:selectedResultIds.value,approve,comment:approve?'审核通过':'退回修改'};if(action==='submit')await api.post('/admin/results/submit',body);if(action==='review')await api.post('/admin/results/review',body);if(action==='publish'){await api.post('/sports-teacher/results/final-review',body);await api.post('/sports-teacher/results/publish',body)}if(action==='unpublish'){await api.post('/sports-teacher/results/unpublish',body)}ElMessage.success(action==='unpublish'?'已成功从实时成绩大屏下架/撤回发布':'成绩流转成功');selectedResultIds.value=[];loadResults()}catch(e){ElMessage.error(errorMessage(e))}}
async function unpublishSingleResult(row:any){try{await ElMessageBox.confirm(`确定将“${row.name}”的已被发布成绩从实时成绩大屏下架吗？`,'下架成绩',{type:'warning'});await api.post('/sports-teacher/results/unpublish',{result_ids:[row.id],comment:'管理员下架单条成绩'});ElMessage.success('已从实时成绩大屏下架');loadResults()}catch(e:any){if(e!=='cancel')ElMessage.error(errorMessage(e))}}
async function exportResults(){if(!selectedEventId.value)return;try{const response=await api.get('/admin/results/export',{params:{event_id:selectedEventId.value},responseType:'blob'});const url=URL.createObjectURL(response.data);const a=document.createElement('a');a.href=url;a.download=`${eventName(selectedEventId.value)}_成绩单.xlsx`;a.click();URL.revokeObjectURL(url)}catch(e){ElMessage.error(errorMessage(e))}}
function logout(){auth.logout();router.push('/login')}
async function changePassword(){if(passwordForm.new_password!==passwordForm.confirm_password)return ElMessage.warning('两次密码输入不一致');try{await api.post('/auth/change-password',{current_password:passwordForm.current_password,new_password:passwordForm.new_password});ElMessage.success('密码修改成功');changePasswordDialog.value=false;logout()}catch(e){ElMessage.error(errorMessage(e))}}

function onResultSelectionChange(val: any[]) { selectedResultIds.value = val.map((item: any) => item.id) }
function onRegistrationSelectionChange(val: any[]) { registrationParticipantIds.value = val.map((item: any) => item.id) }

watch(active, loadActive)
watch(ttTab, () => { if (active.value === 'table-tennis') loadTableTennisData() })
watch(ttTeamEventId, () => { if (active.value === 'table-tennis' && ttTab.value === 'team') loadTableTennisData() })
watch(ttCurrentSinglesEventId, () => { if (active.value === 'table-tennis' && ttTab.value !== 'team') loadTableTennisData() })
watch(selectedEventId, ()=>{selectedResultRoundId.value=null;loadResults()})
watch(selectedResultRoundId, ()=>{if(active.value==='results')loadResults()})
watch(()=>resultForm.round_id, ()=>{if(!resultEditingId.value)resultForm.registration_id=null})
watch(teamMeetId, async()=>{if(active.value==='rosters'){try{await loadCollegeTeams()}catch(e){ElMessage.error(errorMessage(e))}}})
watch(eventRosterEventId, async()=>{eventRosterRoundId.value=null;if(active.value==='rosters'){try{await loadEventRoster()}catch(e){ElMessage.error(errorMessage(e))}}})
watch(eventRosterRoundId, async()=>{if(active.value==='rosters'&&eventRosterRoundId.value){try{await loadEventRoster()}catch(e){ElMessage.error(errorMessage(e))}}})
watch(()=>scheduleForm.event_id, ()=>{if(scheduleDialog.value)loadScheduleRounds()})
onMounted(async()=>{try{const me=(await api.get('/auth/me')).data;if(me.role!=='STUDENT'&&me.first_login_change_required)changePasswordDialog.value=true;await loadBase();await loadActive()}catch(e){ElMessage.error(errorMessage(e))}})
</script>

<template>
  <div class="apple-workspace">
    <!-- 高透毛玻璃侧边栏 -->
    <aside :class="['mac-sidebar', { collapsed }]">
      <!-- 窗口红黄绿三色控制点 -->
      <div class="mac-window-controls">
        <span class="mac-dot red"></span>
        <span class="mac-dot yellow"></span>
        <span class="mac-dot green"></span>
      </div>

      <div class="mac-brand">
        <div class="mac-app-icon">{{ settings.logo_text }}</div>
        <div v-if="!collapsed" class="mac-app-info">
          <b>{{ settings.short_name }}</b>
          <span>Sports Console</span>
        </div>
      </div>

      <div class="mac-section-title" v-if="!collapsed">Main Navigation</div>
      <nav class="mac-nav">
        <button 
          v-for="item in navItems" 
          :key="item.key" 
          :class="['mac-nav-item', { active: active === item.key }]" 
          @click="active = item.key"
        >
          <div :class="['sf-icon-box', item.color]">
            <el-icon><component :is="item.icon"/></el-icon>
          </div>
          <span v-if="!collapsed" class="mac-nav-label">{{ item.label }}</span>
        </button>
      </nav>

      <!-- 账户信息底部栏 -->
      <div class="mac-user-card" v-if="!collapsed">
        <div class="mac-user-avatar">{{ auth.user?.display_name?.slice(0,1) }}</div>
        <div class="mac-user-meta">
          <b>{{ auth.user?.display_name }}</b>
          <span>{{ roleLabel[role] }}</span>
        </div>
        <button class="mac-icon-btn" @click="logout" title="退出登录">
          <el-icon><SwitchButton/></el-icon>
        </button>
      </div>
    </aside>

    <!-- 主页面结构 -->
    <main class="mac-main-area">
      <!-- 悬浮顶栏 -->
      <header class="mac-top-bar">
        <div class="mac-bar-left">
          <button class="mac-toggle-btn" @click="collapsed = !collapsed">
            <el-icon><component :is="collapsed ? MenuIcon : Fold"/></el-icon>
          </button>
          <div>
            <h2>{{ pageTitle }}</h2>
            <p>{{ settings.system_name }}</p>
          </div>
        </div>
        <div class="mac-bar-right">
          <button class="mac-pill-btn ai-copilot-pill" @click="aiDrawerVisible = true">
            <el-icon><ChatDotRound/></el-icon> AI 赛事协同
          </button>
          <button class="mac-pill-btn" @click="router.push('/results')">
            <el-icon><View/></el-icon> 实时成绩大屏
          </button>
          <span class="mac-date-badge">{{ new Date().toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', weekday: 'short' }) }}</span>
        </div>
      </header>

      <!-- 工作区正文区域 -->
      <div class="mac-body" v-loading="loading">
        <!-- 1. 赛事概览页 -->
        <template v-if="active === 'overview'">
          <!-- 亲切富有活力的 Hello Banner -->
          <section class="apple-hello-banner">
            <div>
              <h1>Hello, {{ studentProfile.name || auth.user?.display_name }}</h1>
              <p>{{ role === 'STUDENT' ? `${studentProfile.college || ''} · ${studentProfile.class_name || ''}` : '欢迎进入校园运动会赛事成绩管理系统 · 全流程数据实时审核' }}</p>
            </div>
          </section>

          <!-- 四列统计卡片 -->
          <section class="apple-bento-grid">
            <template v-if="role === 'STUDENT'">
              <article class="apple-bento-card panel blue">
                <div class="bento-top">
                  <div class="sf-badge blue"><el-icon><Calendar/></el-icon></div>
                  <span class="apple-chip">SCHEDULE</span>
                </div>
                <div class="bento-number">{{ summary.registrations || 0 }}</div>
                <span class="bento-title">待参加场次</span>
                <small>按项目轮次即时排赛</small>
              </article>

              <article class="apple-bento-card panel orange">
                <div class="bento-top">
                  <div class="sf-badge orange"><el-icon><Trophy/></el-icon></div>
                  <span class="apple-chip orange">QUALIFIED</span>
                </div>
                <div class="bento-number">{{ summary.qualified || 0 }}</div>
                <span class="bento-title">已晋级场次</span>
                <small>决赛名单同步就绪</small>
              </article>

              <article class="apple-bento-card panel green">
                <div class="bento-top">
                  <div class="sf-badge green"><el-icon><Medal/></el-icon></div>
                  <span class="apple-chip green">RELEASED</span>
                </div>
                <div class="bento-number">{{ summary.published_results || 0 }}</div>
                <span class="bento-title">已公布成绩</span>
                <small>终审完结公开展现</small>
              </article>

              <article class="apple-bento-card panel purple">
                <div class="bento-top">
                  <div class="sf-badge purple"><el-icon><User/></el-icon></div>
                  <span class="apple-chip purple">ACTIVE</span>
                </div>
                <div class="bento-number" style="font-size:22px">正常</div>
                <span class="bento-title">账号状态</span>
                <small>学生权限正常使用中</small>
              </article>
            </template>
            <template v-else>
              <article class="apple-bento-card panel blue">
                <div class="bento-top">
                  <div class="sf-badge blue"><el-icon><Calendar/></el-icon></div>
                  <span class="apple-chip">MEETS</span>
                </div>
                <div class="bento-number">{{ summary.meets || 0 }}</div>
                <span class="bento-title">运动会届次</span>
                <small>历史数据全量保留</small>
              </article>

              <article class="apple-bento-card panel orange">
                <div class="bento-top">
                  <div class="sf-badge orange"><el-icon><Trophy/></el-icon></div>
                  <span class="apple-chip orange">EVENTS</span>
                </div>
                <div class="bento-number">{{ summary.events || 0 }}</div>
                <span class="bento-title">比赛项目</span>
                <small>负责管理的赛事数量</small>
              </article>

              <article class="apple-bento-card panel red">
                <div class="bento-top">
                  <div class="sf-badge red"><el-icon><Tickets/></el-icon></div>
                  <span class="apple-chip red">REVIEW</span>
                </div>
                <div class="bento-number">{{ summary.pending_review || 0 }}</div>
                <span class="bento-title">待审核成绩</span>
                <small>需处理的提交流转</small>
              </article>

              <article class="apple-bento-card panel green">
                <div class="bento-top">
                  <div class="sf-badge green"><el-icon><Medal/></el-icon></div>
                  <span class="apple-chip green">PUBLIC</span>
                </div>
                <div class="bento-number">{{ summary.published || 0 }}</div>
                <span class="bento-title">已发布成绩</span>
                <small>已终审向公众大屏呈现</small>
              </article>
            </template>
          </section>

          <!-- 4 列 SF Icon Quick Actions 入口网格 -->
          <section class="apple-quick-grid">
            <button v-for="item in navItems.slice(1, 5)" :key="item.key" class="apple-quick-card panel" @click="active = item.key">
              <div :class="['sf-quick-badge', item.color]">
                <el-icon><component :is="item.icon"/></el-icon>
              </div>
              <div class="quick-info">
                <h3>{{ item.label }}</h3>
                <p>进入模块高效协同操作</p>
              </div>
              <el-icon class="quick-chevron"><ArrowRight/></el-icon>
            </button>
          </section>
        </template>

        <!-- 2. 账号管理 -->
        <template v-else-if="active === 'accounts'">
          <div class="apple-stat-row">
            <div class="panel"><span>开发人员</span><b>{{ quotas.developers || 0 }} / 10</b></div>
            <div class="panel"><span>体育部老师</span><b>{{ quotas.sports_teachers || 0 }} / 20</b></div>
            <div class="panel"><span>全部管理人员</span><b>{{ quotas.administrators || 0 }} / 500</b></div>
            <div class="panel"><span>学生账号</span><b>{{ quotas.students || 0 }} / 10000</b></div>
          </div>
          <section class="mac-card panel">
            <div class="mac-card-head">
              <div><h3>全部账号管理</h3><p>系统账号支持一键冻结与强制下线保护</p></div>
              <div style="display:flex;gap:8px;flex-wrap:wrap">
                <el-button :icon="Download" @click="downloadRosterTemplate">花名册模板</el-button>
                <el-upload action="#" :show-file-list="false" :http-request="importRoster" :disabled="rosterImporting" accept=".xlsx">
                  <el-button :icon="UploadFilled" :loading="rosterImporting">批量注册学生</el-button>
                </el-upload>
                <el-button type="primary" :icon="CirclePlus" @click="openCreateAccount">创建新账号</el-button>
              </div>
            </div>
            <p>花名册至少填写学号、姓名；学生以学号登录，初始密码为 DF + 完整学号。</p>
            <el-table :data="accounts">
              <el-table-column prop="username" label="用户名" min-width="140"/>
              <el-table-column prop="display_name" label="姓名" width="120"/>
              <el-table-column prop="employee_no" label="工号" width="110"/>
              <el-table-column prop="department" label="部门/学院" min-width="150"/>
              <el-table-column label="角色" width="140"><template #default="s">{{ roleLabel[s.row.role] }}</template></el-table-column>
              <el-table-column label="状态" width="100"><template #default="s"><el-tag :type="tagType(s.row.status)">{{ s.row.status === 'ACTIVE' ? '正常' : '冻结' }}</el-tag></template></el-table-column>
              <el-table-column label="操作" width="260" fixed="right">
                <template #default="s">
                  <el-button link type="primary" @click="openEditAccount(s.row)">编辑</el-button>
                  <el-button link @click="resetAccountPassword(s.row)">重置密码</el-button>
                  <el-button link type="warning" @click="toggleFreeze(s.row)">{{ s.row.status === 'ACTIVE' ? '冻结' : '解冻' }}</el-button>
                  <el-button link type="danger" @click="forceLogout(s.row)">强退</el-button>
                </template>
              </el-table-column>
            </el-table>
          </section>
        </template>

        <!-- 3. 系统配置 -->
        <template v-else-if="active === 'settings'">
          <section class="apple-settings-grid">
            <div class="mac-card panel">
              <div class="mac-card-head">
                <div><h3>系统品牌配置</h3><p>保存后登录页、大屏与后台即时更新</p></div>
                <el-button type="primary" @click="saveSettings">保存配置</el-button>
              </div>
              <el-form label-position="top" class="apple-form-grid">
                <el-form-item label="系统完整名称"><el-input v-model="settings.system_name"/></el-form-item>
                <el-form-item label="系统简称"><el-input v-model="settings.short_name"/></el-form-item>
                <el-form-item label="Logo 文字"><el-input v-model="settings.logo_text" maxlength="2"/></el-form-item>
                <el-form-item label="主色调"><el-color-picker v-model="settings.primary_color"/><el-input v-model="settings.primary_color" style="margin-top:6px"/></el-form-item>
                <el-form-item label="登录页主标题"><el-input v-model="settings.login_heading"/></el-form-item>
                <el-form-item label="成绩公布页名称"><el-input v-model="settings.results_page_name"/></el-form-item>
              </el-form>
            </div>
            <div class="mac-preview-card panel" :style="{ background: `linear-gradient(135deg, #1c1c1e, ${settings.primary_color})` }">
              <div class="mac-app-icon lg">{{ settings.logo_text }}</div>
              <span>PREVIEW</span>
              <h2>{{ settings.login_heading }}</h2>
              <p>{{ settings.system_name }}</p>
            </div>
          </section>
        </template>

        <!-- 4. 名单录入 -->
        <template v-else-if="active === 'rosters'">
          <section class="mac-card panel">
            <div class="mac-card-head"><div><h3>比赛项目参赛名单</h3><p>录入学生资料库与代表队后加入各比赛项目分组</p></div></div>
            <el-tabs v-model="rosterTab">
              <el-tab-pane label="项目参赛名单" name="event">
                <div class="apple-filter-bar">
                  <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">
                    <el-select v-model="eventRosterEventId" filterable placeholder="选择项目" style="width:340px" @change="loadEventRoster">
                      <el-option v-for="e in events" :key="e.id" :label="`[${meets.find((m: any) => m.id === e.meet_id)?.name || '运动会'}] ${e.name} · ${eventTypeLabel[e.event_type] || e.event_type}`" :value="e.id"/>
                    </el-select>
                    <el-select v-model="eventRosterRoundId" placeholder="选择轮次" style="width:140px" @change="loadEventRoster">
                      <el-option v-for="r in eventRosterRounds" :key="r.id" :label="r.name" :value="r.id"/>
                    </el-select>
                  </div>
                  <div style="display:flex;gap:8px;flex-wrap:wrap">
                    <el-button :icon="Download" :disabled="!eventRosterItems.length" @click="exportRoster">导出分组表</el-button>
                    <el-button :disabled="!eventRosterItems.length" @click="autoSeedRoster">自动分组排道</el-button>
                    <el-button :disabled="!eventRosterItems.length" @click="advanceRoster">名次生成下一轮</el-button>
                    <el-button type="primary" :icon="CirclePlus" :disabled="!eventRosterEventId" @click="openRegistrationDialog">添加参赛者</el-button>
                  </div>
                </div>
                <el-table :data="eventRosterItems" empty-text="当前轮次暂无参赛名单">
                  <el-table-column label="参赛对象" min-width="170">
                    <template #default="s"><b>{{ s.row.participant.name }}</b> <small style="color:#8e8e93;margin-left:4px">{{ s.row.participant.student_no }}</small></template>
                  </el-table-column>
                  <el-table-column prop="participant.college" label="学院" min-width="160"/>
                  <el-table-column prop="heat" label="组次" width="110"><template #default="s">{{ s.row.heat || '未排组' }}</template></el-table-column>
                  <el-table-column prop="lane" label="道次" width="110"><template #default="s">{{ s.row.lane || '未排道' }}</template></el-table-column>
                  <el-table-column label="状态" width="120">
                    <template #default="s"><el-tag :type="s.row.status === 'REGISTERED' ? 'info' : 'success'">{{ registrationStatusLabel[s.row.status] || s.row.status }}</el-tag></template>
                  </el-table-column>
                  <el-table-column label="操作" width="160" fixed="right">
                    <template #default="s">
                      <el-button link type="primary" @click="openRegistrationEditor(s.row)">编辑</el-button>
                      <el-button link type="danger" @click="removeEventRegistration(s.row)">移除</el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </el-tab-pane>

              <el-tab-pane label="学生资料库" name="student">
                <div class="apple-filter-bar">
                  <div style="display:flex;gap:8px">
                    <el-button type="primary" :icon="CirclePlus" @click="openStudentRoster()">新增学生</el-button>
                    <el-button :icon="Download" @click="downloadRosterTemplate">下载模板</el-button>
                    <el-upload action="#" :show-file-list="false" :http-request="importRoster" :disabled="rosterImporting" accept=".xlsx" style="display:inline-block">
                      <el-button :icon="UploadFilled" :loading="rosterImporting">{{ role === 'DEVELOPER' ? '导入并注册账号' : '批量导入' }}</el-button>
                    </el-upload>
                  </div>
                </div>
                <p v-if="role === 'DEVELOPER'">至少填写学号、姓名即可注册账号；初始密码为 DF + 完整学号。性别、学院、专业、班级可随后补充。</p>
                <el-table :data="students">
                  <el-table-column prop="student_no" label="学号" width="140"/>
                  <el-table-column prop="name" label="姓名" width="120"/>
                  <el-table-column prop="gender" label="性别" width="80"/>
                  <el-table-column prop="college" label="学院" min-width="160"/>
                  <el-table-column prop="class_name" label="班级" min-width="140"/>
                  <el-table-column label="账号状态" width="110">
                    <template #default="s"><el-tag :type="s.row.activated ? 'success' : 'info'">{{ s.row.activated ? '已注册' : '待注册' }}</el-tag></template>
                  </el-table-column>
                  <el-table-column label="操作" width="140" fixed="right">
                    <template #default="s">
                      <el-button link type="primary" @click="openStudentRoster(s.row)">编辑</el-button>
                      <el-button link type="danger" @click="deleteStudentRoster(s.row)">删除</el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </el-tab-pane>

              <el-tab-pane label="学院代表队" name="team">
                <div class="apple-filter-bar" style="display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;background:#fbfbfd;padding:12px 16px;border-radius:12px;margin-bottom:16px;border:1px solid #f0f0f2">
                  <div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center">
                    <span style="font-weight:600;font-size:13px;color:var(--apple-label)">🚩 运动会届次: </span>
                    <el-select v-model="teamMeetId" style="width:200px" @change="loadCollegeTeams">
                      <el-option v-for="m in meets" :key="m.id" :label="`${m.name} (${m.edition}届)`" :value="m.id"/>
                    </el-select>

                    <span style="font-weight:600;font-size:13px;color:var(--apple-label);margin-left:6px">🎯 比赛项目: </span>
                    <el-select v-model="teamEventFilterId" clearable placeholder="全部参赛项目" style="width:220px" @change="loadCollegeTeams">
                      <el-option :value="null" label="全部比赛代表队 (综合总览)"/>
                      <el-option :value="-1" label="🏛️ 全能/通用学院代表队"/>
                      <el-option v-for="e in eventsForTeamMeet" :key="e.id" :label="`${e.name.includes('篮球') ? '🏀 ' : (e.name.includes('排球') ? '🏐 ' : (e.name.includes('乒乓') ? '🏓 ' : '🏃 '))}${e.name} (${e.code})`" :value="e.id"/>
                    </el-select>

                    <el-input v-model="teamSearchKeyword" placeholder="搜索学院/代表队/领队..." clearable :prefix-icon="Search" style="width:190px"/>
                  </div>
                  <div style="display:flex;gap:8px">
                    <el-button type="success" plain @click="generateCollegeTeams">⚡ 批量生成代表队</el-button>
                    <el-button type="primary" :icon="CirclePlus" @click="openCollegeTeam()">➕ 新增学院代表队</el-button>
                  </div>
                </div>

                <el-table :data="filteredCollegeTeams" stripe style="width:100%">
                  <el-table-column prop="meet_name" label="所属运动会" min-width="130" show-overflow-tooltip/>
                  <el-table-column label="所属比赛项目" min-width="160">
                    <template #default="s">
                      <el-tag v-if="!s.row.event_id" type="info" effect="plain" round>🏛️ 通用/全能代表队</el-tag>
                      <el-tag v-else-if="s.row.event_name?.includes('篮球')" type="warning" effect="light" round>🏀 {{ s.row.event_name }}</el-tag>
                      <el-tag v-else-if="s.row.event_name?.includes('排球')" type="success" effect="light" round>🏐 {{ s.row.event_name }}</el-tag>
                      <el-tag v-else-if="s.row.event_name?.includes('乒乓')" color="#f0f9eb" style="color:#67c23a;border-color:#e1f3d8" round>🏓 {{ s.row.event_name }}</el-tag>
                      <el-tag v-else type="primary" effect="light" round>🏃 {{ s.row.event_name }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="college" label="参赛学院" min-width="130">
                    <template #default="s"><b style="color:var(--apple-blue)">{{ s.row.college }}</b></template>
                  </el-table-column>
                  <el-table-column prop="team_name" label="代表队名称" min-width="160">
                    <template #default="s"><b>{{ s.row.team_name }}</b></template>
                  </el-table-column>
                  <el-table-column label="领队/联系电话" min-width="150">
                    <template #default="s">
                      <span v-if="s.row.leader_name">{{ s.row.leader_name }} <span v-if="s.row.leader_phone" style="color:#8e8e93;font-size:12px">({{ s.row.leader_phone }})</span></span>
                      <span v-else style="color:#c7c7cc">未填写</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="队员阵容状态" min-width="180" align="center">
                    <template #default="s">
                      <div style="display:flex;flex-direction:column;gap:3px;align-items:center">
                        <span style="font-size:13px;font-weight:600">
                          已录入 {{ s.row.total_members || 0 }} 人
                          <span style="font-size:11px;color:#8e8e93;font-weight:normal"> (男{{ s.row.male_count || 0 }} / 女{{ s.row.female_count || 0 }})</span>
                        </span>
                        <el-tag v-if="s.row.event_name?.includes('排球')" :type="(s.row.female_count || 0) >= 2 ? 'success' : 'danger'" size="small">
                          {{ (s.row.female_count || 0) >= 2 ? '女生≥2人达标' : `女生缺${2 - (s.row.female_count || 0)}人` }}
                        </el-tag>
                        <el-tag v-else-if="s.row.event_name?.includes('乒乓') && s.row.event_type === 'TEAM'" :type="((s.row.male_count || 0) >= 3 && (s.row.female_count || 0) >= 2) ? 'success' : 'warning'" size="small">
                          {{ ((s.row.male_count || 0) >= 3 && (s.row.female_count || 0) >= 2) ? '3男2女达标' : '待补齐3男2女' }}
                        </el-tag>
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="220" fixed="right" align="center">
                    <template #default="s">
                      <el-button type="primary" size="small" @click="openTeamMembersManager(s.row)">👥 编辑比赛成员</el-button>
                      <el-button link type="primary" size="small" @click="openCollegeTeam(s.row)">编辑</el-button>
                      <el-button link type="danger" size="small" @click="deleteCollegeTeam(s.row)">删除</el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </el-tab-pane>
            </el-tabs>
          </section>
        </template>

        <!-- 5. 赛事与项目 -->
        <template v-else-if="active === 'events'">
          <div style="margin-bottom:16px;display:flex;justify-content:space-between">
            <el-button type="primary" :icon="CirclePlus" @click="openMeetEditor()">新建运动会届次</el-button>
            <el-button type="primary" :icon="CirclePlus" @click="openEventEditor()">新建比赛项目</el-button>
          </div>
          <section class="mac-card panel" style="margin-bottom:20px">
            <div class="mac-card-head"><div><h3>运动会届次</h3></div></div>
            <el-table :data="meets">
              <el-table-column prop="name" label="运动会名称"/>
              <el-table-column prop="edition" label="年度/届次"/>
              <el-table-column prop="start_date" label="开始日期"/>
              <el-table-column prop="end_date" label="结束日期"/>
              <el-table-column label="状态"><template #default="s"><el-tag :type="s.row.status === 'COMPETING' ? 'success' : 'info'">{{ meetStatusLabel[s.row.status] || s.row.status }}</el-tag></template></el-table-column>
              <el-table-column label="操作" width="140" fixed="right">
                <template #default="s"><el-button link type="primary" @click="openMeetEditor(s.row)">编辑</el-button><el-button link type="danger" @click="deleteMeet(s.row)">删除</el-button></template>
              </el-table-column>
            </el-table>
          </section>
          <section class="mac-card panel">
            <div class="mac-card-head"><div><h3>结构化比赛项目列表</h3></div></div>
            <el-table :data="events">
              <el-table-column label="所属运动会" min-width="210"><template #default="s">{{ meetName(s.row.meet_id) }}</template></el-table-column>
              <el-table-column prop="code" label="项目编号" width="110"/>
              <el-table-column prop="name" label="项目名称" min-width="160"/>
              <el-table-column label="组别" width="100"><template #default="s">{{ genderLabel[s.row.gender_group] }}</template></el-table-column>
              <el-table-column label="类型" width="110"><template #default="s">{{ eventTypeLabel[s.row.event_type] }}</template></el-table-column>
              <el-table-column label="默认阶段" width="100"><template #default="s">{{ stageLabel[s.row.stage] }}</template></el-table-column>
              <el-table-column prop="result_unit" label="单位" width="80"/>
              <el-table-column label="操作" width="140" fixed="right">
                <template #default="s"><el-button link type="primary" @click="openEventEditor(s.row)">编辑</el-button><el-button link type="danger" @click="deleteEvent(s.row)">删除</el-button></template>
              </el-table-column>
            </el-table>
          </section>
        </template>

        <!-- 6. 计分模型 -->
        <template v-else-if="active === 'models'">
          <section class="mac-card panel">
            <div class="mac-card-head">
              <div><h3>版本化计分模型</h3><p>已发布成绩自动锁定绑定的规则版本</p></div>
              <el-button type="primary" :icon="CirclePlus" @click="openModelEditor()">创建新模型</el-button>
            </div>
            <div class="apple-model-grid">
              <article v-for="m in scoringModels" :key="m.id" class="apple-model-card panel">
                <div class="model-head">
                  <b>{{ m.name }}</b>
                  <el-tag :type="tagType(m.status)">{{ m.status === 'ENABLED' ? '生效中' : '草稿' }}</el-tag>
                </div>
                <p>{{ m.description || '暂无详细规则说明' }}</p>
                <div class="points-pills">
                  <span v-for="(p, idx) in m.points" :key="idx"><small>第{{ Number(idx) + 1 }}</small><b>{{ p }}分</b></span>
                </div>
                <div class="model-btns">
                  <el-button link type="primary" @click="openModelEditor(m)">编辑</el-button>
                  <el-button link @click="copyModel(m)">复制</el-button>
                  <el-button link type="warning" @click="toggleModel(m)">{{ m.status === 'ENABLED' ? '停用' : '启用' }}</el-button>
                  <el-button link type="danger" :disabled="m.locked_by_published_results" @click="deleteModel(m)">删除</el-button>
                </div>
              </article>
            </div>
          </section>
        </template>

        <!-- 7. 项目权限 -->
        <template v-else-if="active === 'permissions'">
          <section class="mac-card panel">
            <div class="mac-card-head">
              <div><h3>细粒度项目权限管理</h3><p>为具体工作人员按赛事分配独立操作全组</p></div>
              <el-button type="primary" :icon="CirclePlus" @click="openPermissionEditor()">分配项目权限</el-button>
            </div>
            <el-table :data="permissions">
              <el-table-column label="管理人员" min-width="150"><template #default="s">{{ userName(s.row.user_id) }}</template></el-table-column>
              <el-table-column label="比赛项目" min-width="180"><template #default="s">{{ eventName(s.row.event_id) }}</template></el-table-column>
              <el-table-column label="赛程" width="90"><template #default="s">{{ s.row.can_schedule ? '✓' : '—' }}</template></el-table-column>
              <el-table-column label="登记" width="90"><template #default="s">{{ s.row.can_score ? '✓' : '—' }}</template></el-table-column>
              <el-table-column label="审核" width="90"><template #default="s">{{ s.row.can_review ? '✓' : '—' }}</template></el-table-column>
              <el-table-column label="导出" width="90"><template #default="s">{{ s.row.can_export ? '✓' : '—' }}</template></el-table-column>
              <el-table-column label="操作" width="140" fixed="right">
                <template #default="s"><el-button link type="primary" @click="openPermissionEditor(s.row)">编辑</el-button><el-button link type="danger" @click="deletePermission(s.row)">删除</el-button></template>
              </el-table-column>
            </el-table>
          </section>
        </template>

        <!-- 8. 我的项目 -->
        <template v-else-if="active === 'my-events'">
          <section class="mac-card panel">
            <div class="mac-card-head"><div><h3>我的授权比赛项目</h3></div></div>
            <div class="apple-grid-three">
              <article v-for="item in myEvents" :key="item.event.id" class="apple-assign-card panel">
                <div class="sf-badge orange"><el-icon><Trophy/></el-icon></div>
                <div>
                  <span>{{ eventTypeLabel[item.event.event_type] }} · {{ genderLabel[item.event.gender_group] }}</span>
                  <h3>{{ item.event.name }}</h3>
                  <div class="permission-tags">
                    <el-tag v-if="item.permissions.can_schedule" size="small">赛程</el-tag>
                    <el-tag v-if="item.permissions.can_score" size="small" type="success">登记</el-tag>
                    <el-tag v-if="item.permissions.can_review" size="small" type="warning">审核</el-tag>
                  </div>
                </div>
              </article>
            </div>
          </section>
        </template>

        <!-- 8.5 🏀 篮球赛制工作台 (国家体委审定两阶段赛制) -->
        <template v-else-if="active === 'basketball'">
          <section class="mac-card panel">
            <!-- 头部控制栏：届次切换与新建 -->
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;border-bottom:1px solid rgba(0,0,0,0.06);padding-bottom:14px;flex-wrap:wrap;gap:12px">
              <div>
                <h3 style="font-size:18px;margin:0 0 4px;display:flex;align-items:center;gap:8px">
                  <span>🏀 篮球联赛工作台</span>
                  <el-tag size="small" type="warning" effect="dark">五对五国标赛制</el-tag>
                </h3>
                <p style="margin:0;font-size:12px;color:#8e8e93">
                  第一阶段 A/B 组单循环（胜2分·负1分·弃权0分）· 第二阶段交叉淘汰决胜赛（争夺前四名）
                </p>
              </div>
              <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
                <div style="display:flex;align-items:center;gap:6px">
                  <span style="font-size:13px;font-weight:600">🚩 运动会届次:</span>
                  <el-select v-model="selectedMeetId" style="width:200px" @change="onSelectedMeetChange">
                    <el-option v-for="m in meets" :key="m.id" :label="`${m.name} (${m.edition}届)`" :value="m.id"/>
                  </el-select>
                </div>
                <el-button type="success" :disabled="!canCreateBusiness" @click="openCreateBasketballEventDialog">
                  ➕ 新建篮球项目
                </el-button>
                <el-button plain @click="active = 'rosters'">
                  👥 名单录入中心
                </el-button>
              </div>
            </div>

            <!-- 操作与流程流转栏 -->
            <div class="apple-filter-bar" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;flex-wrap:wrap;gap:12px;background:#f5f5f7;padding:12px 16px;border-radius:12px">
              <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
                <el-select v-model="basketballEventId" placeholder="选择本届篮球项目" style="width:240px" @change="loadBasketballData">
                  <el-option v-for="e in basketballEvents" :key="e.id" :label="`${e.name} (${eventTypeLabel[e.event_type] || '团体赛'})`" :value="e.id"/>
                </el-select>
                <el-button type="success" plain :disabled="!canCreateBusiness" @click="openCreateBasketballEventDialog">➕ 新建篮球项目</el-button>
                <el-button type="primary" :disabled="!basketballEventId || !canCreateBusiness" @click="openAddBasketballTeamsDialog">👥 录入参赛代表队 (已选 {{ basketballTeamsData.registered_teams.length }} 队)</el-button>
              </div>
              <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
                <el-button type="primary" :disabled="!basketballEventId || !canCreateBusiness" @click="autoGenerateBasketballGroups">① A/B组抽签并生成循环赛程</el-button>
                <el-button type="warning" :disabled="!basketballEventId || !canCreateBusiness" @click="advanceBasketballToFinals">② 小组前二名进半决赛</el-button>
                <el-button type="warning" :disabled="!basketballEventId || !canCreateBusiness" @click="generateBasketballFinals">③ 生成决赛与季军赛</el-button>
                <el-button type="success" :disabled="!basketballEventId || !canCreateBusiness" @click="finalizeBasketballResults">④ 定稿前四名成绩</el-button>
              </div>
            </div>

            <!-- 已参赛代表队展示区 -->
            <div style="background:#ffffff;border:1px solid rgba(0,0,0,0.06);border-radius:12px;padding:12px 16px;margin-bottom:16px">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
                <span style="font-size:13px;font-weight:700">📋 本赛事参赛学院队伍 (共 {{ basketballTeamsData.registered_teams.length }} 支)：</span>
                <el-button link type="primary" size="small" @click="openAddBasketballTeamsDialog">编辑参赛队伍名单</el-button>
              </div>
              <div v-if="basketballTeamsData.registered_teams.length" style="display:flex;flex-wrap:wrap;gap:8px">
                <el-tag v-for="t in basketballTeamsData.registered_teams" :key="t.registration_id" :type="t.group_tag === 'A' ? 'primary' : t.group_tag === 'B' ? 'warning' : 'info'" size="default">
                  {{ t.team_name }} · <b>{{ t.group_tag === 'A' ? 'A组' : t.group_tag === 'B' ? 'B组' : '未抽签' }}</b>
                </el-tag>
              </div>
              <div v-else style="font-size:12px;color:#8e8e93;padding:6px 0">
                暂未添加参赛队伍，请点击右上角【👥 录入参赛代表队】选择各学院代表队参赛！
              </div>
            </div>

            <!-- 规则提示条 -->
            <div style="background:rgba(0,122,255,0.06);border:1px solid rgba(0,122,255,0.15);border-radius:10px;padding:10px 14px;margin-bottom:18px;font-size:12px;color:#0055b3;display:flex;align-items:center;gap:8px">
              <el-icon><InfoFilled /></el-icon>
              <span><b>国家体委《篮球竞赛规则》：</b>第一阶段采用A、B两组单循环赛（<b>胜一场积2分、负一场积1分、弃权积0分</b>，积分多者列前）；第二阶段由各小组前二名（A1, A2, B1, B2）进行交叉淘汰与决赛争夺前四名。</span>
            </div>

            <!-- 第一阶段：A/B 组循环赛与积分榜 -->
            <div style="margin-bottom:24px">
              <h3 style="font-size:15px;margin:0 0 12px;color:var(--apple-label)">第一阶段：分组单循环积分赛 (胜积2分 · 负积1分)</h3>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:18px">
                <!-- A 组 -->
                <div style="background:#fcfcfd;border:1px solid rgba(0,0,0,0.06);border-radius:14px;padding:14px">
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
                    <b style="color:var(--apple-blue);font-size:14px">🔵 A 组实时积分榜</b>
                    <span style="font-size:11px;color:#8e8e93">前2名晋级半决赛</span>
                  </div>
                  <el-table :data="basketballStandings.group_a" size="small" border style="margin-bottom:12px">
                    <el-table-column prop="rank" label="名次" width="50" align="center"/>
                    <el-table-column prop="college" label="学院/代表队" min-width="110"/>
                    <el-table-column prop="played" label="已赛" width="50" align="center"/>
                    <el-table-column prop="won" label="胜" width="45" align="center"><template #default="s"><span style="color:#34c759;font-weight:700">{{ s.row.won }}</span></template></el-table-column>
                    <el-table-column prop="lost" label="负" width="45" align="center"><template #default="s"><span style="color:#ff3b30">{{ s.row.lost }}</span></template></el-table-column>
                    <el-table-column prop="points" label="积分" width="55" align="center"><template #default="s"><b style="color:var(--apple-blue)">{{ s.row.points }}</b></template></el-table-column>
                    <el-table-column prop="points_diff" label="净胜" width="60" align="center"/>
                  </el-table>
                  <div style="font-size:12px;font-weight:600;margin-bottom:6px;color:#666">A 组单循环赛程与比分：</div>
                  <div style="display:flex;flex-direction:column;gap:6px">
                    <div v-for="m in basketballMatches.filter(i=>i.stage_type==='GROUP_A')" :key="m.id" style="background:#fff;border:1px solid #eee;border-radius:8px;padding:8px 12px;display:flex;justify-content:space-between;align-items:center">
                      <div style="font-size:12px">
                        <b>{{ m.home_college }}</b>
                        <span style="margin:0 6px;color:#888;font-family:var(--font-mono)">
                          {{ m.status==='FINISHED' ? `${m.home_score} : ${m.away_score}` : 'VS' }}
                        </span>
                        <b>{{ m.away_college }}</b>
                      </div>
                      <el-button link type="primary" size="small" :disabled="!canScoreSelected" @click="openEditBasketballMatch(m)">
                        {{ m.status==='FINISHED' ? '改比分' : '录入比分' }}
                      </el-button>
                    </div>
                  </div>
                </div>

                <!-- B 组 -->
                <div style="background:#fcfcfd;border:1px solid rgba(0,0,0,0.06);border-radius:14px;padding:14px">
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
                    <b style="color:var(--apple-orange);font-size:14px">🟠 B 组实时积分榜</b>
                    <span style="font-size:11px;color:#8e8e93">前2名晋级半决赛</span>
                  </div>
                  <el-table :data="basketballStandings.group_b" size="small" border style="margin-bottom:12px">
                    <el-table-column prop="rank" label="名次" width="50" align="center"/>
                    <el-table-column prop="college" label="学院/代表队" min-width="110"/>
                    <el-table-column prop="played" label="已赛" width="50" align="center"/>
                    <el-table-column prop="won" label="胜" width="45" align="center"><template #default="s"><span style="color:#34c759;font-weight:700">{{ s.row.won }}</span></template></el-table-column>
                    <el-table-column prop="lost" label="负" width="45" align="center"><template #default="s"><span style="color:#ff3b30">{{ s.row.lost }}</span></template></el-table-column>
                    <el-table-column prop="points" label="积分" width="55" align="center"><template #default="s"><b style="color:var(--apple-orange)">{{ s.row.points }}</b></template></el-table-column>
                    <el-table-column prop="points_diff" label="净胜" width="60" align="center"/>
                  </el-table>
                  <div style="font-size:12px;font-weight:600;margin-bottom:6px;color:#666">B 组单循环赛程与比分：</div>
                  <div style="display:flex;flex-direction:column;gap:6px">
                    <div v-for="m in basketballMatches.filter(i=>i.stage_type==='GROUP_B')" :key="m.id" style="background:#fff;border:1px solid #eee;border-radius:8px;padding:8px 12px;display:flex;justify-content:space-between;align-items:center">
                      <div style="font-size:12px">
                        <b>{{ m.home_college }}</b>
                        <span style="margin:0 6px;color:#888;font-family:var(--font-mono)">
                          {{ m.status==='FINISHED' ? `${m.home_score} : ${m.away_score}` : 'VS' }}
                        </span>
                        <b>{{ m.away_college }}</b>
                      </div>
                      <el-button link type="primary" size="small" :disabled="!canScoreSelected" @click="openEditBasketballMatch(m)">
                        {{ m.status==='FINISHED' ? '改比分' : '录入比分' }}
                      </el-button>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 第二阶段：交叉淘汰与决赛 (争夺前四名) -->
            <div>
              <h3 style="font-size:15px;margin:0 0 12px;color:var(--apple-label)">第二阶段：交叉淘汰与决赛 (争夺前四名)</h3>
              <div style="display:grid;grid-template-columns:repeat(4, 1fr);gap:14px">
                <!-- 半决赛 1 -->
                <div v-for="m in basketballMatches.filter(i=>['SEMIFINAL','THIRD_PLACE','FINAL'].includes(i.stage_type))" :key="m.id" style="background:#fff;border:1px solid rgba(0,0,0,0.08);border-radius:12px;padding:14px;display:flex;flex-direction:column;justify-content:space-between">
                  <div>
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
                      <span style="font-size:11px;font-weight:700;color:var(--apple-blue)">{{ m.match_name }}</span>
                      <el-tag size="small" :type="m.status==='FINISHED'?'success':'info'">{{ m.status==='FINISHED'?'已完赛':'未开始' }}</el-tag>
                    </div>
                    <div style="display:flex;flex-direction:column;gap:6px;margin:10px 0">
                      <div style="display:flex;justify-content:space-between;align-items:center;padding:4px 8px;border-radius:6px" :style="m.winner_team_id===m.home_team_id?'background:rgba(52,199,89,0.12);font-weight:700':''">
                        <span>{{ m.home_college }}</span>
                        <b style="font-family:var(--font-mono)">{{ m.home_score !== null ? m.home_score : '—' }}</b>
                      </div>
                      <div style="display:flex;justify-content:space-between;align-items:center;padding:4px 8px;border-radius:6px" :style="m.winner_team_id===m.away_team_id?'background:rgba(52,199,89,0.12);font-weight:700':''">
                        <span>{{ m.away_college }}</span>
                        <b style="font-family:var(--font-mono)">{{ m.away_score !== null ? m.away_score : '—' }}</b>
                      </div>
                    </div>
                  </div>
                  <el-button type="primary" size="small" :disabled="!canScoreSelected" @click="openEditBasketballMatch(m)" style="margin-top:8px">
                    {{ m.status==='FINISHED' ? '修改比分' : '录入决胜比分' }}
                  </el-button>
                </div>
              </div>
            </div>
          </section>
        </template>

        <!-- 🏐 排球赛制工作台 (国家体委《排球竞赛规则》、三局两胜25分制、女生≥2人、胜4分/1:2负2分/0:2负1分/弃权0分判2:0、交叉淘汰决前四名) -->
        <template v-else-if="active === 'volleyball'">
          <section class="mac-card panel">
            <!-- 头部控制栏：届次切换与新建 -->
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;border-bottom:1px solid rgba(0,0,0,0.06);padding-bottom:14px;flex-wrap:wrap;gap:12px">
              <div>
                <h3 style="font-size:18px;margin:0 0 4px;display:flex;align-items:center;gap:8px">
                  <span>🏐 排球联赛工作台</span>
                  <el-tag size="small" type="primary" effect="dark" round>三局两胜 · 25 分制</el-tag>
                  <el-tag size="small" type="danger" effect="plain" round>女生 ≥ 2 人</el-tag>
                  <el-tag size="small" type="warning" effect="plain" round>胜4分 / 1:2负2分 / 0:2负1分 / 弃权0分</el-tag>
                </h3>
                <p style="margin:0;font-size:12px;color:#8e8e93">
                  依据国家体委审定《排球竞赛规则》：第一阶段 A/B 组单循环赛；第二阶段交叉淘汰赛争夺前四名
                </p>
              </div>
              <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
                <div style="display:flex;align-items:center;gap:6px">
                  <span style="font-size:13px;font-weight:600">🚩 运动会届次:</span>
                  <el-select v-model="selectedMeetId" style="width:200px" @change="onSelectedMeetChange">
                    <el-option v-for="m in meets" :key="m.id" :label="`${m.name} (${m.edition}届)`" :value="m.id"/>
                  </el-select>
                </div>
                <el-button type="success" :disabled="!canCreateBusiness" @click="openCreateVolleyballEventDialog">
                  ➕ 新建排球项目
                </el-button>
                <el-button plain @click="active = 'rosters'">
                  👥 名单录入中心
                </el-button>
              </div>
            </div>

            <!-- 项目选择与操作栏 -->
            <div class="apple-filter-bar" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;flex-wrap:wrap;gap:12px;background:#f5f5f7;padding:12px 16px;border-radius:12px">
              <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
                <el-select v-model="volleyballEventId" style="width:240px" placeholder="选择本届排球项目" @change="loadVolleyballData">
                  <el-option v-for="e in volleyballEvents" :key="e.id" :label="`${e.name} (${e.code})`" :value="e.id" />
                </el-select>
                <el-button type="success" plain :disabled="!canCreateBusiness" @click="openCreateVolleyballEventDialog">➕ 新建排球项目</el-button>
                <el-button type="primary" :disabled="!volleyballEventId || !canCreateBusiness" @click="openAddVolleyballTeamsDialog">👥 录入参赛代表队 ({{ volleyballTeamsData.registered_teams.length }}队)</el-button>
              </div>
            </div>

            <!-- 排球规则说明 Banner 与一键流程操作栏 -->
            <div style="background:linear-gradient(135deg, rgba(175,82,222,0.06), rgba(0,122,255,0.06));border:1px solid rgba(175,82,222,0.18);border-radius:14px;padding:16px;margin-bottom:20px">
              <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px">
                <div style="display:flex;flex-direction:column;gap:4px">
                  <b style="color:var(--apple-purple);font-size:14px">📋 排球竞赛规程与计分规则要点：</b>
                  <span style="font-size:12px;color:#636366">
                    ① 上场队员女生不能低于两人； ② 比赛采取三局两胜制（每局25分）； ③ 15分钟未到场按弃权论处判对方 2:0 获胜（弃权0分，胜方4分）； ④ 小组赛每场胜积4分、负(1:2)积2分、负(0:2)积1分，积分多者前列（若相同看C值胜负局比、Z值总分比）； ⑤ 小组前两名出线交叉淘汰争夺前四名。
                  </span>
                </div>
                <div style="display:flex;gap:8px;flex-wrap:wrap">
                  <el-button type="primary" :disabled="!canScoreSelected" @click="autoGenerateVolleyballGroups">① A/B组抽签与赛程生成</el-button>
                  <el-button type="warning" :disabled="!canScoreSelected" @click="advanceVolleyballToFinals">② 小组前二进半决赛</el-button>
                  <el-button type="primary" :disabled="!canScoreSelected" @click="generateVolleyballFinals">③ 生成决赛与季军赛</el-button>
                  <el-button type="success" :disabled="!canScoreSelected" @click="finalizeVolleyballResults">④ 定稿前四名归档</el-button>
                </div>
              </div>
            </div>

            <!-- 参赛代表队女生规则合规性看板 -->
            <div v-if="volleyballTeamsData.registered_teams.length" style="margin-bottom:22px">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
                <h4 style="font-size:14px;margin:0;color:var(--apple-label)">👥 参赛代表队阵容与女生达标情况 (女生不能低于2人)</h4>
                <small style="color:#8e8e93">点击代表队可快速管理队员</small>
              </div>
              <div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(220px, 1fr));gap:12px">
                <div
                  v-for="t in volleyballTeamsData.registered_teams"
                  :key="t.team_id"
                  style="background:#fff;border:1px solid rgba(0,0,0,0.06);border-radius:12px;padding:12px;cursor:pointer;transition:transform 0.15s ease"
                  @click="openTeamMembersManager(t)"
                >
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                    <b style="font-size:14px">{{ t.college }}</b>
                    <el-tag size="small" :type="t.female_rule_passed ? 'success' : 'danger'">{{ t.female_rule_passed ? '女生达标' : '女生不足' }}</el-tag>
                  </div>
                  <div style="font-size:12px;color:#8e8e93;display:flex;justify-content:space-between">
                    <span>队员: {{ t.member_count }}人 (男{{ t.male_count }} / 女{{ t.female_count }})</span>
                    <span style="color:var(--apple-blue);font-weight:600">{{ t.group_tag }}组</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- 第一阶段：A/B 组单循环赛与 4/2/1/0 积分榜 -->
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:28px">
              <!-- A组 -->
              <div style="background:#fcfcfd;border:1px solid rgba(0,0,0,0.06);border-radius:16px;padding:18px">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
                  <h3 style="font-size:15px;margin:0;display:flex;align-items:center;gap:6px">
                    <span style="width:10px;height:10px;border-radius:50%;background:var(--apple-blue)"></span>
                    <span>第一阶段：A组循环赛与积分榜</span>
                  </h3>
                  <small style="color:#8e8e93">前2名出线进入半决赛</small>
                </div>
                <el-table :data="volleyballStandings.group_a" size="small" style="margin-bottom:14px">
                  <el-table-column prop="rank" label="名次" width="50" align="center">
                    <template #default="s">
                      <b :style="s.row.rank<=2 ? 'color:var(--apple-blue);font-weight:800' : ''">{{ s.row.rank }}</b>
                    </template>
                  </el-table-column>
                  <el-table-column prop="college" label="学院" min-width="100"/>
                  <el-table-column prop="played" label="场次" width="50" align="center"/>
                  <el-table-column prop="won" label="胜" width="45" align="center"/>
                  <el-table-column prop="lost" label="负" width="45" align="center"/>
                  <el-table-column prop="points" label="积分" width="55" align="center">
                    <template #default="s"><b style="color:var(--apple-purple);font-size:13px">{{ s.row.points }}</b></template>
                  </el-table-column>
                  <el-table-column prop="set_ratio" label="C值(局比)" width="75" align="center"/>
                  <el-table-column prop="point_ratio" label="Z值(分比)" width="75" align="center"/>
                </el-table>
                <!-- A组单场赛程列表 -->
                <div style="display:flex;flex-direction:column;gap:8px">
                  <div
                    v-for="m in volleyballMatches.filter(i=>i.stage_type==='GROUP_A')"
                    :key="m.id"
                    style="background:#fff;border:1px solid rgba(0,0,0,0.06);border-radius:10px;padding:10px 14px;display:flex;justify-content:space-between;align-items:center"
                  >
                    <div>
                      <div style="font-size:13px;font-weight:600">
                        <span>{{ m.home_college }}</span>
                        <span style="margin:0 8px;color:#8e8e93">vs</span>
                        <span>{{ m.away_college }}</span>
                      </div>
                      <small style="color:#8e8e93">{{ m.court_venue }} | {{ m.sets_summary || (m.status==='FINISHED' ? `${m.home_score}:${m.away_score}` : '未开始') }} {{ m.notes || '' }}</small>
                    </div>
                    <div style="display:flex;align-items:center;gap:10px">
                      <b style="font-size:15px;font-family:var(--font-mono)" :style="m.status==='FINISHED'?'color:var(--apple-blue)':''">
                        {{ m.home_score !== null ? `${m.home_score} : ${m.away_score}` : '— : —' }}
                      </b>
                      <el-button size="small" type="primary" plain :disabled="!canScoreSelected" @click="openEditVolleyballMatch(m)">
                        {{ m.status==='FINISHED' ? '修改比分' : '录入比分' }}
                      </el-button>
                    </div>
                  </div>
                </div>
              </div>

              <!-- B组 -->
              <div style="background:#fcfcfd;border:1px solid rgba(0,0,0,0.06);border-radius:16px;padding:18px">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
                  <h3 style="font-size:15px;margin:0;display:flex;align-items:center;gap:6px">
                    <span style="width:10px;height:10px;border-radius:50%;background:var(--apple-orange)"></span>
                    <span>第一阶段：B组循环赛与积分榜</span>
                  </h3>
                  <small style="color:#8e8e93">前2名出线进入半决赛</small>
                </div>
                <el-table :data="volleyballStandings.group_b" size="small" style="margin-bottom:14px">
                  <el-table-column prop="rank" label="名次" width="50" align="center">
                    <template #default="s">
                      <b :style="s.row.rank<=2 ? 'color:var(--apple-orange);font-weight:800' : ''">{{ s.row.rank }}</b>
                    </template>
                  </el-table-column>
                  <el-table-column prop="college" label="学院" min-width="100"/>
                  <el-table-column prop="played" label="场次" width="50" align="center"/>
                  <el-table-column prop="won" label="胜" width="45" align="center"/>
                  <el-table-column prop="lost" label="负" width="45" align="center"/>
                  <el-table-column prop="points" label="积分" width="55" align="center">
                    <template #default="s"><b style="color:var(--apple-purple);font-size:13px">{{ s.row.points }}</b></template>
                  </el-table-column>
                  <el-table-column prop="set_ratio" label="C值(局比)" width="75" align="center"/>
                  <el-table-column prop="point_ratio" label="Z值(分比)" width="75" align="center"/>
                </el-table>
                <!-- B组单场赛程列表 -->
                <div style="display:flex;flex-direction:column;gap:8px">
                  <div
                    v-for="m in volleyballMatches.filter(i=>i.stage_type==='GROUP_B')"
                    :key="m.id"
                    style="background:#fff;border:1px solid rgba(0,0,0,0.06);border-radius:10px;padding:10px 14px;display:flex;justify-content:space-between;align-items:center"
                  >
                    <div>
                      <div style="font-size:13px;font-weight:600">
                        <span>{{ m.home_college }}</span>
                        <span style="margin:0 8px;color:#8e8e93">vs</span>
                        <span>{{ m.away_college }}</span>
                      </div>
                      <small style="color:#8e8e93">{{ m.court_venue }} | {{ m.sets_summary || (m.status==='FINISHED' ? `${m.home_score}:${m.away_score}` : '未开始') }} {{ m.notes || '' }}</small>
                    </div>
                    <div style="display:flex;align-items:center;gap:10px">
                      <b style="font-size:15px;font-family:var(--font-mono)" :style="m.status==='FINISHED'?'color:var(--apple-orange)':''">
                        {{ m.home_score !== null ? `${m.home_score} : ${m.away_score}` : '— : —' }}
                      </b>
                      <el-button size="small" type="primary" plain :disabled="!canScoreSelected" @click="openEditVolleyballMatch(m)">
                        {{ m.status==='FINISHED' ? '修改比分' : '录入比分' }}
                      </el-button>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 第二阶段：交叉淘汰与前四名争夺 -->
            <div>
              <h3 style="font-size:15px;margin:0 0 12px;color:var(--apple-label)">第二阶段：交叉淘汰与决赛 (争夺全国前四名)</h3>
              <div style="display:grid;grid-template-columns:repeat(4, 1fr);gap:14px">
                <div v-for="m in volleyballMatches.filter(i=>['SEMIFINAL','THIRD_PLACE','FINAL'].includes(i.stage_type))" :key="m.id" style="background:#fff;border:1px solid rgba(0,0,0,0.08);border-radius:12px;padding:14px;display:flex;flex-direction:column;justify-content:space-between">
                  <div>
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
                      <span style="font-size:11px;font-weight:700;color:var(--apple-purple)">{{ m.match_name }}</span>
                      <el-tag size="small" :type="m.status==='FINISHED'?'success':'info'">{{ m.status==='FINISHED'?'已完赛':'未开始' }}</el-tag>
                    </div>
                    <div style="display:flex;flex-direction:column;gap:6px;margin:10px 0">
                      <div style="display:flex;justify-content:space-between;align-items:center;padding:4px 8px;border-radius:6px" :style="m.winner_team_id===m.home_team_id?'background:rgba(52,199,89,0.12);font-weight:700':''">
                        <span>{{ m.home_college }}</span>
                        <b style="font-family:var(--font-mono)">{{ m.home_score !== null ? `${m.home_score}局` : '—' }}</b>
                      </div>
                      <div style="display:flex;justify-content:space-between;align-items:center;padding:4px 8px;border-radius:6px" :style="m.winner_team_id===m.away_team_id?'background:rgba(52,199,89,0.12);font-weight:700':''">
                        <span>{{ m.away_college }}</span>
                        <b style="font-family:var(--font-mono)">{{ m.away_score !== null ? `${m.away_score}局` : '—' }}</b>
                      </div>
                    </div>
                    <div v-if="m.sets_summary" style="font-size:11px;color:#8e8e93;margin-bottom:6px">
                      局分: {{ m.sets_summary }}
                    </div>
                  </div>
                  <el-button type="primary" size="small" :disabled="!canScoreSelected" @click="openEditVolleyballMatch(m)" style="margin-top:8px">
                    {{ m.status==='FINISHED' ? '修改局比分' : '录入三局决胜比分' }}
                  </el-button>
                </div>
              </div>
            </div>
          </section>
        </template>

        <!-- 🏓 乒乓球赛制工作台 (混合团体赛 / 男子单打 / 女子单打) -->
        <template v-else-if="active === 'table-tennis'">
          <section class="mac-card panel">
            <!-- 头部控制栏：子栏目切换（混合团体赛 / 男子单打 / 女子单打）与运动会届次 -->
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;border-bottom:1px solid rgba(0,0,0,0.06);padding-bottom:14px;flex-wrap:wrap;gap:12px">
              <div>
                <h3 style="font-size:18px;margin:0 0 4px;display:flex;align-items:center;gap:8px">
                  <span>🏓 乒乓球赛制工作台</span>
                  <el-tag size="small" type="success" effect="dark">国标竞赛规程</el-tag>
                </h3>
                <p style="margin:0;font-size:12px;color:#8e8e93">
                  混合团体赛（3男2女/打满5场/积分2-1-0）· 男/女单打（种子回避/前3局后5局动态切换）
                </p>
              </div>
              <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
                <div style="display:flex;align-items:center;gap:6px">
                  <span style="font-size:13px;font-weight:600">🚩 运动会届次:</span>
                  <el-select v-model="selectedMeetId" style="width:190px" @change="onSelectedMeetChange">
                    <el-option v-for="m in meets" :key="m.id" :label="`${m.name} (${m.edition}届)`" :value="m.id"/>
                  </el-select>
                </div>
                <el-radio-group v-model="ttTab" size="default">
                  <el-radio-button value="team">🏓 混合团体 (3男2女)</el-radio-button>
                  <el-radio-button value="ms">🏓 男子单打</el-radio-button>
                  <el-radio-button value="ws">🏓 女子单打</el-radio-button>
                </el-radio-group>
                <el-button type="success" :disabled="!canCreateBusiness" @click="openCreateTtEventDialog()">
                  ➕ 新建乒乓球项目
                </el-button>
                <el-button plain @click="active = 'rosters'">
                  👥 名单录入中心
                </el-button>
              </div>
            </div>

            <!-- ===================== A. 混合团体赛 Tab ===================== -->
            <div v-if="ttTab === 'team'">
              <!-- 规则导引提示卡片 -->
              <div style="background:rgba(0,122,255,0.06);border:1px solid rgba(0,122,255,0.18);border-radius:12px;padding:14px 18px;margin-bottom:16px">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                  <b style="color:var(--apple-blue);font-size:14px">🏓 乒乓球混合团体竞赛规则指南</b>
                  <el-tag size="small" type="primary">打满五盘 · 2/1/0分制</el-tag>
                </div>
                <div style="font-size:12px;line-height:1.7;color:#48484a">
                  <b>1. 参赛要求：</b>各学院上报 <b>3男、2女</b> 在籍生队员（独立组队不得外借）；<br/>
                  <b>2. 第一阶段（小组循环赛）：</b>抽签分组（每组3队），严格按【<b>男单1 ➔ 女单1 ➔ 男单2 ➔ 女单2 ➔ 男单3</b>】出场顺序<b>打满五场（5盘）</b>，单盘三局两胜（11分制）。胜一场积 <b>2分</b>，负一场积 <b>1分</b>，15分钟未到场弃权积 <b>0分</b>（判0:5负）；<br/>
                  <b>3. 出线晋级：</b>各小组第1名 + 成绩最好的小组第2名（优先比积分、次查净胜盘、局分比、得分比）晋级四强；<br/>
                  <b>4. 第二阶段（交叉淘汰赛）：</b>半决赛、季军赛、总决赛决出前四名并一键定稿归档大屏与团体积分库。
                </div>
              </div>

              <!-- 混合团体项目选择与操作栏 -->
              <div class="apple-filter-bar" style="background:#f5f5f7;padding:12px 16px;border-radius:12px;margin-bottom:16px">
                <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
                  <el-select v-model="ttTeamEventId" placeholder="选择乒乓球混合团体项目" style="width:240px">
                    <el-option v-for="e in ttTeamEvents" :key="e.id" :label="`${e.name} (${e.code})`" :value="e.id"/>
                  </el-select>
                  <el-button type="success" plain @click="openCreateTtEventDialog('TEAM')">
                    ➕ 新建混合团体项目
                  </el-button>
                  <el-button type="primary" plain :disabled="!ttTeamEventId" @click="openAddTtTeamsDialog">
                    👥 录入参赛队伍 ({{ ttTeamTeamsData.registered_teams?.length || 0 }}队)
                  </el-button>
                  <el-button type="primary" :disabled="!ttTeamEventId" @click="autoGenerateTtTeamGroups">
                    🎲 抽签分组与赛程生成 (每组3队·打满五盘)
                  </el-button>
                </div>
                <div style="display:flex;gap:8px">
                  <el-button type="warning" plain :disabled="!ttTeamEventId" @click="advanceTtTeamToFinals">
                    ⚔️ 最好第二/前二进半决赛
                  </el-button>
                  <el-button type="success" plain :disabled="!ttTeamEventId" @click="generateTtTeamFinals">
                    🏆 生成决赛与季军赛
                  </el-button>
                  <el-button type="danger" :disabled="!ttTeamEventId" @click="finalizeTtTeamResults">
                    📦 定稿前四名归档
                  </el-button>
                </div>
              </div>

              <!-- 3男2女 名单合规性检查展板 -->
              <div style="background:#fff;border:1px solid rgba(0,0,0,0.06);border-radius:14px;padding:14px;margin-bottom:16px">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
                  <b style="font-size:13px">📋 参赛队伍名单合规检查（规程要求：各学院必须报 3男2女）</b>
                  <el-tag :type="ttTeamStatusData.all_compliant ? 'success' : 'danger'" size="small">
                    {{ ttTeamStatusData.all_compliant ? `全部 ${ttTeamStatusData.total_teams} 支队伍名单达标` : `已达标 ${ttTeamStatusData.compliant_count} / ${ttTeamStatusData.total_teams} 队` }}
                  </el-tag>
                </div>
                <div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(180px, 1fr));gap:10px">
                  <div
                    v-for="t in ttTeamStatusData.teams"
                    :key="t.team_id"
                    style="background:#f9f9fb;border:1px solid rgba(0,0,0,0.05);border-radius:8px;padding:8px 12px;display:flex;flex-direction:column;gap:4px"
                  >
                    <div style="display:flex;justify-content:space-between;align-items:center">
                      <b style="font-size:12px">{{ t.college }}</b>
                      <el-tag :type="t.compliant ? 'success' : 'danger'" size="small">
                        {{ t.compliant ? '已达标' : '不足' }}
                      </el-tag>
                    </div>
                    <small style="color:#8e8e93;font-size:11px">
                      男队员: <b :style="t.male_count >= 3 ? 'color:#34c759' : 'color:#ff3b30'">{{ t.male_count }} / 3</b>
                      · 女队员: <b :style="t.female_count >= 2 ? 'color:#34c759' : 'color:#ff3b30'">{{ t.female_count }} / 2</b>
                    </small>
                  </div>
                </div>
              </div>

              <!-- 第一阶段：分组循环赛与积分榜（A组 & B组） -->
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px">
                <!-- A组 -->
                <div style="background:#fcfcfd;border:1px solid rgba(0,0,0,0.06);border-radius:16px;padding:18px">
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
                    <h3 style="font-size:15px;margin:0;display:flex;align-items:center;gap:6px">
                      <span style="width:10px;height:10px;border-radius:50%;background:var(--apple-blue)"></span>
                      <span>第一阶段：A组循环赛与积分榜 (每组3队)</span>
                    </h3>
                    <small style="color:#8e8e93">胜2分·负1分·弃权0分</small>
                  </div>
                  <el-table :data="ttTeamStandings.groups?.group_a || []" size="small" style="margin-bottom:14px">
                    <el-table-column prop="rank" label="名次" width="50" align="center">
                      <template #default="s">
                        <b :style="s.row.rank===1 ? 'color:var(--apple-blue);font-weight:800' : ''">{{ s.row.rank }}</b>
                      </template>
                    </el-table-column>
                    <el-table-column prop="college" label="学院" min-width="90"/>
                    <el-table-column prop="played" label="场次" width="45" align="center"/>
                    <el-table-column prop="won" label="胜" width="40" align="center"/>
                    <el-table-column prop="lost" label="负" width="40" align="center"/>
                    <el-table-column prop="points" label="积分" width="50" align="center">
                      <template #default="s"><b style="color:var(--apple-blue);font-size:13px">{{ s.row.points }}</b></template>
                    </el-table-column>
                    <el-table-column prop="rubber_diff" label="净胜盘" width="55" align="center"/>
                    <el-table-column prop="set_ratio" label="局比" width="60" align="center"/>
                    <el-table-column label="状态" width="80" align="center">
                      <template #default="s">
                        <el-tag v-if="s.row.rank===1" size="small" type="success">小组第1</el-tag>
                        <el-tag v-else-if="ttTeamStandings.best_second?.team_id===s.row.team_id" size="small" type="warning">🌟 最好第2</el-tag>
                      </template>
                    </el-table-column>
                  </el-table>
                  <!-- A组赛程列表 -->
                  <div style="display:flex;flex-direction:column;gap:8px">
                    <div
                      v-for="m in ttTeamMatches.filter(i=>i.stage_type==='GROUP_A')"
                      :key="m.id"
                      style="background:#fff;border:1px solid rgba(0,0,0,0.06);border-radius:10px;padding:10px 14px;display:flex;justify-content:space-between;align-items:center"
                    >
                      <div>
                        <div style="font-size:13px;font-weight:600">
                          <span>{{ m.home_college }}</span>
                          <span style="margin:0 8px;color:#8e8e93">vs</span>
                          <span>{{ m.away_college }}</span>
                        </div>
                        <small style="color:#8e8e93">{{ m.court_venue }} | {{ m.sets_summary || (m.status==='FINISHED' ? `${m.home_score}:${m.away_score}` : (m.status==='FORFEIT' ? '弃权 0:5' : '打满5场')) }}</small>
                      </div>
                      <div style="display:flex;align-items:center;gap:10px">
                        <b style="font-size:15px;font-family:var(--font-mono)" :style="m.status==='FINISHED'?'color:var(--apple-blue)':''">
                          {{ m.home_score !== null ? `${m.home_score} : ${m.away_score}` : '— : —' }}
                        </b>
                        <el-button size="small" type="primary" plain @click="openEditTtTeamMatch(m)">
                          {{ m.status==='FINISHED' ? '修改比分' : '录入5盘比分' }}
                        </el-button>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- B组 -->
                <div style="background:#fcfcfd;border:1px solid rgba(0,0,0,0.06);border-radius:16px;padding:18px">
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
                    <h3 style="font-size:15px;margin:0;display:flex;align-items:center;gap:6px">
                      <span style="width:10px;height:10px;border-radius:50%;background:var(--apple-orange)"></span>
                      <span>第一阶段：B组循环赛与积分榜 (每组3队)</span>
                    </h3>
                    <small style="color:#8e8e93">胜2分·负1分·弃权0分</small>
                  </div>
                  <el-table :data="ttTeamStandings.groups?.group_b || []" size="small" style="margin-bottom:14px">
                    <el-table-column prop="rank" label="名次" width="50" align="center">
                      <template #default="s">
                        <b :style="s.row.rank===1 ? 'color:var(--apple-orange);font-weight:800' : ''">{{ s.row.rank }}</b>
                      </template>
                    </el-table-column>
                    <el-table-column prop="college" label="学院" min-width="90"/>
                    <el-table-column prop="played" label="场次" width="45" align="center"/>
                    <el-table-column prop="won" label="胜" width="40" align="center"/>
                    <el-table-column prop="lost" label="负" width="40" align="center"/>
                    <el-table-column prop="points" label="积分" width="50" align="center">
                      <template #default="s"><b style="color:var(--apple-orange);font-size:13px">{{ s.row.points }}</b></template>
                    </el-table-column>
                    <el-table-column prop="rubber_diff" label="净胜盘" width="55" align="center"/>
                    <el-table-column prop="set_ratio" label="局比" width="60" align="center"/>
                    <el-table-column label="状态" width="80" align="center">
                      <template #default="s">
                        <el-tag v-if="s.row.rank===1" size="small" type="success">小组第1</el-tag>
                        <el-tag v-else-if="ttTeamStandings.best_second?.team_id===s.row.team_id" size="small" type="warning">🌟 最好第2</el-tag>
                      </template>
                    </el-table-column>
                  </el-table>
                  <!-- B组赛程列表 -->
                  <div style="display:flex;flex-direction:column;gap:8px">
                    <div
                      v-for="m in ttTeamMatches.filter(i=>i.stage_type==='GROUP_B')"
                      :key="m.id"
                      style="background:#fff;border:1px solid rgba(0,0,0,0.06);border-radius:10px;padding:10px 14px;display:flex;justify-content:space-between;align-items:center"
                    >
                      <div>
                        <div style="font-size:13px;font-weight:600">
                          <span>{{ m.home_college }}</span>
                          <span style="margin:0 8px;color:#8e8e93">vs</span>
                          <span>{{ m.away_college }}</span>
                        </div>
                        <small style="color:#8e8e93">{{ m.court_venue }} | {{ m.sets_summary || (m.status==='FINISHED' ? `${m.home_score}:${m.away_score}` : (m.status==='FORFEIT' ? '弃权 0:5' : '打满5场')) }}</small>
                      </div>
                      <div style="display:flex;align-items:center;gap:10px">
                        <b style="font-size:15px;font-family:var(--font-mono)" :style="m.status==='FINISHED'?'color:var(--apple-orange)':''">
                          {{ m.home_score !== null ? `${m.home_score} : ${m.away_score}` : '— : —' }}
                        </b>
                        <el-button size="small" type="primary" plain @click="openEditTtTeamMatch(m)">
                          {{ m.status==='FINISHED' ? '修改比分' : '录入5盘比分' }}
                        </el-button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 第二阶段：交叉淘汰与前四名争夺 -->
              <div>
                <h3 style="font-size:15px;margin:0 0 12px;color:var(--apple-label)">第二阶段：交叉淘汰与总决赛 (争夺前四名)</h3>
                <div style="display:grid;grid-template-columns:repeat(4, 1fr);gap:14px">
                  <div v-for="m in ttTeamMatches.filter(i=>['SEMIFINAL','THIRD_PLACE','FINAL'].includes(i.stage_type))" :key="m.id" style="background:#fff;border:1px solid rgba(0,0,0,0.08);border-radius:12px;padding:14px;display:flex;flex-direction:column;justify-content:space-between">
                    <div>
                      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
                        <span style="font-size:11px;font-weight:700;color:var(--apple-blue)">{{ m.match_name }}</span>
                        <el-tag size="small" :type="m.status==='FINISHED'?'success':'info'">{{ m.status==='FINISHED'?'已完赛':'未开始' }}</el-tag>
                      </div>
                      <div style="display:flex;flex-direction:column;gap:6px;margin:10px 0">
                        <div style="display:flex;justify-content:space-between;align-items:center;padding:4px 8px;border-radius:6px" :style="m.winner_team_id===m.home_team_id?'background:rgba(52,199,89,0.12);font-weight:700':''">
                          <span>{{ m.home_college }}</span>
                          <b style="font-family:var(--font-mono)">{{ m.home_score !== null ? `${m.home_score}盘` : '—' }}</b>
                        </div>
                        <div style="display:flex;justify-content:space-between;align-items:center;padding:4px 8px;border-radius:6px" :style="m.winner_team_id===m.away_team_id?'background:rgba(52,199,89,0.12);font-weight:700':''">
                          <span>{{ m.away_college }}</span>
                          <b style="font-family:var(--font-mono)">{{ m.away_score !== null ? `${m.away_score}盘` : '—' }}</b>
                        </div>
                      </div>
                      <div v-if="m.sets_summary" style="font-size:11px;color:#8e8e93;margin-bottom:6px">
                        盘分: {{ m.sets_summary }}
                      </div>
                    </div>
                    <el-button type="primary" size="small" @click="openEditTtTeamMatch(m)" style="margin-top:8px">
                      {{ m.status==='FINISHED' ? '修改盘比分' : '录入打满5盘比分' }}
                    </el-button>
                  </div>
                </div>
              </div>
            </div>

            <!-- ===================== B/C. 单打比赛 Tab (男单 / 女单) ===================== -->
            <div v-else>
              <!-- 规则导引提示卡片 -->
              <div style="background:rgba(52,199,89,0.06);border:1px solid rgba(52,199,89,0.2);border-radius:12px;padding:14px 18px;margin-bottom:16px">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                  <b style="color:#248a3d;font-size:14px">🏓 {{ ttTab==='ms' ? '男子单打' : '女子单打' }} 竞赛规则与淘汰制切换指南</b>
                  <el-tag size="small" type="success">前三局后五局动态切换</el-tag>
                </div>
                <div style="font-size:12px;line-height:1.7;color:#48484a">
                  <b>1. 报名资格：</b>各学院男、女各上报 <b>3 名运动员</b>，报名时请将<b>种子选手排列在前（1、2、3 号种子）</b>；<br/>
                  <b>2. 签表编排：</b>系统根据种子排位与<b>同院回避原则</b>进行淘汰赛抽签编排；<br/>
                  <b>3. 动态局制：</b>单打前期淘汰赛（如 1/8 决赛）采用<b>三局两胜制（Best of 3）</b>，进入八强后（1/4 决赛、半决赛、季军赛、决赛）自动切换为<b>五局三胜制（Best of 5）</b>，每局 11 分制；<br/>
                  <b>4. 定稿归档：</b>决赛与季军赛结束后，一键定稿前四名/前八名并归档至大屏和个人中心。
                </div>
              </div>

              <!-- 单打项目选择与操作栏 -->
              <div class="apple-filter-bar" style="background:#f5f5f7;padding:12px 16px;border-radius:12px;margin-bottom:16px">
                <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
                  <el-select v-model="ttCurrentSinglesEventId" :placeholder="`选择${ttTab==='ms'?'男子':'女子'}单打项目`" style="width:240px">
                    <el-option v-for="e in ttCurrentSinglesEvents" :key="e.id" :label="`${e.name} (${e.code})`" :value="e.id"/>
                  </el-select>
                  <el-button type="success" plain @click="openCreateTtEventDialog(ttTab==='ms'?'MS':'WS')">
                    ➕ 新建{{ ttTab==='ms'?'男子':'女子' }}单打项目
                  </el-button>
                  <el-button type="primary" plain :disabled="!ttCurrentSinglesEventId" @click="openAddTtSinglesAthletesDialog">
                    👥 申报单打名单 ({{ ttSinglesAthletesData.athletes?.length || 0 }}人)
                  </el-button>
                  <el-button type="primary" :disabled="!ttCurrentSinglesEventId" @click="autoGenerateTtSinglesDraw">
                    🎲 种子排位与同院回避抽签编排
                  </el-button>
                </div>
                <div style="display:flex;gap:8px">
                  <el-button type="danger" :disabled="!ttCurrentSinglesEventId" @click="finalizeTtSinglesResults">
                    📦 定稿前四名成绩并归档
                  </el-button>
                </div>
              </div>

              <!-- 单打报名选手与种子排列展板 -->
              <div style="background:#fff;border:1px solid rgba(0,0,0,0.06);border-radius:14px;padding:14px;margin-bottom:16px">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
                  <b style="font-size:13px">📋 参赛选手名单与种子排位（每院 3 名选手）</b>
                  <el-tag size="small" type="info">共 {{ ttSinglesAthletesData.total_athletes || 0 }} 名选手</el-tag>
                </div>
                <div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(200px, 1fr));gap:10px">
                  <div
                    v-for="a in ttSinglesAthletesData.athletes"
                    :key="a.id"
                    style="background:#f9f9fb;border:1px solid rgba(0,0,0,0.05);border-radius:8px;padding:8px 12px;display:flex;justify-content:space-between;align-items:center"
                  >
                    <div>
                      <b style="font-size:13px">{{ a.student_name }}</b>
                      <small style="color:#8e8e93;display:block;font-size:11px">{{ a.college }}</small>
                    </div>
                    <el-tag size="small" :type="a.seed_order <= 3 ? 'warning' : 'info'">
                      {{ a.seed_label || `种子${a.seed_order}` }}
                    </el-tag>
                  </div>
                </div>
              </div>

              <!-- 淘汰赛对阵图与阶段赛程 -->
              <div v-if="ttSinglesMatches.length" style="display:flex;flex-direction:column;gap:16px">
                <div
                  v-for="stageKey in ['ROUND_OF_16', 'QUARTERFINAL', 'SEMIFINAL', 'THIRD_PLACE', 'FINAL']"
                  :key="stageKey"
                  v-show="ttSinglesMatches.some(m => m.stage_type === stageKey)"
                  style="background:#fcfcfd;border:1px solid rgba(0,0,0,0.06);border-radius:14px;padding:16px"
                >
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
                    <div style="display:flex;align-items:center;gap:8px">
                      <b style="font-size:14px">
                        {{ stageKey === 'ROUND_OF_16' ? '1/8 决赛' : (stageKey === 'QUARTERFINAL' ? '1/4 决赛 (八强战)' : (stageKey === 'SEMIFINAL' ? '半决赛 (四强战)' : (stageKey === 'THIRD_PLACE' ? '季军争夺战' : '冠亚军总决赛'))) }}
                      </b>
                      <el-tag size="small" :type="['QUARTERFINAL','SEMIFINAL','THIRD_PLACE','FINAL'].includes(stageKey)?'danger':'primary'">
                        {{ ['QUARTERFINAL','SEMIFINAL','THIRD_PLACE','FINAL'].includes(stageKey) ? '八强 · 五局三胜制 (11分)' : '前期 · 三局两胜制 (11分)' }}
                      </el-tag>
                    </div>
                    <el-button
                      v-if="['ROUND_OF_16', 'QUARTERFINAL', 'SEMIFINAL'].includes(stageKey)"
                      type="primary"
                      size="small"
                      plain
                      @click="advanceTtSinglesNextRound(stageKey)"
                    >
                      晋级下一轮 ➔
                    </el-button>
                  </div>

                  <!-- 比赛卡片网格 -->
                  <div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(280px, 1fr));gap:12px">
                    <div
                      v-for="m in ttSinglesMatches.filter(i=>i.stage_type===stageKey)"
                      :key="m.id"
                      style="background:#fff;border:1px solid rgba(0,0,0,0.07);border-radius:10px;padding:12px;display:flex;flex-direction:column;justify-content:space-between"
                    >
                      <div>
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
                          <small style="color:#8e8e93;font-weight:600">{{ m.match_name }}</small>
                          <el-tag size="small" :type="m.status==='FINISHED'?'success':'info'">{{ m.status==='FINISHED'?'已完赛':'未开始' }}</el-tag>
                        </div>
                        <div style="display:flex;flex-direction:column;gap:6px;margin:8px 0">
                          <div style="display:flex;justify-content:space-between;align-items:center;padding:4px 8px;border-radius:6px" :style="m.winner_student_id===m.home_student_id?'background:rgba(52,199,89,0.12);font-weight:700':''">
                            <span>{{ m.home_student_name }} <small style="color:#8e8e93">({{ m.home_college }})</small></span>
                            <b style="font-family:var(--font-mono)">{{ m.home_score !== null ? `${m.home_score}局` : '—' }}</b>
                          </div>
                          <div style="display:flex;justify-content:space-between;align-items:center;padding:4px 8px;border-radius:6px" :style="m.winner_student_id===m.away_student_id?'background:rgba(52,199,89,0.12);font-weight:700':''">
                            <span>{{ m.away_student_name }} <small style="color:#8e8e93">({{ m.away_college }})</small></span>
                            <b style="font-family:var(--font-mono)">{{ m.away_score !== null ? `${m.away_score}局` : '—' }}</b>
                          </div>
                        </div>
                        <div v-if="m.sets_summary" style="font-size:11px;color:#8e8e93;margin-bottom:6px">
                          局分明细: {{ m.sets_summary }}
                        </div>
                      </div>
                      <el-button type="primary" size="small" @click="openEditTtSinglesMatch(m)" style="margin-top:6px">
                        {{ m.status==='FINISHED' ? '修改比分' : '录入局分' }}
                      </el-button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </template>

        <!-- 9. 跳绳团体赛制 -->
        <template v-else-if="active === 'rope'">
          <RopeTableTools :key="selectedMeetId || 0" :meet-id="selectedMeetId" :event-id="ropeEventId" :events="ropeData.events" :can-manage="canCreateBusiness" @changed="loadRopeData"/>
          <!-- 竞赛规程总览 (三项并列卡片) -->
          <section class="mac-card panel" style="margin-bottom:14px">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
              <div>
                <h3 style="margin:0 0 4px;font-size:16px">🪢 学院跳绳团体赛竞赛规程</h3>
                <p style="margin:0;font-size:12px;color:#8e8e93">以学院为单位参赛，每队22人；系统自动校验各分项人数、角色及跳绳者男女比例</p>
              </div>
              <div style="display:flex;gap:10px;align-items:center">
                <el-select v-model="selectedMeetId" placeholder="选择运动会届次" style="width:240px" @change="onSelectedMeetChange">
                  <el-option v-for="m in meets" :key="m.id" :label="`${m.name}（${m.edition}）`" :value="m.id"/>
                </el-select>
                <el-button v-if="canCreateBusiness" @click="goToRopeRoster">👥 维护22人总队</el-button>
                <el-button v-if="canCreateBusiness" type="primary" :icon="CirclePlus" @click="initializeRopeEvents">⚡ 初始化/同步跳绳赛制</el-button>
              </div>
            </div>
            <!-- 三项并列规程卡片 -->
            <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px">
              <!-- 1. 前单跳 -->
              <div style="background:linear-gradient(135deg,rgba(0,122,255,.07),rgba(0,122,255,.03));border:1px solid rgba(0,122,255,.2);border-radius:14px;padding:16px">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
                  <span style="width:32px;height:32px;background:var(--apple-blue);border-radius:8px;display:grid;place-items:center;font-size:16px">🏃</span>
                  <div>
                    <div style="font-weight:700;font-size:14px;color:var(--apple-blue)">"前单跳"计时计数团体挑战赛</div>
                    <div style="font-size:11px;color:#8e8e93">ROPE_SINGLE</div>
                  </div>
                </div>
                <div style="font-size:12.5px;line-height:2;color:#3a3a3c">
                  <div>👥 <b>出场人数：</b>10人（男5人 + 女5人）</div>
                  <div>⏱️ <b>比赛时间：</b>每人1分钟计时计数</div>
                  <div>📊 <b>排名规则：</b>团体总次数多者名次列前</div>
                  <div>🔄 <b>同成绩：</b>并列队伍平均所占名次积分</div>
                  <div style="margin-top:6px;padding:6px 10px;background:rgba(0,122,255,.1);border-radius:6px;font-size:11.5px;color:var(--apple-blue)">
                    💡 从22人总队中选派10人上场，阵容中摇绳者为0人
                  </div>
                </div>
              </div>
              <!-- 2. 集体单摇跳 -->
              <div style="background:linear-gradient(135deg,rgba(255,149,0,.07),rgba(255,149,0,.03));border:1px solid rgba(255,149,0,.25);border-radius:14px;padding:16px">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
                  <span style="width:32px;height:32px;background:var(--apple-orange);border-radius:8px;display:grid;place-items:center;font-size:16px">🪢</span>
                  <div>
                    <div style="font-weight:700;font-size:14px;color:var(--apple-orange)">集体单摇跳</div>
                    <div style="font-size:11px;color:#8e8e93">ROPE_SYNC</div>
                  </div>
                </div>
                <div style="font-size:12.5px;line-height:2;color:#3a3a3c">
                  <div>👥 <b>出场人数：</b>12人（摇绳2人性别不限 + 跳绳男5女5）</div>
                  <div>⏱️ <b>比赛时间：</b>5分钟，目标30次有效跳动</div>
                  <div>📊 <b>排名规则①：</b>5分钟内完成30次 → 用时少者列前</div>
                  <div>📊 <b>排名规则②：</b>未完成 → 有效次数多者列前（排在完成队之后）</div>
                  <div style="margin-top:6px;padding:6px 10px;background:rgba(255,149,0,.1);border-radius:6px;font-size:11.5px;color:#b35900">
                    💡 摇绳者与跳绳者可以更换，中途不得改变跳绳者的先后顺序
                  </div>
                </div>
              </div>
              <!-- 3. "8"字环绕跳 -->
              <div style="background:linear-gradient(135deg,rgba(52,199,89,.07),rgba(52,199,89,.03));border:1px solid rgba(52,199,89,.25);border-radius:14px;padding:16px">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
                  <span style="width:32px;height:32px;background:#34c759;border-radius:8px;display:grid;place-items:center;font-size:16px">8️⃣</span>
                  <div>
                    <div style="font-weight:700;font-size:14px;color:#1b6e2d">"8"字环绕跳</div>
                    <div style="font-size:11px;color:#8e8e93">ROPE_FIG8</div>
                  </div>
                </div>
                <div style="font-size:12.5px;line-height:2;color:#3a3a3c">
                  <div>👥 <b>出场人数：</b>22人（摇绳2人性别不限 + 跳绳男10女10）</div>
                  <div>⏱️ <b>比赛时间：</b>5分钟</div>
                  <div>📊 <b>排名规则：</b>全队有效完成次数多者名次列前</div>
                  <div>🔄 <b>同成绩：</b>并列队伍平均所占名次积分</div>
                  <div style="margin-top:6px;padding:6px 10px;background:rgba(52,199,89,.1);border-radius:6px;font-size:11.5px;color:#1b6e2d">
                    💡 按"8"字围绕方式，中途不得随意改变顺序；摇绳人与跳绳人可自主更换
                  </div>
                </div>
              </div>
            </div>
          </section>

          <!-- 操作区 -->
          <section class="mac-card panel" style="margin-bottom:18px">
            <el-empty v-if="!ropeData.events.length" :description="canCreateBusiness ? '当前运动会尚未初始化跳绳赛制，请点击右上角按钮一键建立三个跳绳项目' : '当前运动会尚未初始化跳绳赛制，请联系体育部老师或开发人员进行初始化'">
              <el-button v-if="canCreateBusiness" type="primary" size="large" @click="initializeRopeEvents">⚡ 立即建立三个跳绳项目 + 自动创建计分模型</el-button>
            </el-empty>
            <template v-else>
              <!-- 操作步骤引导 -->
              <div style="background:#f9f9fb;border:1px solid rgba(0,0,0,.06);border-radius:12px;padding:12px 16px;margin-bottom:16px">
                <div style="font-size:12px;color:#48484a;display:flex;gap:20px;align-items:center;flex-wrap:wrap">
                  <span style="font-weight:700;color:var(--apple-label)">操作流程：</span>
                  <span>① 在"名单录入"中为各学院建立 <b>22人通用代表队</b></span>
                  <span style="color:#8e8e93">→</span>
                  <span>② 点击【配置阵容】为各学院分配各分项的跳绳者/摇绳者</span>
                  <span style="color:#8e8e93">→</span>
                  <span>③ 点击【录入成绩】进入成绩工作台录入比赛结果</span>
                  <span style="color:#8e8e93">→</span>
                  <span>④ 提交审核 → 终审发布大屏</span>
                </div>
              </div>
              <!-- 分项切换 -->
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
                <el-radio-group v-model="ropeEventId" size="large">
                  <el-radio-button v-for="event in ropeData.events" :key="event.id" :value="event.id">{{ event.rule.title }}</el-radio-button>
                </el-radio-group>
                <el-button type="success" @click="goToRopeResults()">📊 进入本项目成绩录入工作台</el-button>
              </div>
              <!-- 当前分项规程说明 -->
              <div v-if="selectedRopeEvent" style="background:rgba(0,122,255,.055);border:1px solid rgba(0,122,255,.18);border-radius:12px;padding:12px 16px;margin-bottom:16px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px">
                <div style="font-size:13px;color:#3a3a3c;line-height:1.8">
                  <b style="color:var(--apple-blue)">{{ selectedRopeEvent.rule.title }}</b>
                  <span style="margin:0 8px;color:#c7c7cc">|</span>
                  阵容：<b>{{ selectedRopeEvent.rule.lineup_size }}</b> 人
                  （跳绳者 <b>{{ selectedRopeEvent.rule.jumper_count }}</b> 人：男 {{ selectedRopeEvent.rule.male_jumpers }}、女 {{ selectedRopeEvent.rule.female_jumpers }}；
                  摇绳者 <b>{{ selectedRopeEvent.rule.turner_count }}</b> 人，性别不限）
                  <span style="margin:0 8px;color:#c7c7cc">|</span>
                  比赛时长：<b>{{ selectedRopeEvent.rule.duration_seconds >= 300 ? '5分钟' : selectedRopeEvent.rule.duration_seconds + '秒/人' }}</b>
                </div>
                <el-tag type="info" size="small">前8名 9-7-6-5-4-3-2-1分</el-tag>
              </div>
              <!-- 各学院状态表 -->
              <el-table :data="selectedRopeEvent?.teams || []" stripe border style="width:100%">
                <el-table-column prop="college" label="参赛学院" min-width="140"/>
                <el-table-column prop="team_name" label="代表队名称" min-width="170"/>
                <el-table-column label="22人总队" width="110" align="center">
                  <template #default="s">
                    <el-tag :type="s.row.members.length === 22 ? 'success' : 'danger'" size="small">
                      {{ s.row.members.length }}/22人
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="分项阵容校验" min-width="240">
                  <template #default="s">
                    <div v-if="s.row.lineup_status.valid" style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
                      <el-tag type="success" size="small">✓ 校验通过</el-tag>
                      <span style="font-size:12px;color:#666">跳绳{{ s.row.lineup_status.jumper_count }}人（男{{ s.row.lineup_status.male_jumpers }}/女{{ s.row.lineup_status.female_jumpers }}）· 摇绳{{ s.row.lineup_status.turner_count }}人</span>
                    </div>
                    <div v-else style="font-size:12px;color:#d93025;line-height:1.5">
                      <el-tag type="danger" size="small" style="margin-bottom:3px">待配置</el-tag>
                      <div>{{ s.row.lineup_status.errors.join('；') }}</div>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="当前成绩" width="170" align="center">
                  <template #default="s">
                    <span v-if="s.row.result" style="font-size:13px">
                      <b style="color:var(--apple-blue)">第{{ s.row.result.rank || '—' }}名</b>
                      · {{ ropeResultText(s.row.result) }}
                    </span>
                    <span v-else style="color:#8e8e93;font-size:12px">暂未录入</span>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="160" fixed="right" align="center">
                  <template #default="s">
                    <div style="display:flex;gap:6px;justify-content:center">
                      <el-button v-if="canCreateBusiness" link type="primary" size="small" @click="openRopeLineup(s.row)">配置阵容</el-button>
                      <el-button link type="success" size="small" @click="goToRopeResults(selectedRopeEvent)">录入成绩</el-button>
                    </div>
                  </template>
                </el-table-column>
              </el-table>
            </template>
          </section>
        </template>


        <!-- 10. 赛程管理 -->
        <template v-else-if="active === 'schedules'">
          <section class="mac-card panel">
            <div class="mac-card-head">
              <div><h3>项目赛程管理</h3><p>发布后同步公开至个人中心与成绩大屏</p></div>
              <el-button type="primary" :icon="CirclePlus" :disabled="!canScheduleAny" @click="openScheduleDialog()">发布赛程</el-button>
            </div>
            <el-table :data="schedules">
              <el-table-column label="项目" min-width="160"><template #default="s">{{ eventName(s.row.event_id) }}</template></el-table-column>
              <el-table-column prop="round_name" label="轮次" width="100"/>
              <el-table-column label="比赛时间" width="160"><template #default="s">{{ formatDate(s.row.competition_at) }}</template></el-table-column>
              <el-table-column label="检录时间" width="160"><template #default="s">{{ formatDate(s.row.check_in_at) }}</template></el-table-column>
              <el-table-column prop="venue" label="比赛场地" min-width="150"/>
              <el-table-column label="状态" width="100"><template #default="s"><el-tag :type="tagType(s.row.status)">{{ scheduleStatusLabel[s.row.status] || s.row.status }}</el-tag></template></el-table-column>
              <el-table-column label="操作" width="140" fixed="right">
                <template #default="s">
                  <el-button link type="primary" :disabled="!canScheduleEvent(s.row.event_id)" @click="openScheduleDialog(s.row)">编辑</el-button>
                  <el-button link type="danger" :disabled="!canScheduleEvent(s.row.event_id)" @click="deleteSchedule(s.row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </section>
        </template>

        <!-- 10. 成绩工作台 -->
        <template v-else-if="active === 'results'">
          <section class="mac-card panel">
            <div class="apple-filter-bar">
              <div style="display:flex;gap:12px">
                <el-select v-model="selectedEventId" filterable placeholder="选择比赛项目" style="width:300px">
                  <el-option v-for="e in availableEvents" :key="e.id" :label="`${e.name} · ${eventTypeLabel[e.event_type]}`" :value="e.id"/>
                </el-select>
                <el-select v-model="selectedResultRoundId" placeholder="轮次" style="width:130px">
                  <el-option v-for="r in rounds" :key="r.id" :label="r.name" :value="r.id"/>
                </el-select>
              </div>
              <div style="display:flex;gap:8px">
                <el-button :icon="Download" :disabled="!canExportSelected" @click="exportResults">导出正式成绩单</el-button>
                <el-button type="primary" :icon="CirclePlus" :disabled="!canScoreSelected" @click="openResultEntry()">录入成绩</el-button>
              </div>
            </div>
            <div style="margin-bottom:14px;display:flex;gap:8px;align-items:center">
              <el-button type="warning" size="small" :disabled="!selectedResultIds.length || !canScoreSelected" @click="resultAction('submit')">提交送审</el-button>
              <el-button type="primary" size="small" :disabled="!selectedResultIds.length || !canReviewSelected" @click="resultAction('review', true)">裁判审核通过</el-button>
              <el-button type="danger" size="small" :disabled="!selectedResultIds.length || !canReviewSelected" @click="resultAction('review', false)">退回修改</el-button>
              <el-button type="success" size="small" :disabled="!selectedResultIds.length || !canCreateBusiness" @click="resultAction('publish')">终审发布大屏</el-button>
              <el-button type="info" size="small" :disabled="!selectedResultIds.length || !canCreateBusiness" @click="resultAction('unpublish')">撤回发布/下架大屏</el-button>
              <span style="font-size:12px;color:#8e8e93;margin-left:8px">已选择 {{ selectedResultIds.length }} 项</span>
            </div>
            <el-table :data="results" @selection-change="onResultSelectionChange" stripe>
              <el-table-column type="selection" width="40"/>
              <el-table-column label="名次" width="65" align="center"><template #default="s"><b>{{ s.row.rank || '—' }}</b></template></el-table-column>
              <el-table-column prop="name" label="姓名/代表队" min-width="120"/>
              <el-table-column prop="student_no" label="学号" width="125"/>
              <el-table-column prop="college" label="学院" min-width="140"/>
              <el-table-column prop="heat" label="组次" width="75" align="center"/>
              <el-table-column prop="lane" label="道次" width="75" align="center"/>
              <el-table-column label="原始成绩" min-width="130">
                <template #default="s">
                  <b style="font-family:var(--font-mono)">{{ ropeResultText(s.row) }}</b>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="95" align="center"><template #default="s">{{ competitionStatusLabel[s.row.competition_status] }}</template></el-table-column>
              <el-table-column prop="points" label="积分" width="70" align="center"/>
              <el-table-column label="流转" width="95" align="center"><template #default="s"><el-tag :type="tagType(s.row.state)" size="small">{{ resultStateLabel[s.row.state] }}</el-tag></template></el-table-column>
              <el-table-column label="操作" width="160">
                <template #default="s">
                  <div style="display: flex; gap: 8px; align-items: center;">
                    <el-button link type="primary" :disabled="!canScoreSelected" @click="openResultEntry(s.row)">编辑</el-button>
                    <el-button v-if="s.row.state === 'PUBLISHED'" link type="primary" :disabled="!canCreateBusiness" @click="unpublishSingleResult(s.row)">下架大屏</el-button>
                    <el-button v-else link type="danger" :disabled="!canScoreSelected" @click="deleteResult(s.row)">删除</el-button>
                  </div>
                </template>
              </el-table-column>
            </el-table>
          </section>
        </template>

        <!-- 11. 学生赛事 -->
        <template v-else-if="active === 'student-events'">
          <section class="mac-card panel">
            <div class="mac-card-head"><div><h3>我的参赛项目与赛程</h3></div></div>
            <div class="apple-grid-three">
              <article v-for="item in studentEvents" :key="item.registration_id" class="apple-assign-card panel">
                <div class="sf-badge blue"><el-icon><Calendar/></el-icon></div>
                <div>
                  <el-tag size="small">{{ item.event_type === 'RELAY' ? '接力' : '个人' }}</el-tag>
                  <h3>{{ item.event_name }}</h3>
                  <p><el-icon><Calendar/></el-icon> 检录: {{ formatDate(item.check_in_at) }}</p>
                </div>
              </article>
            </div>
          </section>
        </template>

        <!-- 12. 学生成绩 -->
        <template v-else-if="active === 'student-results'">
          <section class="mac-card panel">
            <div class="mac-card-head"><div><h3>我的历史成绩</h3></div></div>
            <el-table :data="studentResults">
              <el-table-column prop="event_name" label="项目名称" min-width="160"/>
              <el-table-column prop="round_name" label="轮次" width="100"/>
              <el-table-column label="成绩" width="140"><template #default="s"><b>{{ s.row.raw_value }} {{ s.row.unit }}</b></template></el-table-column>
              <el-table-column label="名次" width="90"><template #default="s"><b>{{ s.row.rank || '—' }}</b></template></el-table-column>
              <el-table-column prop="points" label="积分" width="90"/>
              <el-table-column label="发布时间" width="160"><template #default="s">{{ formatDate(s.row.published_at) }}</template></el-table-column>
            </el-table>
          </section>
        </template>

        <!-- 13. 日志 -->
        <template v-else-if="active === 'logs'">
          <section class="mac-card panel">
            <div class="mac-card-head"><div><h3>审计日志</h3></div></div>
            <el-table :data="logs">
              <el-table-column prop="created_at" label="时间" width="160"><template #default="s">{{ formatDate(s.row.created_at) }}</template></el-table-column>
              <el-table-column prop="actor" label="操作人" width="130"/>
              <el-table-column prop="action" label="动作" width="160"/>
              <el-table-column prop="target_type" label="目标" width="130"/>
              <el-table-column prop="reason" label="备注" min-width="200"><template #default="s">{{ s.row.reason || '—' }}</template></el-table-column>
            </el-table>
          </section>
        </template>

        <!-- 14. AI 智能中心 -->
        <template v-else-if="active === 'ai-center'">
          <AiCenter />
        </template>
      </div>
    </main>

    <!-- 全局 AI 赛事协同抽屉 -->
    <AiCopilotDrawer
      v-model="aiDrawerVisible"
      :current-meet-id="selectedMeetId"
      :current-event-id="selectedEventId"
      :current-page="active"
    />

    <!-- 全局 AI 赛事协同悬浮按钮 -->
    <button
      class="apple-ai-floating-fab"
      @click="aiDrawerVisible = true"
      title="唤起 AI 赛事协同助手"
    >
      <div class="fab-pulse"></div>
      <el-icon><ChatDotRound/></el-icon>
      <span class="fab-label">AI 协同</span>
    </button>

    <!-- 业务表单弹窗 -->
    <el-dialog v-model="accountDialog" :title="accountEditingId ? '编辑账号' : '创建新账号'" width="520px">
      <el-form label-position="top" class="apple-dialog-form">
        <el-form-item label="用户名"><el-input v-model="accountForm.username" :disabled="!!accountEditingId"/></el-form-item>
        <el-form-item label="姓名"><el-input v-model="accountForm.display_name"/></el-form-item>
        <el-form-item v-if="!accountEditingId && accountForm.role === 'STUDENT'" label="初始密码"><el-input :model-value="`DF${accountForm.username}`" disabled/></el-form-item>
        <el-form-item v-else label="密码"><el-input v-model="accountForm.password" type="password" show-password/></el-form-item>
        <el-form-item label="角色"><el-select v-model="accountForm.role"><el-option v-for="(lbl, key) in roleLabel" :key="key" :label="lbl" :value="key"/></el-select></el-form-item>
        <el-form-item label="部门"><el-input v-model="accountForm.department"/></el-form-item>
        <div v-if="accountForm.role !== 'DEVELOPER' && accountForm.role !== 'STUDENT'" style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
          <el-form-item label="工号"><el-input v-model="accountForm.employee_no" placeholder="留空则自动生成"/></el-form-item>
          <el-form-item label="联系电话"><el-input v-model="accountForm.phone"/></el-form-item>
        </div>
      </el-form>
      <template #footer><el-button @click="accountDialog = false">取消</el-button><el-button type="primary" @click="saveAccount">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="studentRosterDialog" :title="studentRosterEditingId ? '编辑学生资料' : '新增学生资料'" width="520px">
      <el-form label-position="top" class="apple-dialog-form">
        <el-form-item label="学号"><el-input v-model="studentRosterForm.student_no"/></el-form-item>
        <el-form-item label="姓名"><el-input v-model="studentRosterForm.name"/></el-form-item>
        <el-form-item label="性别"><el-select v-model="studentRosterForm.gender"><el-option label="男" value="男"/><el-option label="女" value="女"/></el-select></el-form-item>
        <el-form-item label="学院"><el-input v-model="studentRosterForm.college"/></el-form-item>
        <el-form-item label="专业"><el-input v-model="studentRosterForm.major"/></el-form-item>
        <el-form-item label="班级"><el-input v-model="studentRosterForm.class_name"/></el-form-item>
      </el-form>
      <template #footer><el-button @click="studentRosterDialog = false">取消</el-button><el-button type="primary" @click="saveStudentRoster">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="collegeTeamDialog" :title="collegeTeamEditingId ? '✏️ 编辑学院代表队信息' : '➕ 新增学院代表队'" width="540px">
      <el-form label-position="top" class="apple-dialog-form">
        <el-form-item label="所属运动会届次" required>
          <el-select v-model="collegeTeamForm.meet_id" style="width:100%" placeholder="请选择运动会">
            <el-option v-for="m in meets" :key="m.id" :label="`${m.name} (${m.edition}届)`" :value="m.id"/>
          </el-select>
        </el-form-item>
        <el-form-item label="所属比赛项目 (细分不同赛制代表队)">
          <el-select v-model="collegeTeamForm.event_id" clearable placeholder="全能/通用代表队 (未绑定特定项目)" style="width:100%" @change="onCollegeTeamCollegeOrEventChange">
            <el-option :value="null" label="🏛️ 全能/通用学院代表队 (默认)"/>
            <el-option v-for="e in eventsForTeamMeet" :key="e.id" :label="`${e.name.includes('篮球') ? '🏀 ' : (e.name.includes('排球') ? '🏐 ' : (e.name.includes('乒乓') ? '🏓 ' : '🏃 '))}${e.name} (${e.code})`" :value="e.id"/>
          </el-select>
        </el-form-item>
        <el-form-item label="参赛学院" required>
          <el-select
            v-model="collegeTeamForm.college"
            filterable
            allow-create
            default-first-option
            placeholder="请选择或输入学院名称"
            style="width:100%"
            @change="onCollegeTeamCollegeOrEventChange"
          >
            <el-option v-for="c in distinctColleges" :key="c" :label="c" :value="c"/>
          </el-select>
        </el-form-item>
        <el-form-item label="代表队名称" required>
          <el-input v-model="collegeTeamForm.team_name" placeholder="例如：计算机学院男篮队 / 软件学院排球队 / 计算机学院代表队"/>
        </el-form-item>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
          <el-form-item label="领队姓名">
            <el-input v-model="collegeTeamForm.leader_name" placeholder="例如：张老师 / 队长"/>
          </el-form-item>
          <el-form-item label="领队联系电话">
            <el-input v-model="collegeTeamForm.leader_phone" placeholder="例如：13800000000"/>
          </el-form-item>
        </div>
        <el-form-item label="队伍备注说明">
          <el-input v-model="collegeTeamForm.notes" type="textarea" :rows="2" placeholder="可选备注，例如：主力队员安排、男女生协调等"/>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="collegeTeamDialog = false">取消</el-button>
        <el-button type="primary" @click="saveCollegeTeam">保存代表队</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="registrationDialog" :title="`选择加入【${rosterEvent?.name || ''}】`" width="600px">
      <el-table :data="eventRosterCandidates" max-height="300" @selection-change="onRegistrationSelectionChange">
        <el-table-column type="selection" width="45"/>
        <el-table-column prop="name" label="姓名/代表队" min-width="140"/>
        <el-table-column prop="college" label="学院" min-width="150"/>
      </el-table>
      <template #footer><el-button @click="registrationDialog = false">取消</el-button><el-button type="primary" :disabled="!registrationParticipantIds.length" @click="addEventRegistrations">确定加入</el-button></template>
    </el-dialog>

    <el-dialog v-model="registrationEditDialog" title="编辑参赛分组信息" width="480px">
      <el-form label-position="top" class="apple-dialog-form">
        <el-form-item label="组次"><el-input v-model="registrationEditForm.heat"/></el-form-item>
        <el-form-item label="道次"><el-input v-model="registrationEditForm.lane"/></el-form-item>
      </el-form>
      <template #footer><el-button @click="registrationEditDialog = false">取消</el-button><el-button type="primary" @click="updateEventRegistration">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="meetDialog" :title="meetEditingId ? '编辑运动会' : '新建运动会'" width="620px">
      <el-form label-position="top" class="apple-dialog-form">
        <el-form-item label="运动会名称"><el-input v-model="meetForm.name"/></el-form-item>
        <el-form-item label="年度/届次标识"><el-input v-model="meetForm.edition" placeholder="例如：2026、2026春季、第3届"/></el-form-item>
        <el-form-item label="开始日期"><el-date-picker v-model="meetForm.start_date" type="date" value-format="YYYY-MM-DD" style="width:100%"/></el-form-item>
        <el-form-item label="结束日期"><el-date-picker v-model="meetForm.end_date" type="date" value-format="YYYY-MM-DD" style="width:100%"/></el-form-item>
        <el-form-item label="赛事状态">
          <el-select v-model="meetForm.status" style="width:100%">
            <el-option label="筹备中" value="PREPARING"/><el-option label="报名中" value="REGISTRATION"/><el-option label="比赛中" value="COMPETING"/><el-option label="已结束" value="FINISHED"/>
          </el-select>
        </el-form-item>
        <el-form-item label="公开展示"><el-switch v-model="meetForm.public_visible" active-text="公开" inactive-text="隐藏"/></el-form-item>
      </el-form>
      <div style="margin-top:-8px;color:#8e8e93;font-size:13px">同一年度可以创建多场不同名称、不同类型的运动会。</div>
      <template #footer><el-button :disabled="meetSaving" @click="meetDialog = false">取消</el-button><el-button type="primary" :loading="meetSaving" @click="saveMeet">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="eventDialog" :title="eventEditingId ? '编辑比赛项目' : '新建比赛项目'" width="560px">
      <el-form label-position="top" class="apple-dialog-form">
        <el-form-item label="所属运动会" style="grid-column:1 / -1">
          <el-select v-model="eventForm.meet_id" placeholder="请选择本项目所属的运动会" style="width:100%">
            <el-option v-for="m in meets" :key="m.id" :label="`${m.name}（${m.edition}）`" :value="m.id"/>
          </el-select>
        </el-form-item>
        <el-form-item label="项目编号"><el-input v-model="eventForm.code"/></el-form-item>
        <el-form-item label="项目名称"><el-input v-model="eventForm.name"/></el-form-item>
        <el-form-item label="项目类型"><el-select v-model="eventForm.event_type" style="width:100%"><el-option label="个人项目" value="INDIVIDUAL"/><el-option label="接力项目" value="RELAY"/><el-option label="团体项目" value="TEAM"/></el-select></el-form-item>
        <el-form-item label="组别"><el-select v-model="eventForm.gender_group" style="width:100%"><el-option label="男子组" value="MALE"/><el-option label="女子组" value="FEMALE"/><el-option label="混合组" value="MIXED"/></el-select></el-form-item>
        <el-form-item label="成绩单位"><el-input v-model="eventForm.result_unit"/></el-form-item>
        <el-form-item label="排名方向"><el-select v-model="eventForm.sort_direction" style="width:100%"><el-option label="数值小者在前" value="ASC"/><el-option label="数值大者在前" value="DESC"/></el-select></el-form-item>
        <el-form-item label="晋级人数"><el-input-number v-model="eventForm.qualification_count" :min="0" :max="100" style="width:100%"/></el-form-item>
        <el-form-item label="录取名次"><el-input-number v-model="eventForm.scoring_places" :min="1" :max="100" style="width:100%"/></el-form-item>
      </el-form>
      <template #footer><el-button :disabled="eventSaving" @click="eventDialog = false">取消</el-button><el-button type="primary" :loading="eventSaving" @click="saveEvent">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="modelDialog" title="编辑计分模型" width="500px">
      <el-form label-position="top">
        <el-form-item label="模型名称"><el-input v-model="modelForm.name"/></el-form-item>
        <el-form-item label="名次积分(逗号分隔)"><el-input v-model="modelForm.pointsText"/></el-form-item>
      </el-form>
      <template #footer><el-button @click="modelDialog = false">取消</el-button><el-button type="primary" @click="saveModel">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="permissionDialog" title="分配项目权限" width="480px">
      <el-form label-position="top">
        <el-form-item label="管理人员"><el-select v-model="permissionForm.user_id" filterable><el-option v-for="m in managers" :key="m.id" :label="m.display_name" :value="m.id"/></el-select></el-form-item>
        <el-form-item label="比赛项目"><el-select v-model="permissionForm.event_id" filterable><el-option v-for="e in events" :key="e.id" :label="e.name" :value="e.id"/></el-select></el-form-item>
      </el-form>
      <template #footer><el-button @click="permissionDialog = false">取消</el-button><el-button type="primary" @click="savePermission">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="scheduleDialog" title="发布赛程" width="520px">
      <el-form label-position="top" class="apple-dialog-form">
        <el-form-item label="比赛项目" style="grid-column:1 / -1"><el-select v-model="scheduleForm.event_id" filterable style="width:100%"><el-option v-for="e in schedulableEvents" :key="e.id" :label="e.name" :value="e.id"/></el-select></el-form-item>
        <el-form-item label="比赛轮次"><el-select v-model="scheduleForm.round_id" style="width:100%"><el-option v-for="r in scheduleRounds" :key="r.id" :label="r.name" :value="r.id"/></el-select></el-form-item>
        <el-form-item label="赛程状态"><el-select v-model="scheduleForm.status" style="width:100%"><el-option v-for="(label, key) in scheduleStatusLabel" :key="key" :label="label" :value="key"/></el-select></el-form-item>
        <el-form-item label="比赛时间"><el-date-picker v-model="scheduleForm.competition_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%"/></el-form-item>
        <el-form-item label="检录时间"><el-date-picker v-model="scheduleForm.check_in_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width:100%"/></el-form-item>
        <el-form-item label="比赛场地"><el-input v-model="scheduleForm.venue"/></el-form-item>
        <el-form-item label="组次"><el-input v-model="scheduleForm.heat" placeholder="可选，例如：第1组"/></el-form-item>
        <el-form-item label="备注" style="grid-column:1 / -1"><el-input v-model="scheduleForm.notes" type="textarea" :rows="2"/></el-form-item>
        <el-form-item label="公开发布"><el-switch v-model="scheduleForm.published" active-text="公开" inactive-text="暂不公开"/></el-form-item>
      </el-form>
      <template #footer><el-button @click="scheduleDialog = false">取消</el-button><el-button type="primary" @click="saveSchedule">保存</el-button></template>
    </el-dialog>

    <!-- 📊 成绩录入与跳绳专属录入弹窗 -->
    <el-dialog v-model="resultDialog" :title="ropeHelper.isRopeSingle ? '🪢 跳绳“前单跳”团体赛成绩录入 (男女各5人)' : (ropeHelper.isRopeSync ? '🪢 跳绳“集体单摇跳”成绩录入 (12人·5分钟30次)' : (ropeHelper.isRopeFig8 ? '🪢 跳绳“8”字环绕跳成绩录入 (22人·5分钟总次数)' : '成绩录入'))" width="600px">
      <el-form label-position="top" class="apple-dialog-form">
        <el-form-item label="比赛轮次">
          <el-select v-model="resultForm.round_id" :disabled="!!resultEditingId" style="width:100%">
            <el-option v-for="round in rounds" :key="round.id" :label="round.name" :value="round.id"/>
          </el-select>
        </el-form-item>
        <el-form-item label="参赛运动员/学院代表队">
          <el-select v-model="resultForm.registration_id" :disabled="!!resultEditingId" filterable style="width:100%" placeholder="请选择参赛对象">
            <el-option v-for="registration in resultRegistrations" :key="registration.id" :label="`${registration.student.name}（${registration.student.college}）`" :value="registration.id"/>
          </el-select>
        </el-form-item>
        <!-- 1. 前单跳专属求和器 (男女各5人) -->
        <div v-if="ropeHelper.isRopeSingle" style="grid-column:1 / -1;background:#f9f9fb;border:1px solid #e5e5ea;border-radius:12px;padding:14px;margin-bottom:16px">
          <div style="font-size:13px;font-weight:700;color:var(--apple-blue);margin-bottom:8px">
            🏃‍♂️ 10人单人一分钟跳绳次数录入（系统自动累加全队总次数）：
          </div>
          
          <!-- 男生 5 人 -->
          <div style="margin-bottom:10px">
            <div style="font-size:12px;font-weight:600;color:#1c1c1e;margin-bottom:4px">🔵 男生组（5人）：</div>
            <div style="display:grid;grid-template-columns:repeat(5, 1fr);gap:6px">
              <div v-for="i in 5" :key="'m'+i">
                <div style="font-size:11px;margin-bottom:4px" :title="ropeEntryJumpers[i-1]?.student_no">男{{ i }} · {{ ropeEntryJumpers[i-1]?.name || '待选择队伍' }}</div>
                <el-input-number v-model="ropeHelper.maleScores[i-1]" :min="0" :max="500" :controls="false" size="small" :placeholder="`男${i}`" style="width:100%"/>
              </div>
            </div>
          </div>

          <!-- 女生 5 人 -->
          <div style="margin-bottom:12px">
            <div style="font-size:12px;font-weight:600;color:#1c1c1e;margin-bottom:4px">🔴 女生组（5人）：</div>
            <div style="display:grid;grid-template-columns:repeat(5, 1fr);gap:6px">
              <div v-for="i in 5" :key="'f'+i">
                <div style="font-size:11px;margin-bottom:4px" :title="ropeEntryJumpers[i+4]?.student_no">女{{ i }} · {{ ropeEntryJumpers[i+4]?.name || '待选择队伍' }}</div>
                <el-input-number v-model="ropeHelper.femaleScores[i-1]" :min="0" :max="500" :controls="false" size="small" :placeholder="`女${i}`" style="width:100%"/>
              </div>
            </div>
          </div>

          <div style="display:flex;justify-content:space-between;align-items:center;background:#fff;border:1px dashed var(--apple-blue);border-radius:8px;padding:8px 12px">
            <span style="font-size:13px">10 人累计总次数：<b style="color:var(--apple-blue);font-size:16px">{{ ropeSingleTotal }}</b> 次</span>
            <el-button size="small" type="primary" @click="applyRopeSingleTotal">一键同步填入总成绩</el-button>
          </div>
        </div>

        <!-- 2. 集体单摇跳专属 (30次用时 / 未完次数) -->
        <div v-else-if="ropeHelper.isRopeSync" style="grid-column:1 / -1;background:#f9f9fb;border:1px solid #e5e5ea;border-radius:12px;padding:14px;margin-bottom:16px">
          <div style="font-size:13px;font-weight:700;color:var(--apple-orange);margin-bottom:10px">
            ⏱️ 5分钟30次有效跳动比赛结果判定：
          </div>
          <el-radio-group v-model="ropeHelper.syncCompleted" style="margin-bottom:12px">
            <el-radio :value="true">✅ 5分钟内完成30次（录入用时，用时短者排前）</el-radio>
            <el-radio :value="false">⚠️ 5分钟未完成30次（录入完成次数，次数多者排前）</el-radio>
          </el-radio-group>

          <div v-if="ropeHelper.syncCompleted" style="background:#fff;border:1px solid #e5e5ea;border-radius:8px;padding:10px">
            <div style="font-size:12px;color:#666;margin-bottom:6px">完赛用时（秒）：</div>
            <el-input-number v-model="ropeHelper.syncTime" :precision="2" :step="0.1" :min="1" :max="300" style="width:100%"/>
          </div>
          <div v-else style="background:#fff;border:1px solid #e5e5ea;border-radius:8px;padding:10px">
            <div style="font-size:12px;color:#666;margin-bottom:6px">5分钟内实际完成有效跳动次数（次）：</div>
            <el-input-number v-model="ropeHelper.syncCompletedCount" :min="0" :max="29" style="width:100%"/>
          </div>
        </div>

        <!-- 3. “8”字环绕跳专属 (5分钟全队总次数) -->
        <div v-else-if="ropeHelper.isRopeFig8" style="grid-column:1 / -1;background:rgba(52,199,89,0.06);border:1px solid rgba(52,199,89,0.2);border-radius:12px;padding:12px 14px;margin-bottom:16px">
          <div style="font-size:12px;color:#1b6e2d;margin-bottom:10px"><b>“8”字环绕跳规则：</b>全队22人（2摇绳+20跳绳）5分钟穿梭跳绳，以全队累计完成总次数排定名次（次数多者名次列前）。</div>
          <el-input-number v-model="ropeHelper.fig8Count" :min="0" :max="10000" style="width:100%"/>
        </div>

        <!-- 原始成绩输入项 (常规项目或跳绳同步后的总成绩) -->
        <el-form-item v-if="!ropeHelper.isRopeSingle && !ropeHelper.isRopeSync && !ropeHelper.isRopeFig8" label="原始成绩值 (次 / 秒 / 米)">
          <el-input-number v-model="resultForm.raw_value" :precision="3" :step="0.01" style="width:100%"/>
        </el-form-item>

        <el-form-item label="备注说明 (如跳绳分项明细)">
          <el-input v-model="resultForm.notes" placeholder="可选备注说明"/>
        </el-form-item>

        <el-form-item v-if="resultEditingId && resultForm.published_at" label="修改原因 (已发布成绩修改必填)">
          <el-input v-model="resultForm.modification_reason" placeholder="请填写修改已发布成绩的具体原因"/>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resultDialog = false">取消</el-button>
        <el-button type="primary" @click="saveResult">保存成绩</el-button>
      </template>
    </el-dialog>

    <!-- 🪢 跳绳分项阵容配置 -->
    <el-dialog v-model="ropeLineupDialog" :title="`配置${selectedRopeEvent?.rule?.title || '跳绳项目'}阵容 · ${ropeLineupTeam?.college || ''}`" width="720px">
      <div v-if="ropeLineupTeam" style="margin-bottom:14px;padding:10px 12px;border-radius:10px;background:#f7f8fa;font-size:13px">
        学院总队当前 <b :style="{color: ropeLineupTeam.members.length === 22 ? '#34c759' : '#ff3b30'}">{{ ropeLineupTeam.members.length }}/22</b> 人。
        分项要求：跳绳者 {{ selectedRopeEvent?.rule?.jumper_count }} 人（男{{ selectedRopeEvent?.rule?.male_jumpers }}、女{{ selectedRopeEvent?.rule?.female_jumpers }}），摇绳者 {{ selectedRopeEvent?.rule?.turner_count }} 人。
      </div>
      <el-form label-position="top">
        <el-form-item :label="`跳绳者（已选 ${ropeLineupForm.jumper_ids.length}/${selectedRopeEvent?.rule?.jumper_count || 0}）`">
          <el-select v-model="ropeLineupForm.jumper_ids" multiple filterable collapse-tags :max-collapse-tags="6" style="width:100%" placeholder="请选择跳绳者">
            <el-option v-for="member in ropeLineupMembers" :key="member.student_id" :label="`${member.name}（${member.gender} · ${member.student_no}）`" :value="member.student_id" :disabled="ropeLineupForm.turner_ids.includes(member.student_id)"/>
          </el-select>
        </el-form-item>
        <el-form-item v-if="(selectedRopeEvent?.rule?.turner_count || 0) > 0" :label="`摇绳者（已选 ${ropeLineupForm.turner_ids.length}/${selectedRopeEvent?.rule?.turner_count || 0}，性别不限）`">
          <el-select v-model="ropeLineupForm.turner_ids" multiple filterable style="width:100%" placeholder="请选择摇绳者">
            <el-option v-for="member in ropeLineupMembers" :key="member.student_id" :label="`${member.name}（${member.gender} · ${member.student_no}）`" :value="member.student_id" :disabled="ropeLineupForm.jumper_ids.includes(member.student_id)"/>
          </el-select>
        </el-form-item>
      </el-form>
      <div v-if="ropeLineupTeam?.members.length !== 22" style="color:#d93025;font-size:13px">请先到“名单录入 → 学院代表队”把该学院跳绳总队补齐为22人，未补齐时后端不会允许保存阵容或录入成绩。</div>
      <template #footer>
        <el-button @click="ropeLineupDialog = false">取消</el-button>
        <el-button v-if="ropeLineupTeam?.members.length !== 22" @click="ropeLineupDialog = false; goToRopeRoster()">前往补齐总队</el-button>
        <el-button type="primary" :loading="ropeLineupSaving" @click="saveRopeLineup">保存并校验阵容</el-button>
      </template>
    </el-dialog>

    <!-- 🏀 选择/录入参赛学院代表队弹窗 -->
    <el-dialog v-model="basketballAddTeamsDialog" :title="`👥 选择参赛学院代表队 (${currentMeet?.name || '当前运动会'})`" width="560px">
      <div v-if="basketballTeamsData.all_available_teams?.length">
        <p style="font-size:13px;color:#8e8e93;margin-top:0">请勾选参加本场篮球赛事的学院代表队：</p>
        <el-checkbox-group v-model="selectedBasketballTeamIds" style="display:grid;grid-template-columns:1fr 1fr;gap:10px;max-height:300px;overflow-y:auto;padding:8px">
          <el-checkbox v-for="t in basketballTeamsData.all_available_teams" :key="t.id" :value="t.id" border style="margin:0;width:100%">
            <b>{{ t.college }}</b> ({{ t.team_name }})
          </el-checkbox>
        </el-checkbox-group>
      </div>
      <div v-else style="background:#f5f5f7;border-radius:12px;padding:20px;text-align:center">
        <p style="font-size:14px;color:#8e8e93;margin:0 0 12px">当前运动会届次暂未创建学院代表队</p>
        <el-button type="success" size="default" @click="quickGenerateTeamsForCurrentMeet">⚡ 一键为当前届次生成 6 学院代表队</el-button>
        <el-button plain size="default" @click="active = 'rosters'">👥 前往名单录入中心</el-button>
      </div>
      <template #footer>
        <el-button @click="basketballAddTeamsDialog = false">取消</el-button>
        <el-button type="primary" :disabled="!basketballTeamsData.all_available_teams?.length" @click="submitAddBasketballTeams">保存参赛名单</el-button>
      </template>
    </el-dialog>

    <!-- ➕ 快速创建篮球赛事项目弹窗 -->
    <el-dialog v-model="basketballCreateEventDialog" title="➕ 快速新建篮球赛项目" width="480px">
      <el-form label-position="top">
        <el-form-item label="所属运动会届次">
          <el-select v-model="basketballCreateEventForm.meet_id" placeholder="选择所属运动会" style="width:100%">
            <el-option v-for="m in meets" :key="m.id" :label="`${m.name} (${m.edition}届)`" :value="m.id"/>
          </el-select>
        </el-form-item>
        <el-form-item label="赛事名称">
          <el-input v-model="basketballCreateEventForm.name" placeholder="例如：男子五人制篮球赛 / 女子篮球锦标赛"/>
        </el-form-item>
        <el-form-item label="项目代码">
          <el-input v-model="basketballCreateEventForm.code" placeholder="例如：BB_2026"/>
        </el-form-item>
        <el-form-item label="参赛组别">
          <el-radio-group v-model="basketballCreateEventForm.gender_group">
            <el-radio value="MALE">男子组</el-radio>
            <el-radio value="FEMALE">女子组</el-radio>
            <el-radio value="MIXED">混合组</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="basketballCreateEventDialog = false">取消</el-button>
        <el-button type="primary" @click="submitQuickCreateBasketballEvent">确定创建并自动绑定篮球规程与计分模型</el-button>
      </template>
    </el-dialog>
    <el-dialog v-model="basketballMatchDialog" title="🏀 录入篮球比赛单场比分" width="460px">
      <div style="background:#f5f5f7;border-radius:10px;padding:12px;margin-bottom:16px;text-align:center">
        <b style="font-size:15px;color:var(--apple-blue)">{{ basketballMatchForm.home_team_name }}</b>
        <span style="margin:0 12px;color:#8e8e93;font-weight:700">VS</span>
        <b style="font-size:15px;color:var(--apple-orange)">{{ basketballMatchForm.away_team_name }}</b>
      </div>
      <el-form label-position="top">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
          <el-form-item :label="`${basketballMatchForm.home_team_name} 得分`">
            <el-input-number v-model="basketballMatchForm.home_score" :min="0" :max="250" style="width:100%"/>
          </el-form-item>
          <el-form-item :label="`${basketballMatchForm.away_team_name} 得分`">
            <el-input-number v-model="basketballMatchForm.away_score" :min="0" :max="250" style="width:100%"/>
          </el-form-item>
        </div>
        <el-form-item label="比赛场地">
          <el-input v-model="basketballMatchForm.court_venue" placeholder="例如：篮球馆1号场 / 篮球主馆"/>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="basketballMatchDialog = false">取消</el-button>
        <el-button type="primary" @click="saveBasketballMatch">确定保存比分</el-button>
      </template>
    </el-dialog>

    <!-- 👥 代表队队员阵容与专项规则达标管理弹窗 -->
    <el-dialog v-model="teamMembersDialog" :title="`👥 参赛成员管理 - ${currentManagingTeam.college} (${currentManagingTeam.team_name})`" width="760px">
      <!-- 队伍信息与赛制规则提示卡片 -->
      <div style="background:#f5f5f7;border-radius:12px;padding:14px;margin-bottom:16px;display:flex;justify-content:space-between;align-items:center">
        <div>
          <div style="font-weight:700;font-size:15px;color:var(--apple-label);margin-bottom:4px;display:flex;gap:8px;align-items:center">
            <span>{{ currentManagingTeam.team_name }}</span>
            <el-tag size="small" type="info">{{ currentManagingTeam.event_name || '通用代表队' }}</el-tag>
          </div>
          <div style="font-size:13px;color:#48484a">
            <b>参赛队员总数:</b> {{ currentManagingTeam.total_members }} 人
            （<span style="color:#0071e3;font-weight:600">男 {{ currentManagingTeam.male_count }} 人</span> / <span style="color:#ff2d55;font-weight:600">女 {{ currentManagingTeam.female_count }} 人</span>）
            <span v-if="currentManagingTeam.leader_name" style="margin-left:12px;color:#8e8e93">领队: {{ currentManagingTeam.leader_name }} {{ currentManagingTeam.leader_phone ? '(' + currentManagingTeam.leader_phone + ')' : '' }}</span>
          </div>
        </div>
        <div>
          <el-tag v-if="currentManagingTeam.event_name?.includes('排球')" :type="currentManagingTeam.female_rule_passed ? 'success' : 'danger'" size="large" effect="dark" round>
            {{ currentManagingTeam.female_rule_tip || (currentManagingTeam.female_rule_passed ? '女生达标（≥2人）' : '女生不足2人') }}
          </el-tag>
          <el-tag v-else-if="currentManagingTeam.event_name?.includes('乒乓')" :type="(currentManagingTeam.male_count >= 3 && currentManagingTeam.female_count >= 2) ? 'success' : 'warning'" size="large" effect="dark" round>
            {{ (currentManagingTeam.male_count >= 3 && currentManagingTeam.female_count >= 2) ? '3男2女规程达标' : `当前：男${currentManagingTeam.male_count}/3，女${currentManagingTeam.female_count}/2` }}
          </el-tag>
          <el-tag v-else type="primary" size="large" effect="light" round>
            已录入 {{ currentManagingTeam.total_members }} 名队员
          </el-tag>
        </div>
      </div>

      <!-- 从学院学生中添加新队员 -->
      <div style="background:#fafafa;border:1px solid #ebeef5;border-radius:10px;padding:14px;margin-bottom:18px">
        <h4 style="margin:0 0 10px;font-size:13px;color:var(--apple-label);display:flex;justify-content:space-between">
          <span>➕ 添加本院学生至代表队 (本院可选候选人: {{ availableCandidates.length }} 人)</span>
          <span style="font-size:12px;color:#8e8e93;font-weight:normal">可按姓名/学号多选勾选</span>
        </h4>
        <div style="display:flex;gap:10px;align-items:center">
          <el-select
            v-model="selectedCandidateIds"
            multiple
            filterable
            collapse-tags
            placeholder="请勾选学生（可输入姓名/学号检索，带性别显示）"
            style="flex:1"
          >
            <el-option
              v-for="c in availableCandidates"
              :key="c.id"
              :label="`${c.name} (${c.gender}) - ${c.student_no} - ${c.major || ''}`"
              :value="c.id"
            />
          </el-select>
          <el-select v-model="newMemberRole" allow-create filterable default-first-option placeholder="队内角色" style="width:130px">
            <el-option v-for="r in memberRolePresets" :key="r" :label="r" :value="r"/>
          </el-select>
          <el-button type="primary" :disabled="!selectedCandidateIds.length" @click="addTeamMembersBatch">批量加入</el-button>
        </div>
      </div>

      <!-- 已有队员列表 -->
      <div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <h4 style="margin:0;font-size:14px">📋 当前参赛队员阵容 (共 {{ currentTeamMembers.length }} 人)</h4>
          <span style="font-size:12px;color:#8e8e93">点击角色可直接切换修改，点击首发可切换状态</span>
        </div>
        <el-table :data="currentTeamMembers" size="small" max-height="260" stripe style="width:100%">
          <el-table-column prop="student_no" label="学号" width="115"/>
          <el-table-column prop="name" label="姓名" width="100">
            <template #default="s"><b>{{ s.row.name }}</b></template>
          </el-table-column>
          <el-table-column prop="gender" label="性别" width="65" align="center">
            <template #default="s">
              <el-tag size="small" :type="s.row.gender === '女' ? 'danger' : 'primary'">{{ s.row.gender }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="major" label="专业/班级" min-width="120" show-overflow-tooltip>
            <template #default="s">{{ s.row.major }} {{ s.row.class_name ? `(${s.row.class_name})` : '' }}</template>
          </el-table-column>
          <el-table-column label="队内角色" width="130">
            <template #default="s">
              <el-select
                v-model="s.row.role_title"
                size="small"
                filterable
                allow-create
                default-first-option
                @change="updateTeamMemberRole(s.row, s.row.role_title)"
              >
                <el-option v-for="r in memberRolePresets" :key="r" :label="r" :value="r"/>
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="首发/主力" width="90" align="center">
            <template #default="s">
              <el-tag
                :type="s.row.is_starter ? 'success' : 'info'"
                size="small"
                style="cursor:pointer"
                @click="toggleTeamMemberStarter(s.row)"
              >
                {{ s.row.is_starter ? '⭐ 首发' : '替补' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80" align="center">
            <template #default="s">
              <el-button link type="danger" size="small" @click="deleteTeamMember(s.row)">移除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <template #footer>
        <el-button type="primary" @click="teamMembersDialog = false">完成阵容维护</el-button>
      </template>
    </el-dialog>

    <!-- 🏐 选择/录入排球参赛学院代表队弹窗 -->
    <el-dialog v-model="volleyballAddTeamsDialog" :title="`👥 选择排球参赛学院代表队 (${currentMeet?.name || '当前运动会'})`" width="560px">
      <div v-if="volleyballTeamsData.all_available_teams?.length">
        <p style="font-size:13px;color:#8e8e93;margin-top:0">请勾选参加本次排球比赛的学院代表队（提示：每队需配置至少2名女生队员）：</p>
        <el-checkbox-group v-model="selectedVolleyballTeamIds" style="display:grid;grid-template-columns:1fr 1fr;gap:10px;max-height:300px;overflow-y:auto;padding:8px">
          <el-checkbox v-for="t in volleyballTeamsData.all_available_teams" :key="t.id" :value="t.id" border style="margin:0;width:100%">
            <b>{{ t.college }}</b> ({{ t.team_name }})
          </el-checkbox>
        </el-checkbox-group>
      </div>
      <div v-else style="background:#f5f5f7;border-radius:12px;padding:20px;text-align:center">
        <p style="font-size:14px;color:#8e8e93;margin:0 0 12px">当前运动会届次暂未创建学院代表队</p>
        <el-button type="success" size="default" @click="quickGenerateTeamsForCurrentMeet">⚡ 一键为当前届次生成 6 学院代表队</el-button>
        <el-button plain size="default" @click="active = 'rosters'">👥 前往名单录入中心</el-button>
      </div>
      <template #footer>
        <el-button @click="volleyballAddTeamsDialog = false">取消</el-button>
        <el-button type="primary" :disabled="!volleyballTeamsData.all_available_teams?.length" @click="submitAddVolleyballTeams">保存排球参赛名单</el-button>
      </template>
    </el-dialog>

    <!-- ➕ 快速创建排球赛事项目弹窗 -->
    <el-dialog v-model="volleyballCreateEventDialog" title="➕ 快速新建排球赛项目" width="480px">
      <el-form label-position="top">
        <el-form-item label="所属运动会届次">
          <el-select v-model="volleyballCreateEventForm.meet_id" placeholder="选择所属运动会" style="width:100%">
            <el-option v-for="m in meets" :key="m.id" :label="`${m.name} (${m.edition}届)`" :value="m.id"/>
          </el-select>
        </el-form-item>
        <el-form-item label="赛事名称">
          <el-input v-model="volleyballCreateEventForm.name" placeholder="例如：男女混合排球赛 / 阳光排球联赛"/>
        </el-form-item>
        <el-form-item label="项目代码">
          <el-input v-model="volleyballCreateEventForm.code" placeholder="例如：VB_2026"/>
        </el-form-item>
        <el-form-item label="参赛组别">
          <el-radio-group v-model="volleyballCreateEventForm.gender_group">
            <el-radio value="MIXED">混合组 (女生≥2人)</el-radio>
            <el-radio value="FEMALE">女子组</el-radio>
            <el-radio value="MALE">男子组</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="volleyballCreateEventDialog = false">取消</el-button>
        <el-button type="primary" @click="submitQuickCreateVolleyballEvent">确定创建并自动绑定排球规程与计分模型</el-button>
      </template>
    </el-dialog>

    <!-- 🏐 录入排球单场比分弹窗 (三局两胜 25分制 + 15分钟未到场弃权判2:0) -->
    <el-dialog v-model="volleyballMatchDialog" title="🏐 录入排球单场比分与判决" width="520px">
      <div style="background:#f5f5f7;border-radius:10px;padding:12px;margin-bottom:16px;text-align:center">
        <b style="font-size:15px;color:var(--apple-blue)">{{ volleyballMatchForm.home_team_name }}</b>
        <span style="margin:0 12px;color:#8e8e93;font-weight:700">VS</span>
        <b style="font-size:15px;color:var(--apple-orange)">{{ volleyballMatchForm.away_team_name }}</b>
      </div>

      <el-form label-position="top">
        <!-- 弃权规则开关 -->
        <el-form-item label="15分钟未到场弃权处理">
          <div style="display:flex;align-items:center;gap:12px">
            <el-switch v-model="volleyballMatchForm.is_forfeit" active-text="一方弃权" inactive-text="正常完赛" />
            <span v-if="volleyballMatchForm.is_forfeit" style="font-size:12px;color:#ff3b30">（判对方2:0获胜，胜方积4分，弃权方积0分）</span>
          </div>
        </el-form-item>

        <!-- 弃权方选择 -->
        <div v-if="volleyballMatchForm.is_forfeit" style="background:rgba(255,59,48,0.08);border-radius:8px;padding:12px;margin-bottom:14px">
          <el-form-item label="未到场/弃权队伍" style="margin-bottom:0">
            <el-radio-group v-model="volleyballMatchForm.forfeit_team_id">
              <el-radio :value="volleyballMatchForm.home_team_id">{{ volleyballMatchForm.home_team_name }} (弃权)</el-radio>
              <el-radio :value="volleyballMatchForm.away_team_id">{{ volleyballMatchForm.away_team_name }} (弃权)</el-radio>
            </el-radio-group>
          </el-form-item>
        </div>

        <!-- 正常局分录入（三局两胜，每局25分制） -->
        <div v-else style="display:flex;flex-direction:column;gap:12px;margin-bottom:14px">
          <!-- 第 1 局 -->
          <div style="background:#fff;border:1px solid #ebeef5;border-radius:8px;padding:10px">
            <div style="font-size:12px;font-weight:700;color:var(--apple-label);margin-bottom:6px">第 1 局得分 (25分制)</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
              <el-input-number v-model="volleyballMatchForm.set1_home" :min="0" :max="50" style="width:100%"/>
              <el-input-number v-model="volleyballMatchForm.set1_away" :min="0" :max="50" style="width:100%"/>
            </div>
          </div>

          <!-- 第 2 局 -->
          <div style="background:#fff;border:1px solid #ebeef5;border-radius:8px;padding:10px">
            <div style="font-size:12px;font-weight:700;color:var(--apple-label);margin-bottom:6px">第 2 局得分 (25分制)</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
              <el-input-number v-model="volleyballMatchForm.set2_home" :min="0" :max="50" style="width:100%"/>
              <el-input-number v-model="volleyballMatchForm.set2_away" :min="0" :max="50" style="width:100%"/>
            </div>
          </div>

          <!-- 第 3 局（决胜局开关） -->
          <div style="background:#fff;border:1px solid #ebeef5;border-radius:8px;padding:10px">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
              <span style="font-size:12px;font-weight:700;color:var(--apple-label)">第 3 局 (决胜局，前两局 1:1 战平时打)</span>
              <el-checkbox v-model="volleyballMatchForm.need_third_set">启用第3局</el-checkbox>
            </div>
            <div v-if="volleyballMatchForm.need_third_set" style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
              <el-input-number v-model="volleyballMatchForm.set3_home" :min="0" :max="50" style="width:100%"/>
              <el-input-number v-model="volleyballMatchForm.set3_away" :min="0" :max="50" style="width:100%"/>
            </div>
          </div>
        </div>

        <el-form-item label="比赛场地">
          <el-input v-model="volleyballMatchForm.court_venue" placeholder="例如：排球馆1号场 / 排球主馆"/>
        </el-form-item>
        <el-form-item label="备注说明">
          <el-input v-model="volleyballMatchForm.notes" placeholder="例如：迟到弃权 / 激战三局胜出"/>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="volleyballMatchDialog = false">取消</el-button>
        <el-button type="primary" @click="saveVolleyballMatch">确定保存排球比分</el-button>
      </template>
    </el-dialog>

    <!-- 🏓 录入乒乓球混合团体比分弹窗 (打满五盘：男1/女1/男2/女2/男3，单盘3局2胜 11分制 + 弃权0:5) -->
    <el-dialog v-model="ttTeamMatchDialog" title="🏓 录入乒乓球混合团体比分 (打满五场)" width="680px">
      <div style="background:#f5f5f7;border-radius:10px;padding:12px;margin-bottom:16px;text-align:center">
        <b style="font-size:16px;color:var(--apple-blue)">{{ ttTeamMatchForm.home_team_name }}</b>
        <span style="margin:0 14px;color:#8e8e93;font-weight:700">VS</span>
        <b style="font-size:16px;color:var(--apple-orange)">{{ ttTeamMatchForm.away_team_name }}</b>
      </div>

      <el-form label-position="top">
        <!-- 弃权判决开关 -->
        <el-form-item label="15分钟未到场弃权处理">
          <div style="display:flex;align-items:center;gap:12px">
            <el-switch v-model="ttTeamMatchForm.is_forfeit" active-text="一方弃权" inactive-text="正常完赛" />
            <span v-if="ttTeamMatchForm.is_forfeit" style="font-size:12px;color:#ff3b30">（判对方5:0获胜，胜方积2分，弃权方积0分）</span>
          </div>
        </el-form-item>

        <!-- 弃权方选择 -->
        <div v-if="ttTeamMatchForm.is_forfeit" style="background:rgba(255,59,48,0.08);border-radius:8px;padding:12px;margin-bottom:14px">
          <el-form-item label="未到场/弃权队伍" style="margin-bottom:0">
            <el-radio-group v-model="ttTeamMatchForm.forfeit_team_id">
              <el-radio :value="ttTeamMatchForm.home_team_id">{{ ttTeamMatchForm.home_team_name }} (弃权)</el-radio>
              <el-radio :value="ttTeamMatchForm.away_team_id">{{ ttTeamMatchForm.away_team_name }} (弃权)</el-radio>
            </el-radio-group>
          </el-form-item>
        </div>

        <!-- 正常打满五盘录入 -->
        <div v-else style="display:flex;flex-direction:column;gap:12px;margin-bottom:14px">
          <div style="font-size:13px;font-weight:700;color:#1c1c1e">
            必须打满五场（出场顺序：男单1 ➔ 女单1 ➔ 男单2 ➔ 女单2 ➔ 男单3，每场三局两胜 11分制）
          </div>

          <div
            v-for="(r, idx) in ttTeamMatchForm.rubbers"
            :key="idx"
            style="background:#fff;border:1px solid #e5e5ea;border-radius:10px;padding:12px"
          >
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
              <div style="display:flex;align-items:center;gap:6px">
                <el-tag size="small" :type="r.type.startsWith('MALE') ? 'primary' : 'danger'">
                  {{ r.name }} ({{ r.type.startsWith('MALE') ? '男单' : '女单' }})
                </el-tag>
                <span style="font-size:12px;font-weight:600">{{ ttTeamMatchForm.home_team_name }} vs {{ ttTeamMatchForm.away_team_name }}</span>
              </div>
              <el-checkbox v-model="r.need_third_set" size="small">打满第3局 (决胜局)</el-checkbox>
            </div>

            <!-- 出场队员姓名 (可选) -->
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:8px">
              <el-input v-model="r.home_player_name" :placeholder="`主队${r.name}选手姓名`" size="small"/>
              <el-input v-model="r.away_player_name" :placeholder="`客队${r.name}选手姓名`" size="small"/>
            </div>

            <!-- 局分录入（11分制） -->
            <div style="display:flex;flex-direction:column;gap:6px">
              <div style="display:grid;grid-template-columns:80px 1fr 1fr;gap:8px;align-items:center">
                <span style="font-size:11px;color:#8e8e93">第 1 局(11分)</span>
                <el-input-number v-model="r.set1_home" :min="0" :max="50" size="small" style="width:100%"/>
                <el-input-number v-model="r.set1_away" :min="0" :max="50" size="small" style="width:100%"/>
              </div>
              <div style="display:grid;grid-template-columns:80px 1fr 1fr;gap:8px;align-items:center">
                <span style="font-size:11px;color:#8e8e93">第 2 局(11分)</span>
                <el-input-number v-model="r.set2_home" :min="0" :max="50" size="small" style="width:100%"/>
                <el-input-number v-model="r.set2_away" :min="0" :max="50" size="small" style="width:100%"/>
              </div>
              <div v-if="r.need_third_set" style="display:grid;grid-template-columns:80px 1fr 1fr;gap:8px;align-items:center">
                <span style="font-size:11px;color:#8e8e93">第 3 局(决胜)</span>
                <el-input-number v-model="r.set3_home" :min="0" :max="50" size="small" style="width:100%"/>
                <el-input-number v-model="r.set3_away" :min="0" :max="50" size="small" style="width:100%"/>
              </div>
            </div>
          </div>
        </div>

        <el-form-item label="比赛台次与场地">
          <el-input v-model="ttTeamMatchForm.court_venue" placeholder="例如：乒乓球馆1号台"/>
        </el-form-item>
        <el-form-item label="备注说明">
          <el-input v-model="ttTeamMatchForm.notes" placeholder="例如：打满五盘激战胜出 / 迟到弃权"/>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="ttTeamMatchDialog = false">取消</el-button>
        <el-button type="primary" @click="saveTtTeamMatch">确定保存混合团体比分</el-button>
      </template>
    </el-dialog>

    <!-- 🏓 录入乒乓球单打比分弹窗 (前期3局2胜 / 八强5局3胜 11分制) -->
    <el-dialog v-model="ttSinglesMatchDialog" title="🏓 录入乒乓球单打比赛比分" width="520px">
      <div style="background:#f5f5f7;border-radius:10px;padding:12px;margin-bottom:16px;text-align:center">
        <div style="display:flex;justify-content:center;align-items:center;gap:12px">
          <div>
            <b style="font-size:15px;color:var(--apple-blue)">{{ ttSinglesMatchForm.home_student_name }}</b>
            <small style="color:#8e8e93;display:block">({{ ttSinglesMatchForm.home_college }})</small>
          </div>
          <span style="color:#8e8e93;font-weight:700">VS</span>
          <div>
            <b style="font-size:15px;color:var(--apple-orange)">{{ ttSinglesMatchForm.away_student_name }}</b>
            <small style="color:#8e8e93;display:block">({{ ttSinglesMatchForm.away_college }})</small>
          </div>
        </div>
        <div style="margin-top:8px">
          <el-tag size="small" :type="ttSinglesMatchForm.best_of===5?'danger':'primary'">
            {{ ttSinglesMatchForm.best_of===5 ? '八强战 · 五局三胜制 (每局11分)' : '前期战 · 三局两胜制 (每局11分)' }}
          </el-tag>
        </div>
      </div>

      <el-form label-position="top">
        <div style="display:flex;flex-direction:column;gap:10px;margin-bottom:14px">
          <div
            v-for="(st, idx) in ttSinglesMatchForm.sets"
            :key="idx"
            style="background:#fff;border:1px solid #ebeef5;border-radius:8px;padding:10px"
          >
            <div style="font-size:12px;font-weight:700;color:var(--apple-label);margin-bottom:6px">
              第 {{ st.set }} 局得分 (11分制)
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
              <el-input-number v-model="st.home" :min="0" :max="50" style="width:100%"/>
              <el-input-number v-model="st.away" :min="0" :max="50" style="width:100%"/>
            </div>
          </div>
        </div>

        <el-form-item label="比赛球台场地">
          <el-input v-model="ttSinglesMatchForm.court_venue" placeholder="例如：乒乓球馆2号台"/>
        </el-form-item>
        <el-form-item label="备注说明">
          <el-input v-model="ttSinglesMatchForm.notes" placeholder="例如：打满决胜局 / 精彩逆转"/>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="ttSinglesMatchDialog = false">取消</el-button>
        <el-button type="primary" @click="saveTtSinglesMatch">确定保存单打比分</el-button>
      </template>
    </el-dialog>

    <!-- 🏓 录入混合团体参赛队伍弹窗 -->
    <el-dialog v-model="ttTeamAddTeamsDialog" :title="`👥 录入混合团体赛参赛队伍 (${currentMeet?.name || '当前运动会'})`" width="560px">
      <div v-if="ttTeamTeamsData.all_available_teams?.length">
        <div style="margin-bottom:12px;font-size:13px;color:#8e8e93">
          请勾选参加本次乒乓球混合团体赛的学院代表队（各代表队需包含3男2女队员）：
        </div>
        <el-checkbox-group v-model="selectedTtTeamIds" style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
          <el-checkbox v-for="t in ttTeamTeamsData.all_available_teams" :key="t.id" :value="t.id" border style="margin:0;width:100%">
            <b>{{ t.college }}</b> ({{ t.team_name }})
          </el-checkbox>
        </el-checkbox-group>
      </div>
      <div v-else style="background:#f5f5f7;border-radius:12px;padding:20px;text-align:center">
        <p style="font-size:14px;color:#8e8e93;margin:0 0 12px">当前运动会届次暂未创建学院代表队</p>
        <el-button type="success" size="default" @click="quickGenerateTeamsForCurrentMeet">⚡ 一键为当前届次生成 6 学院代表队</el-button>
        <el-button plain size="default" @click="active = 'rosters'">👥 前往名单录入中心</el-button>
      </div>
      <template #footer>
        <el-button @click="ttTeamAddTeamsDialog = false">取消</el-button>
        <el-button type="primary" :disabled="!ttTeamTeamsData.all_available_teams?.length" @click="submitAddTtTeams">保存参赛代表队名单</el-button>
      </template>
    </el-dialog>

    <!-- 🏓 申报单打参赛选手名单弹窗 -->
    <el-dialog v-model="ttSinglesAddAthletesDialog" :title="`👥 申报${ttTab==='ms'?'男子':'女子'}单打运动员名单`" width="600px">
      <div style="margin-bottom:12px;font-size:13px;color:#8e8e93">
        请勾选参赛运动员（每学院限上报3名运动员，报名顺序前置自动标记为种子选手）：
      </div>
      <el-checkbox-group v-model="selectedTtAthleteIds" style="display:grid;grid-template-columns:1fr 1fr;gap:10px;max-height:360px;overflow-y:auto">
        <el-checkbox
          v-for="s in students.filter((i:any)=>i.gender===(ttTab==='ms'?'男':'女'))"
          :key="s.id"
          :value="s.id"
        >
          {{ s.name }} ({{ s.college }} · {{ s.student_no }})
        </el-checkbox>
      </el-checkbox-group>
      <template #footer>
        <el-button @click="ttSinglesAddAthletesDialog = false">取消</el-button>
        <el-button type="primary" @click="submitAddTtSinglesAthletes">保存单打运动员名单</el-button>
      </template>
    </el-dialog>

    <!-- 🏓 快捷创建乒乓球比赛项目弹窗 (支持混合团体 / 男单 / 女单) -->
    <el-dialog v-model="ttCreateEventDialog" title="🏓 一键创建乒乓球比赛项目" width="520px">
      <el-form label-position="top">
        <el-form-item label="比赛项目类型">
          <el-radio-group v-model="ttCreateEventForm.category" @change="onTtCategoryChange" style="display:flex;flex-direction:column;gap:8px">
            <el-radio value="TEAM">🏓 乒乓球混合团体赛 (各学院3男2女 · 打满5盘 · 胜2分负1分)</el-radio>
            <el-radio value="MS">🏓 男子乒乓球单打 (各学院3名男选手 · 种子排位回避 · 前3局后5局)</el-radio>
            <el-radio value="WS">🏓 女子乒乓球单打 (各学院3名女选手 · 种子排位回避 · 前3局后5局)</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="关联运动会">
          <el-select v-model="ttCreateEventForm.meet_id" placeholder="选择所属运动会" style="width:100%">
            <el-option v-for="m in meets" :key="m.id" :label="`${m.name} (${m.edition}届)`" :value="m.id"/>
          </el-select>
        </el-form-item>
        <el-form-item label="项目名称">
          <el-input v-model="ttCreateEventForm.name" placeholder="例如：乒乓球混合团体赛"/>
        </el-form-item>
        <el-form-item label="项目代码">
          <el-input v-model="ttCreateEventForm.code" placeholder="例如：TT_TEAM"/>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ttCreateEventDialog = false">取消</el-button>
        <el-button type="primary" @click="submitQuickCreateTtEvent">确定创建并自动配置国标乒乓球规程</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="changePasswordDialog" title="首次登录修改密码" width="400px" :close-on-click-modal="false" :show-close="false">
      <el-form label-position="top">
        <el-form-item label="当前密码"><el-input v-model="passwordForm.current_password" type="password" show-password/></el-form-item>
        <el-form-item label="新密码"><el-input v-model="passwordForm.new_password" type="password" show-password/></el-form-item>
      </el-form>
      <template #footer><el-button type="primary" @click="changePassword">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
/* 工作台布局 */
.apple-workspace {
  display: flex;
  min-height: 100vh;
  background-color: #f5f5f7;
  color: #1c1c1e;
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", sans-serif;
}

/* 高透毛玻璃侧边栏 */
.mac-sidebar {
  width: 240px;
  background: rgba(246, 246, 248, 0.82);
  backdrop-filter: blur(25px) saturate(190%);
  -webkit-backdrop-filter: blur(25px) saturate(190%);
  border-right: 1px solid rgba(0, 0, 0, 0.08);
  display: flex;
  flex-direction: column;
  position: fixed;
  inset: 0 auto 0 0;
  z-index: 20;
  transition: width 0.22s cubic-bezier(0.16, 1, 0.3, 1);
  padding: 16px 12px;
}

.mac-sidebar.collapsed {
  width: 72px;
}

/* 窗口红黄绿三色指示灯 */
.mac-window-controls {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 4px 8px 16px;
}

.mac-dot {
  width: 11px;
  height: 11px;
  border-radius: 50%;
}

.mac-dot.red { background-color: #ff5f57; border: 0.5px solid #e0443e; }
.mac-dot.yellow { background-color: #febc2e; border: 0.5px solid #dea123; }
.mac-dot.green { background-color: #28c840; border: 0.5px solid #1aab29; }

/* 顶部图标 */
.mac-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 6px 14px;
  margin-bottom: 10px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
}

.mac-app-icon {
  width: 38px;
  height: 38px;
  flex-basis: 38px;
  background: linear-gradient(135deg, #007aff, #0051a8);
  border-radius: 10px;
  display: grid;
  place-items: center;
  font-weight: 700;
  font-size: 17px;
  color: #ffffff;
  box-shadow: 0 4px 10px rgba(0, 122, 255, 0.3);
}

.mac-app-icon.lg {
  width: 60px;
  height: 60px;
  font-size: 26px;
  border-radius: 16px;
}

.mac-app-info b {
  font-size: 14px;
  font-weight: 700;
  line-height: 1.2;
}

.mac-app-info span {
  font-size: 11px;
  color: #8e8e93;
}

.mac-section-title {
  font-size: 10px;
  font-weight: 700;
  color: #8e8e93;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 0 10px;
  margin-bottom: 6px;
}

/* 导航列表 */
.mac-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  overflow-y: auto;
}

.mac-nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  height: 38px;
  padding: 0 10px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 500;
  color: #3a3a3c;
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all 0.15s ease;
  text-align: left;
}

.mac-nav-item:hover {
  background: rgba(0, 0, 0, 0.04);
}

.mac-nav-item.active {
  background: #007aff;
  color: #ffffff;
  font-weight: 600;
  box-shadow: 0 4px 12px rgba(0, 122, 255, 0.25);
}

.mac-nav-item.active .sf-icon-box {
  background: rgba(255, 255, 255, 0.2) !important;
  color: #ffffff !important;
}

/* 彩色图标块 */
.sf-icon-box {
  width: 26px;
  height: 26px;
  flex-basis: 26px;
  border-radius: 7px;
  display: grid;
  place-items: center;
  font-size: 14px;
  transition: all 0.15s ease;
}

.sf-icon-box.blue { background: rgba(0, 122, 255, 0.12); color: #007aff; }
.sf-icon-box.orange { background: rgba(255, 149, 0, 0.12); color: #ff9500; }
.sf-icon-box.purple { background: rgba(175, 82, 222, 0.12); color: #af52de; }
.sf-icon-box.green { background: rgba(52, 199, 89, 0.12); color: #34c759; }
.sf-icon-box.red { background: rgba(255, 59, 48, 0.12); color: #ff3b30; }
.sf-icon-box.teal { background: rgba(48, 176, 199, 0.12); color: #30b0c7; }
.sf-icon-box.gray { background: rgba(142, 142, 147, 0.12); color: #8e8e93; }

.mac-nav-label {
  white-space: nowrap;
}

/* 用户卡片底部 */
.mac-user-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.7);
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.04);
}

.mac-user-avatar {
  width: 30px;
  height: 30px;
  flex-basis: 30px;
  border-radius: 50%;
  background: #007aff;
  color: #ffffff;
  display: grid;
  place-items: center;
  font-weight: 700;
  font-size: 13px;
}

.mac-user-meta {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
}

.mac-user-meta b {
  font-size: 12px;
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
}

.mac-user-meta span {
  font-size: 10px;
  color: #8e8e93;
}

.mac-icon-btn {
  background: transparent;
  border: none;
  color: #8e8e93;
  cursor: pointer;
  font-size: 15px;
  padding: 4px;
}

.mac-icon-btn:hover {
  color: #ff3b30;
}

/* 主页面 */
.mac-main-area {
  margin-left: 240px;
  width: calc(100% - 240px);
  flex: 1;
  transition: margin-left 0.22s cubic-bezier(0.16, 1, 0.3, 1);
  display: flex;
  flex-direction: column;
}

.mac-sidebar.collapsed + .mac-main-area {
  margin-left: 72px;
  width: calc(100% - 72px);
}

/* 页面顶栏 */
.mac-top-bar {
  height: 60px;
  padding: 0 28px;
  background: rgba(245, 245, 247, 0.85);
  backdrop-filter: blur(20px) saturate(180%);
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 10;
}

.mac-bar-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.mac-toggle-btn {
  width: 32px;
  height: 32px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 8px;
  background: #ffffff;
  color: #3a3a3c;
  cursor: pointer;
  display: grid;
  place-items: center;
  font-size: 15px;
}

.mac-top-bar h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.01em;
}

.mac-top-bar p {
  margin: 1px 0 0;
  font-size: 11px;
  color: #8e8e93;
}

.mac-bar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.mac-pill-btn {
  height: 32px;
  padding: 0 14px;
  border-radius: 9999px;
  border: 1px solid rgba(0, 122, 255, 0.3);
  background: rgba(0, 122, 255, 0.08);
  color: #007aff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
}

.mac-pill-btn:hover {
  background: rgba(0, 122, 255, 0.15);
}

.mac-date-badge {
  font-size: 12px;
  color: #8e8e93;
}

/* 主内容正文 */
.mac-body {
  padding: 24px 28px 40px;
  max-width: 1400px;
  width: 100%;
}

/* 欢迎横幅 */
.apple-hello-banner {
  margin-bottom: 20px;
}

.apple-hello-banner h1 {
  margin: 0;
  font-size: 26px;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: #1c1c1e;
}

.apple-hello-banner p {
  margin: 4px 0 0;
  font-size: 13px;
  color: #8e8e93;
}

/* 四列统计卡片 */
.apple-bento-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.apple-bento-card {
  padding: 20px;
  background: #ffffff;
  border-radius: 18px;
  border: 1px solid rgba(0, 0, 0, 0.05);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.03);
  display: flex;
  flex-direction: column;
  transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.apple-bento-card:hover {
  transform: translateY(-2px);
}

.bento-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.sf-badge {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  font-size: 18px;
}

.sf-badge.blue { background: rgba(0, 122, 255, 0.12); color: #007aff; }
.sf-badge.orange { background: rgba(255, 149, 0, 0.12); color: #ff9500; }
.sf-badge.green { background: rgba(52, 199, 89, 0.12); color: #34c759; }
.sf-badge.red { background: rgba(255, 59, 48, 0.12); color: #ff3b30; }
.sf-badge.purple { background: rgba(175, 82, 222, 0.12); color: #af52de; }

.apple-chip {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  padding: 2px 8px;
  border-radius: 9999px;
  background: rgba(0, 122, 255, 0.1);
  color: #007aff;
}

.apple-chip.orange { background: rgba(255, 149, 0, 0.1); color: #ff9500; }
.apple-chip.green { background: rgba(52, 199, 89, 0.1); color: #34c759; }
.apple-chip.red { background: rgba(255, 59, 48, 0.1); color: #ff3b30; }
.apple-chip.purple { background: rgba(175, 82, 222, 0.1); color: #af52de; }

.bento-number {
  font-size: 32px;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: #1c1c1e;
}

.bento-title {
  font-size: 14px;
  font-weight: 600;
  color: #1c1c1e;
  margin-top: 2px;
}

.apple-bento-card small {
  font-size: 12px;
  color: #8e8e93;
  margin-top: 2px;
}

/* 4 列 SF Icon Quick Actions 入口网格 */
.apple-quick-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.apple-quick-card {
  padding: 16px 18px;
  background: #ffffff;
  border-radius: 16px;
  border: 1px solid rgba(0, 0, 0, 0.05);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.03);
  display: flex;
  align-items: center;
  gap: 14px;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  text-align: left;
}

.apple-quick-card:hover {
  transform: scale(1.02);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
}

.sf-quick-badge {
  width: 42px;
  height: 42px;
  flex-basis: 42px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  font-size: 20px;
}

.sf-quick-badge.blue { background: rgba(0, 122, 255, 0.1); color: #007aff; }
.sf-quick-badge.orange { background: rgba(255, 149, 0, 0.1); color: #ff9500; }
.sf-quick-badge.purple { background: rgba(175, 82, 222, 0.1); color: #af52de; }
.sf-quick-badge.teal { background: rgba(48, 176, 199, 0.1); color: #30b0c7; }
.sf-quick-badge.green { background: rgba(52, 199, 89, 0.1); color: #34c759; }

.quick-info h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: #1c1c1e;
}

.quick-info p {
  margin: 2px 0 0;
  font-size: 11px;
  color: #8e8e93;
}

.quick-chevron {
  margin-left: auto;
  color: #aeaeb2;
  font-size: 15px;
}

/* 极简卡片面板 */
.mac-card {
  padding: 24px;
  background: #ffffff;
  border-radius: 18px;
  border: 1px solid rgba(0, 0, 0, 0.05);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.03);
}

.mac-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
}

.mac-card-head h3 {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
}

.mac-card-head p {
  margin: 2px 0 0;
  font-size: 12px;
  color: #8e8e93;
}

.apple-stat-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.apple-stat-row > div {
  padding: 16px;
  background: #ffffff;
  border-radius: 14px;
  border: 1px solid rgba(0, 0, 0, 0.04);
  display: flex;
  flex-direction: column;
}

.apple-stat-row span {
  font-size: 12px;
  color: #8e8e93;
}

.apple-stat-row b {
  font-size: 20px;
  font-weight: 700;
  margin-top: 4px;
}

.apple-settings-grid {
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: 20px;
}

.apple-form-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px 18px;
}

.mac-preview-card {
  padding: 30px;
  border-radius: 18px;
  color: #ffffff;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  justify-content: center;
}

.apple-model-grid, .apple-grid-three {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-top: 14px;
}

.apple-model-card, .apple-assign-card {
  padding: 18px;
  background: #ffffff;
  border-radius: 14px;
  border: 1px solid rgba(0, 0, 0, 0.04);
  display: flex;
  flex-direction: column;
}

.model-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.points-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 10px 0;
}

.points-pills span {
  background: #f5f5f7;
  padding: 3px 8px;
  border-radius: 6px;
  font-size: 11px;
}

.model-btns {
  display: flex;
  gap: 8px;
  margin-top: auto;
  padding-top: 10px;
  border-top: 1px solid #f5f5f7;
}

.apple-filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.apple-dialog-form {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px 16px;
}

/* 响应式断点 */
@media (max-width: 1024px) {
  .apple-bento-grid, .apple-quick-grid, .apple-stat-row, .apple-model-grid, .apple-grid-three {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 640px) {
  .apple-bento-grid, .apple-quick-grid, .apple-stat-row, .apple-model-grid, .apple-grid-three, .apple-dialog-form {
    grid-template-columns: 1fr;
  }
  .mac-sidebar {
    width: 72px;
  }
  .mac-main-area {
    margin-left: 72px;
    width: calc(100% - 72px);
  }
  .mac-app-info, .mac-section-title, .mac-nav-label, .mac-user-meta {
    display: none;
  }
}

/* AI 赛事协同顶栏按钮与悬浮球 */
.mac-pill-btn.ai-copilot-pill {
  background: linear-gradient(135deg, rgba(0, 122, 255, 0.12) 0%, rgba(88, 86, 214, 0.15) 100%);
  border-color: rgba(88, 86, 214, 0.3);
  color: #5856d6;
  font-weight: 700;
}

.mac-pill-btn.ai-copilot-pill:hover {
  background: linear-gradient(135deg, rgba(0, 122, 255, 0.2) 0%, rgba(88, 86, 214, 0.25) 100%);
}

.apple-ai-floating-fab {
  position: fixed;
  bottom: 28px;
  right: 32px;
  height: 48px;
  padding: 0 18px;
  border-radius: 9999px;
  background: linear-gradient(135deg, #007aff 0%, #5856d6 100%);
  color: #ffffff;
  border: none;
  box-shadow: 0 8px 24px rgba(88, 86, 214, 0.35);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  z-index: 1000;
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.apple-ai-floating-fab:hover {
  transform: translateY(-3px) scale(1.03);
  box-shadow: 0 12px 30px rgba(88, 86, 214, 0.45);
}

.fab-label {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: -0.01em;
}

.fab-pulse {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  border-radius: 9999px;
  box-shadow: 0 0 0 0 rgba(88, 86, 214, 0.6);
  animation: fab-ripple 2.5s infinite;
}

@keyframes fab-ripple {
  0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(88, 86, 214, 0.5); }
  70% { transform: scale(1.1); box-shadow: 0 0 0 14px rgba(88, 86, 214, 0); }
  100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(88, 86, 214, 0); }
}
</style>
