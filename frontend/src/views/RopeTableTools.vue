<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api, { errorMessage } from '../api'
import registrationTemplateUrl from '../assets/rope-registration-template.xlsx?url'

const props = defineProps<{ meetId: number | null; eventId: number | null; events: any[]; canManage: boolean }>()
const emit = defineEmits<{ changed: [] }>()
const busy = ref(false)
const importDialog = ref(false)
const drawDialog = ref(false)
const file = ref<File | null>(null)
const preview = ref<any>(null)
const importWarnings = ref<string[]>([])
const importForm = reactive({ college: '', default_event: '', last_two_turners: false })
const exportTeamId = ref<number | null>(null)
const exportEventId = ref<number | null>(null)
const drawForm = reactive({ event_id: null as number | null, competition_at: '', venue: '', slot_minutes: 15, check_in_minutes: 15 })
const teams = computed(() => {
  const unique = new Map<number, any>()
  for (const event of props.events) for (const team of event.teams || []) unique.set(team.team_id, team)
  return [...unique.values()]
})
const collegeCount = computed(() => new Set(teams.value.map(team => team.college)).size)

function openImport() {
  if (!props.meetId) return ElMessage.warning('请先选择运动会')
  if (props.events.length !== 3) return ElMessage.warning('请先初始化跳绳赛制')
  preview.value = null
  file.value = null
  importWarnings.value = []
  importDialog.value = true
}

function downloadTemplate() {
  const link = document.createElement('a')
  link.href = registrationTemplateUrl
  link.download = '跳绳比赛报名表模板.xlsx'
  link.click()
}

function selectFile(event: Event) {
  file.value = (event.target as HTMLInputElement).files?.[0] || null
  preview.value = null
}

function importBody() {
  const body = new FormData()
  body.append('meet_id', String(props.meetId))
  body.append('college', importForm.college.trim())
  body.append('default_event', importForm.default_event)
  body.append('last_two_turners', String(importForm.last_two_turners))
  body.append('file', file.value!)
  return body
}

async function recognize() {
  if (!file.value) return ElMessage.warning('请选择报名表')
  busy.value = true
  try {
    preview.value = (await api.post('/sports-teacher/rope/import/preview', importBody(), { timeout: 60000 })).data
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    busy.value = false
  }
}

async function importRoster() {
  if (!preview.value || preview.value.errors.length || !file.value) return
  busy.value = true
  try {
    const { data } = await api.post('/sports-teacher/rope/import', importBody(), { timeout: 60000 })
    importWarnings.value = data.warnings || []
    ElMessage.success(data.message)
    importDialog.value = false
    emit('changed')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    busy.value = false
  }
}

async function download(kind: 'record-sheets' | 'summary' | 'schedules') {
  if (!props.meetId) return ElMessage.warning('请先选择运动会')
  busy.value = true
  try {
    const params: Record<string, number> = { meet_id: props.meetId }
    if (kind !== 'summary' && exportEventId.value) params.event_id = exportEventId.value
    if (kind === 'record-sheets' && exportTeamId.value) params.team_id = exportTeamId.value
    const response = await api.get(`/admin/rope/${kind}/export`, { params, responseType: 'blob', timeout: 60000 })
    const url = URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = url
    const filename = /filename\*=UTF-8''([^;]+)/i.exec(response.headers['content-disposition'] || '')?.[1]
    const fallback = { 'record-sheets': '成绩登记表', summary: '最终成绩排名汇总', schedules: '抽签赛程表' }
    link.download = filename ? decodeURIComponent(filename) : `跳绳_${fallback[kind]}.xlsx`
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (error: any) {
    // Blob下载失败时也显示服务端的阵容/权限提示。
    if (error.response?.data instanceof Blob) {
      try { error.response.data = JSON.parse(await error.response.data.text()) } catch { /* 使用原错误 */ }
    }
    ElMessage.error(errorMessage(error))
  } finally {
    busy.value = false
  }
}

async function generateSchedule() {
  if (!drawForm.competition_at || !drawForm.venue.trim()) return ElMessage.warning('请填写比赛开始时间和场地')
  busy.value = true
  try {
    const { data } = await api.post('/sports-teacher/rope/draw', { ...drawForm, meet_id: props.meetId })
    ElMessage.success(data.message)
    drawDialog.value = false
    emit('changed')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    busy.value = false
  }
}

const projectLabel: Record<string, string> = { ROPE_SINGLE: '计时计数项目', ROPE_SYNC: '集体单摇跳', ROPE_FIG8: '8字绕绳跳' }
</script>

<template>
  <section class="mac-card panel" style="margin-bottom:14px">
    <h3 style="margin:0 0 10px;font-size:16px">报名表与比赛用表</h3>
    <p style="margin:0 0 14px;color:#666;font-size:13px">先下载模板填写各学院报名名单，导入并配置三个项目阵容后导出手写登记表。成绩和备注两列留空，比赛后由裁判在成绩工作台录入。</p>
    <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
      <el-button v-if="canManage" :disabled="busy" @click="downloadTemplate">下载模板</el-button>
      <el-button v-if="canManage" type="primary" :disabled="busy" @click="openImport">导入报名表</el-button>
      <el-button v-if="canManage" :disabled="busy || !events.length" @click="drawDialog = true">随机抽签 / 生成赛程</el-button>
      <el-select v-model="exportTeamId" clearable placeholder="全部学院" style="width:200px">
        <el-option v-for="team in teams" :key="team.team_id" :label="`${team.college} · ${team.team_name}`" :value="team.team_id"/>
      </el-select>
      <span v-if="events.length" style="font-size:12px;color:#666">已关联 {{ collegeCount }} 个学院</span>
      <el-select v-model="exportEventId" clearable placeholder="三个小项目" style="width:180px">
        <el-option v-for="event in events" :key="event.id" :label="event.rule.title" :value="event.id"/>
      </el-select>
      <el-button :disabled="busy || !events.length" @click="download('record-sheets')">导出手写登记表</el-button>
      <el-button :disabled="busy || !events.length" @click="download('schedules')">导出赛程表</el-button>
      <el-button type="success" :disabled="busy || !events.length" @click="download('summary')">导出最终排名汇总</el-button>
    </div>
    <el-alert v-if="importWarnings.length" type="warning" :closable="true" style="margin-top:12px" @close="importWarnings = []">
      <template #title>报名已导入，以下阵容需要补充</template>
      <div v-for="warning in importWarnings" :key="warning">{{ warning }}</div>
    </el-alert>
    <p style="margin:12px 0 0;font-size:12px;color:#888">登记表按所选学院、项目导出，每个学院每项一张打印页。最终汇总包含全部学院，按已发布积分排名；未全部发布的学院不列总名次。</p>
  </section>

  <el-dialog v-model="importDialog" title="识别学院跳绳报名表" width="min(1000px, 94vw)" :close-on-click-modal="false">
    <el-alert type="info" :closable="false" title="支持.xlsx、.csv；自动识别表头别名、工作表项目名称、代表队信息和合并的学院列。导入只处理报名信息，成绩仍由裁判手动登记。"/>
    <p style="margin:12px 0 0;font-size:13px;color:#666">模板含22人总名单及三个项目报名页。学号须为8位数字，前两位表示年级（如24表示24级），请按文本填写以保留前导零，同一队员在各页的信息保持一致；跳绳者、摇绳者填写在对应区域。</p>
    <el-form label-width="110px" style="margin-top:16px" :disabled="busy" @change="preview = null">
      <el-form-item label="报名文件"><input type="file" accept=".xlsx,.csv" @change="selectFile"/></el-form-item>
      <el-form-item label="默认学院"><el-input v-model="importForm.college" placeholder="表格没有学院列时填写；多学院总表请填写学院列" @input="preview = null"/></el-form-item>
      <el-form-item label="默认项目">
        <el-select v-model="importForm.default_event" placeholder="自动识别；无项目时仅导入22人总队" @change="preview = null">
          <el-option label="自动识别；无项目时仅导入22人总队" value=""/>
          <el-option v-for="(label, code) in projectLabel" :key="code" :label="label" :value="code"/>
        </el-select>
      </el-form-item>
      <el-form-item label="摇绳者识别">
        <div>
          <el-checkbox v-model="importForm.last_two_turners" @change="preview = null">确认无角色列的12人/22人项目名单，末两人为摇绳者</el-checkbox>
          <div style="color:#888;font-size:12px">若表内有角色列，将按表格角色识别。未确认时，请导入后在“配置阵容”选择摇绳者。</div>
        </div>
      </el-form-item>
    </el-form>
    <template v-if="preview">
      <el-alert :type="preview.errors.length ? 'error' : 'success'" :closable="false" :title="`识别到 ${preview.participants} 人、${preview.entries} 条报名，去重 ${preview.duplicates} 条`"/>
      <div style="max-height:150px;overflow:auto;margin:10px 0">
        <div v-for="error in preview.errors" :key="error" style="color:#c33">{{ error }}</div>
        <div v-for="warning in preview.warnings" :key="warning" style="color:#986800">{{ warning }}</div>
        <div v-for="sheet in preview.sheets" :key="sheet.sheet" style="color:#666">{{ sheet.sheet }}：{{ sheet.count }}条</div>
      </div>
      <el-table :data="preview.records.slice(0, 100)" height="300" border>
        <el-table-column prop="college" label="学院" min-width="130"/>
        <el-table-column prop="student_no" label="学号" min-width="150"/>
        <el-table-column prop="name" label="姓名" width="100"/>
        <el-table-column prop="gender" label="性别" width="70"/>
        <el-table-column label="项目" min-width="140"><template #default="s">{{ projectLabel[s.row.event_code] || '22人总队' }}</template></el-table-column>
        <el-table-column label="角色" width="100"><template #default="s">{{ s.row.role === 'TURNER' ? '摇绳者' : s.row.event_code ? '跳绳者' : '队员' }}</template></el-table-column>
      </el-table>
      <p v-if="preview.entries > 100" style="font-size:12px">预览显示前100条，确认后导入全部 {{ preview.entries }} 条。</p>
    </template>
    <template #footer>
      <el-button :disabled="busy" @click="importDialog = false">取消</el-button>
      <el-button :loading="busy" @click="recognize">识别 / 重新预览</el-button>
      <el-button type="primary" :loading="busy" :disabled="!preview || !!preview.errors.length" @click="importRoster">确认导入</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="drawDialog" title="随机抽签并生成赛程" width="560px" :close-on-click-modal="false">
    <el-alert type="info" :closable="false" title="每个项目独立随机抽签，三个项目依次排在同一场地。仅正式报名且阵容校验通过的队伍参加。生成后在赛程管理核对并发布。"/>
    <el-form label-width="120px" style="margin-top:16px" :disabled="busy">
      <el-form-item label="抽签项目">
        <el-select v-model="drawForm.event_id" clearable placeholder="全部三个项目">
          <el-option v-for="event in events" :key="event.id" :label="event.rule.title" :value="event.id"/>
        </el-select>
      </el-form-item>
      <el-form-item label="比赛开始时间"><el-date-picker v-model="drawForm.competition_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" placeholder="学校当地时间"/></el-form-item>
      <el-form-item label="比赛场地"><el-input v-model="drawForm.venue" maxlength="128"/></el-form-item>
      <el-form-item label="每队时段(分钟)"><el-input-number v-model="drawForm.slot_minutes" :min="1" :max="120"/><span style="margin-left:8px">含比赛及换场</span></el-form-item>
      <el-form-item label="提前检录(分钟)"><el-input-number v-model="drawForm.check_in_minutes" :min="0" :max="120"/></el-form-item>
    </el-form>
    <template #footer>
      <el-button :disabled="busy" @click="drawDialog = false">取消</el-button>
      <el-button type="primary" :loading="busy" @click="generateSchedule">生成抽签与赛程草稿</el-button>
    </template>
  </el-dialog>
</template>
