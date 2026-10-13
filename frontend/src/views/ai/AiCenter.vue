<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  CirclePlus, Connection, Cpu, DataAnalysis, Delete, Document, Edit,
  Loading, Refresh, Setting, SuccessFilled, WarningFilled
} from '@element-plus/icons-vue'
import {
  createAiModel,
  deleteAiModel,
  fetchAiAuditLogs,
  fetchAiModels,
  fetchAiStats,
  testAiConnection,
  updateAiModel,
  type ConnectionTestResult,
  type ModelConfig,
} from './aiApi'
import { errorMessage } from '../../api'

const activeTab = ref('models')
const loading = ref(false)
const models = ref<ModelConfig[]>([])
const stats = reactive<any>({
  total_conversations: 0,
  total_messages: 0,
  total_tool_calls: 0,
  total_tokens: 0,
  avg_latency_ms: 0,
  success_rate: 100,
})
const auditLogs = ref<any[]>([])

// Dialog & Form
const modelDialog = ref(false)
const isEditing = ref(false)
const editingId = ref<number | null>(null)
const testLoading = ref<number | null>(null)
const dialogTestLoading = ref(false)
const dialogTestResult = ref<ConnectionTestResult | null>(null)

const form = reactive<any>({
  provider_name: '',
  provider_type: 'DEEPSEEK',
  base_url: 'https://api.deepseek.com/v1',
  api_key: '',
  model_name: 'deepseek-chat',
  temperature: 0.3,
  max_tokens: 2048,
  timeout: 30,
  is_enabled: true,
  is_default: false,
  is_fallback: false,
})

const auditDetailDialog = ref(false)
const selectedAudit = ref<any>(null)

const providerPresets: Record<string, { base_url: string; model_name: string }> = {
  DEEPSEEK: { base_url: 'https://api.deepseek.com/v1', model_name: 'deepseek-chat' },
  OPENAI: { base_url: 'https://api.openai.com/v1', model_name: 'gpt-4o-mini' },
  CLAUDE: { base_url: 'https://api.anthropic.com/v1', model_name: 'claude-3-5-sonnet-20241022' },
  GEMINI: { base_url: 'https://generativelanguage.googleapis.com', model_name: 'gemini-1.5-flash' },
  OPENAI_COMPATIBLE: { base_url: 'https://api.openai.com/v1', model_name: 'gpt-3.5-turbo' },
  CUSTOM: { base_url: 'http://localhost:8000/v1', model_name: 'custom-model' },
}

function onProviderTypeChange(val: string) {
  if (providerPresets[val] && !isEditing.value) {
    form.base_url = providerPresets[val].base_url
    form.model_name = providerPresets[val].model_name
  }
}

async function loadData() {
  loading.value = true
  try {
    if (activeTab.value === 'models') {
      models.value = await fetchAiModels()
    } else if (activeTab.value === 'stats') {
      const data = await fetchAiStats()
      Object.assign(stats, data)
    } else if (activeTab.value === 'audit') {
      auditLogs.value = await fetchAiAuditLogs(100)
    }
  } catch (e) {
    ElMessage.error(errorMessage(e))
  } finally {
    loading.value = false
  }
}

function openCreateModel() {
  isEditing.value = false
  editingId.value = null
  dialogTestResult.value = null
  Object.assign(form, {
    provider_name: 'DeepSeek 官方模型服务',
    provider_type: 'DEEPSEEK',
    base_url: 'https://api.deepseek.com/v1',
    api_key: '',
    model_name: 'deepseek-chat',
    temperature: 0.3,
    max_tokens: 2048,
    timeout: 30,
    is_enabled: true,
    is_default: models.value.length === 0,
    is_fallback: false,
  })
  modelDialog.value = true
}

function openEditModel(m: ModelConfig) {
  isEditing.value = true
  editingId.value = m.id
  dialogTestResult.value = null
  Object.assign(form, {
    provider_name: m.provider_name,
    provider_type: m.provider_type,
    base_url: m.base_url,
    api_key: m.api_key_masked,
    model_name: m.model_name,
    temperature: m.temperature,
    max_tokens: m.max_tokens,
    timeout: m.timeout,
    is_enabled: m.is_enabled,
    is_default: m.is_default,
    is_fallback: m.is_fallback,
  })
  modelDialog.value = true
}

async function handleSaveModel() {
  if (!form.provider_name || !form.base_url || !form.model_name) {
    return ElMessage.warning('请完整填写服务名称、接口地址和模型标识')
  }
  if (!form.api_key) {
    return ElMessage.warning('请填写 API Key')
  }
  try {
    if (isEditing.value && editingId.value) {
      await updateAiModel(editingId.value, form)
      ElMessage.success('模型服务配置已更新')
    } else {
      await createAiModel(form)
      ElMessage.success('模型服务已成功接入')
    }
    modelDialog.value = false
    await loadData()
  } catch (e) {
    ElMessage.error(errorMessage(e))
  }
}

async function handleDeleteModel(m: ModelConfig) {
  try {
    await ElMessageBox.confirm(`确定删除模型服务配置“${m.provider_name}”吗？`, '删除模型配置', {
      type: 'warning',
    })
    await deleteAiModel(m.id)
    ElMessage.success('已删除')
    await loadData()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(errorMessage(e))
  }
}

async function handleCardTest(m: ModelConfig) {
  testLoading.value = m.id
  try {
    const res = await testAiConnection({
      model_config_id: m.id,
      provider_type: m.provider_type,
      base_url: m.base_url,
      model_name: m.model_name,
      timeout: m.timeout,
    })
    if (res.code === 'CONNECTED') {
      ElMessage.success({ message: `【${m.provider_name}】连接测试成功！耗时 ${res.latency_ms}ms`, duration: 4000 })
    } else {
      ElMessage.error({ message: `【${m.provider_name}】连接测试异常：${res.message}`, duration: 5000 })
    }
  } catch (e) {
    ElMessage.error(errorMessage(e))
  } finally {
    testLoading.value = null
  }
}

async function handleDialogTest() {
  if (!form.base_url || !form.model_name || !form.api_key) {
    return ElMessage.warning('请先填写 Base URL、Model 与 API Key')
  }
  dialogTestLoading.value = true
  dialogTestResult.value = null
  try {
    const payload: any = {
      provider_type: form.provider_type,
      base_url: form.base_url,
      model_name: form.model_name,
      timeout: form.timeout,
    }
    if (isEditing.value && editingId.value && form.api_key.includes('***')) {
      payload.model_config_id = editingId.value
    } else {
      payload.api_key = form.api_key
    }
    dialogTestResult.value = await testAiConnection(payload)
  } catch (e) {
    dialogTestResult.value = {
      status: 'Other Error',
      code: 'OTHER_ERROR',
      latency_ms: 0,
      message: errorMessage(e),
    }
  } finally {
    dialogTestLoading.value = false
  }
}

function openAuditDetail(row: any) {
  selectedAudit.value = row
  auditDetailDialog.value = true
}

onMounted(() => {
  loadData()
})
</script>

<template>
  <div class="ai-center-workspace">
    <!-- 顶部标签导航 -->
    <div class="apple-tab-bar">
      <div class="tab-pill-group">
        <button
          :class="['tab-pill', { active: activeTab === 'models' }]"
          @click="activeTab = 'models'; loadData()"
        >
          <el-icon><Cpu/></el-icon> 模型服务管理
        </button>
        <button
          :class="['tab-pill', { active: activeTab === 'stats' }]"
          @click="activeTab = 'stats'; loadData()"
        >
          <el-icon><DataAnalysis/></el-icon> AI 运行监控与统计
        </button>
        <button
          :class="['tab-pill', { active: activeTab === 'audit' }]"
          @click="activeTab = 'audit'; loadData()"
        >
          <el-icon><Document/></el-icon> AI 审计追踪与日志
        </button>
      </div>

      <div class="tab-bar-actions">
        <button v-if="activeTab === 'models'" class="apple-primary-btn" @click="openCreateModel">
          <el-icon><CirclePlus/></el-icon> 接入新大模型
        </button>
        <button class="apple-secondary-btn" @click="loadData" :disabled="loading">
          <el-icon :class="{ 'is-loading': loading }"><Refresh/></el-icon> 刷新
        </button>
      </div>
    </div>

    <!-- 1. 模型服务管理 -->
    <section v-if="activeTab === 'models'" class="tab-content">
      <div v-if="models.length === 0 && !loading" class="empty-glass-card">
        <div class="empty-icon"><el-icon><Cpu/></el-icon></div>
        <h3>暂未接入大模型服务</h3>
        <p>支持配置 DeepSeek、OpenAI、Claude、Gemini 以及各类 OpenAI 兼容端点</p>
        <button class="apple-primary-btn" style="margin-top: 16px" @click="openCreateModel">
          <el-icon><CirclePlus/></el-icon> 立即配置第一个大语言模型
        </button>
      </div>

      <div v-else class="provider-grid">
        <article
          v-for="m in models"
          :key="m.id"
          :class="['provider-card', { 'is-default': m.is_default, 'is-disabled': !m.is_enabled }]"
        >
          <div class="provider-card-header">
            <div class="provider-title-group">
              <span class="provider-type-tag">{{ m.provider_type }}</span>
              <h4>{{ m.provider_name }}</h4>
            </div>
            <div class="status-badges">
              <span v-if="m.is_default" class="badge-pill default">默认主模型</span>
              <span v-if="m.is_fallback" class="badge-pill fallback">备用降级</span>
              <span :class="['badge-pill', m.is_enabled ? 'enabled' : 'disabled']">
                {{ m.is_enabled ? '已启用' : '已停用' }}
              </span>
            </div>
          </div>

          <div class="provider-details">
            <div class="detail-row">
              <span class="label">模型标识</span>
              <span class="value font-mono">{{ m.model_name }}</span>
            </div>
            <div class="detail-row">
              <span class="label">接口地址</span>
              <span class="value font-mono ellipsis" :title="m.base_url">{{ m.base_url }}</span>
            </div>
            <div class="detail-row">
              <span class="label">凭证密文</span>
              <span class="value font-mono key-mask">{{ m.api_key_masked }}</span>
            </div>
            <div class="detail-row params">
              <span>温度: {{ m.temperature }}</span>
              <span>最大Token: {{ m.max_tokens }}</span>
              <span>超时: {{ m.timeout }}s</span>
            </div>
          </div>

          <div class="provider-actions">
            <button
              class="action-btn test"
              :disabled="testLoading === m.id"
              @click="handleCardTest(m)"
            >
              <el-icon v-if="testLoading === m.id" class="is-loading"><Loading/></el-icon>
              <el-icon v-else><Connection/></el-icon>
              测试连接
            </button>
            <button class="action-btn edit" @click="openEditModel(m)">
              <el-icon><Edit/></el-icon> 编辑
            </button>
            <button class="action-btn delete" @click="handleDeleteModel(m)">
              <el-icon><Delete/></el-icon>
            </button>
          </div>
        </article>
      </div>
    </section>

    <!-- 2. AI 运行监控与统计 Bento -->
    <section v-if="activeTab === 'stats'" class="tab-content">
      <div class="apple-bento-grid">
        <article class="apple-bento-card panel blue">
          <div class="bento-top">
            <div class="sf-badge blue"><el-icon><Cpu/></el-icon></div>
            <span class="apple-chip">CONVERSATIONS</span>
          </div>
          <div class="bento-number">{{ stats.total_conversations }}</div>
          <span class="bento-title">隔离会话总数</span>
          <small>多角色完全数据隔离</small>
        </article>

        <article class="apple-bento-card panel purple">
          <div class="bento-top">
            <div class="sf-badge purple"><el-icon><Document/></el-icon></div>
            <span class="apple-chip purple">MESSAGES</span>
          </div>
          <div class="bento-number">{{ stats.total_messages }}</div>
          <span class="bento-title">协同问答总条数</span>
          <small>包含多轮推理与建议</small>
        </article>

        <article class="apple-bento-card panel green">
          <div class="bento-top">
            <div class="sf-badge green"><el-icon><Connection/></el-icon></div>
            <span class="apple-chip green">TOOL CALLS</span>
          </div>
          <div class="bento-number">{{ stats.total_tool_calls }}</div>
          <span class="bento-title">结构化工具调用</span>
          <small>真实业务 Service 访问</small>
        </article>

        <article class="apple-bento-card panel orange">
          <div class="bento-top">
            <div class="sf-badge orange"><el-icon><DataAnalysis/></el-icon></div>
            <span class="apple-chip orange">TOKENS & HEALTH</span>
          </div>
          <div class="bento-number" style="font-size: 26px">{{ stats.total_tokens.toLocaleString() }}</div>
          <span class="bento-title">Token 消耗量</span>
          <small>平均耗时: {{ stats.avg_latency_ms }}ms · 成功率: {{ stats.success_rate }}%</small>
        </article>
      </div>

      <div class="mac-card" style="margin-top: 24px">
        <div class="mac-card-head">
          <div>
            <h3>AI 架构健康度与安全防护机制</h3>
            <p>基于 RBAC 强约束与 Human-in-the-Loop 的双重保护状态</p>
          </div>
        </div>
        <div class="health-indicators-grid">
          <div class="health-card">
            <div class="h-icon green"><el-icon><SuccessFilled/></el-icon></div>
            <div>
              <b>RBAC 数据沙箱</b>
              <p>启用 · 学生仅可查本人数据，高危操作已完全拦截</p>
            </div>
          </div>
          <div class="health-card">
            <div class="h-icon green"><el-icon><SuccessFilled/></el-icon></div>
            <div>
              <b>凭证存储加密</b>
              <p>启用 · 基于 AES-GCM-256 算法，前端脱敏返回</p>
            </div>
          </div>
          <div class="health-card">
            <div class="h-icon green"><el-icon><SuccessFilled/></el-icon></div>
            <div>
              <b>Fallback 自动容灾降级</b>
              <p>就绪 · 主模型异常时自动无感切换备用渠道</p>
            </div>
          </div>
          <div class="health-card">
            <div class="h-icon green"><el-icon><SuccessFilled/></el-icon></div>
            <div>
              <b>全链路审计跟踪</b>
              <p>启用 · 完整留存 Tool 参数、耗时与决策链路</p>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 3. AI 审计日志 -->
    <section v-if="activeTab === 'audit'" class="tab-content">
      <div class="mac-card">
        <div class="mac-card-head">
          <div>
            <h3>AI 智能审计追踪日志 (Audit Trail)</h3>
            <p>实时记录大模型调用、工具执行与安全核验记录</p>
          </div>
        </div>

        <el-table :data="auditLogs" stripe style="width: 100%" v-loading="loading">
          <el-table-column prop="id" label="ID" width="70"/>
          <el-table-column prop="created_at" label="调用时间" width="160"/>
          <el-table-column prop="user_role" label="操作角色" width="120">
            <template #default="{ row }">
              <el-tag size="small">{{ row.user_role || 'SYSTEM' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="action_type" label="操作类型" width="130">
            <template #default="{ row }">
              <span class="font-mono">{{ row.action_type }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="model" label="服务模型" width="150"/>
          <el-table-column prop="tool_name" label="触发工具" min-width="160">
            <template #default="{ row }">
              <span v-if="row.tool_name" class="tool-tag font-mono">{{ row.tool_name }}</span>
              <span v-else style="color: #8e8e93">—</span>
            </template>
          </el-table-column>
          <el-table-column prop="latency_ms" label="耗时" width="90">
            <template #default="{ row }">
              <span>{{ row.latency_ms }}ms</span>
            </template>
          </el-table-column>
          <el-table-column prop="success" label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.success ? 'success' : 'danger'" size="small">
                {{ row.success ? '成功' : '失败' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="详情" width="90" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="openAuditDetail(row)">
                查看
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </section>

    <!-- 新建/编辑模型对话框 -->
    <el-dialog
      v-model="modelDialog"
      :title="isEditing ? '编辑大模型接入服务' : '接入新大语言模型'"
      width="680px"
      destroy-on-close
    >
      <el-form :model="form" label-width="120px" class="apple-dialog-form">
        <el-form-item label="服务名称" required>
          <el-input v-model="form.provider_name" placeholder="如：DeepSeek 官方 API / 校内私有化部署"/>
        </el-form-item>

        <el-form-item label="服务类型" required>
          <el-select v-model="form.provider_type" @change="onProviderTypeChange" style="width: 100%">
            <el-option label="DeepSeek (深度求索)" value="DEEPSEEK"/>
            <el-option label="OpenAI (GPT-4o / 3.5)" value="OPENAI"/>
            <el-option label="Anthropic Claude" value="CLAUDE"/>
            <el-option label="Google Gemini" value="GEMINI"/>
            <el-option label="OpenAI 兼容接口 (vLLM/Qwen/Kimi/Ollama)" value="OPENAI_COMPATIBLE"/>
            <el-option label="Custom (自定义适配器)" value="CUSTOM"/>
          </el-select>
        </el-form-item>

        <el-form-item label="Base URL" required>
          <el-input v-model="form.base_url" placeholder="如：https://api.deepseek.com/v1"/>
        </el-form-item>

        <el-form-item label="模型标识" required>
          <el-input v-model="form.model_name" placeholder="如：deepseek-chat, gpt-4o-mini"/>
        </el-form-item>

        <el-form-item label="API Key" required>
          <el-input
            v-model="form.api_key"
            type="password"
            show-password
            placeholder="输入 API 密钥 (数据库安全加密保存，前端永不返回明文)"
          />
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="Temperature">
              <el-input-number v-model="form.temperature" :step="0.1" :min="0" :max="1" style="width: 100%"/>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="超时时间 (秒)">
              <el-input-number v-model="form.timeout" :min="5" :max="120" style="width: 100%"/>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="启用状态">
              <el-switch v-model="form.is_enabled"/>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="默认主模型">
              <el-switch v-model="form.is_default"/>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="备用降级">
              <el-switch v-model="form.is_fallback"/>
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 测试连接反馈条 -->
        <div v-if="dialogTestResult" :class="['dialog-test-alert', dialogTestResult.code]">
          <el-icon v-if="dialogTestResult.code === 'CONNECTED'"><SuccessFilled/></el-icon>
          <el-icon v-else><WarningFilled/></el-icon>
          <div class="test-text">
            <b>{{ dialogTestResult.status }} ({{ dialogTestResult.latency_ms }}ms)</b>
            <p>{{ dialogTestResult.message }}</p>
          </div>
        </div>
      </el-form>

      <template #footer>
        <div class="dialog-footer">
          <button
            class="apple-secondary-btn"
            style="margin-right: auto"
            :disabled="dialogTestLoading"
            @click="handleDialogTest"
          >
            <el-icon v-if="dialogTestLoading" class="is-loading"><Loading/></el-icon>
            <el-icon v-else><Connection/></el-icon>
            测试当前连接
          </button>
          <button class="apple-secondary-btn" @click="modelDialog = false">取消</button>
          <button class="apple-primary-btn" @click="handleSaveModel">保存配置</button>
        </div>
      </template>
    </el-dialog>

    <!-- 审计详情弹窗 -->
    <el-dialog v-model="auditDetailDialog" title="AI 工具调用与审计详情" width="600px">
      <div v-if="selectedAudit" class="audit-detail-body">
        <div class="detail-field">
          <span class="label">动作类型:</span>
          <b>{{ selectedAudit.action_type }}</b>
        </div>
        <div class="detail-field">
          <span class="label">执行模型:</span>
          <span>{{ selectedAudit.model }} ({{ selectedAudit.provider }})</span>
        </div>
        <div class="detail-field">
          <span class="label">工具名称:</span>
          <span class="tool-tag">{{ selectedAudit.tool_name || '无' }}</span>
        </div>
        <div class="detail-field">
          <span class="label">执行入参:</span>
          <pre class="apple-code-block">{{ JSON.stringify(selectedAudit.tool_arguments, null, 2) }}</pre>
        </div>
        <div class="detail-field">
          <span class="label">结果摘要:</span>
          <p>{{ selectedAudit.tool_result_summary || '—' }}</p>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.ai-center-workspace {
  width: 100%;
}

.apple-tab-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.tab-pill-group {
  display: flex;
  background: rgba(0, 0, 0, 0.05);
  padding: 4px;
  border-radius: 12px;
  gap: 4px;
}

.tab-pill {
  padding: 8px 18px;
  border-radius: 10px;
  border: none;
  background: transparent;
  color: #3a3a3c;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.tab-pill.active {
  background: #ffffff;
  color: #007aff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.tab-bar-actions {
  display: flex;
  gap: 10px;
}

.apple-primary-btn {
  height: 36px;
  padding: 0 16px;
  border-radius: 10px;
  border: none;
  background: #007aff;
  color: #ffffff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition: opacity 0.2s;
}

.apple-primary-btn:hover {
  opacity: 0.9;
}

.apple-secondary-btn {
  height: 36px;
  padding: 0 14px;
  border-radius: 10px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  background: #ffffff;
  color: #1c1c1e;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.apple-secondary-btn:hover {
  background: #f5f5f7;
}

/* Provider Grid */
.provider-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 20px;
}

.provider-card {
  background: #ffffff;
  border-radius: 18px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  padding: 20px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.02);
  display: flex;
  flex-direction: column;
  transition: transform 0.2s, box-shadow 0.2s;
}

.provider-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.05);
}

.provider-card.is-default {
  border-color: rgba(0, 122, 255, 0.35);
  box-shadow: 0 4px 20px rgba(0, 122, 255, 0.08);
}

.provider-card.is-disabled {
  opacity: 0.65;
}

.provider-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
}

.provider-title-group h4 {
  margin: 4px 0 0;
  font-size: 16px;
  font-weight: 700;
  color: #1c1c1e;
}

.provider-type-tag {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.05em;
  padding: 2px 8px;
  border-radius: 6px;
  background: rgba(0, 122, 255, 0.1);
  color: #007aff;
  display: inline-block;
}

.status-badges {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}

.badge-pill {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 9999px;
}

.badge-pill.default {
  background: rgba(0, 122, 255, 0.12);
  color: #007aff;
}

.badge-pill.fallback {
  background: rgba(255, 149, 0, 0.12);
  color: #ff9500;
}

.badge-pill.enabled {
  background: rgba(52, 199, 89, 0.12);
  color: #34c759;
}

.badge-pill.disabled {
  background: rgba(142, 142, 147, 0.12);
  color: #8e8e93;
}

.provider-details {
  background: #f9f9fb;
  border-radius: 12px;
  padding: 12px 14px;
  margin-bottom: 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

.detail-row .label {
  color: #8e8e93;
}

.detail-row .value {
  color: #1c1c1e;
  font-weight: 500;
}

.detail-row.params {
  color: #8e8e93;
  font-size: 11px;
  margin-top: 4px;
  border-top: 1px solid rgba(0, 0, 0, 0.04);
  padding-top: 6px;
}

.key-mask {
  color: #5856d6 !important;
}

.font-mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.ellipsis {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.provider-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: auto;
}

.action-btn {
  height: 32px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: #ffffff;
  color: #3a3a3c;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.action-btn.test {
  flex: 1;
  color: #007aff;
  border-color: rgba(0, 122, 255, 0.2);
  background: rgba(0, 122, 255, 0.05);
}

.action-btn.test:hover {
  background: rgba(0, 122, 255, 0.12);
}

.action-btn.delete {
  color: #ff3b30;
}

.empty-glass-card {
  background: #ffffff;
  border-radius: 20px;
  padding: 60px 20px;
  text-align: center;
  border: 1px solid rgba(0, 0, 0, 0.05);
}

.empty-icon {
  font-size: 48px;
  color: #c7c7cc;
  margin-bottom: 12px;
}

.dialog-test-alert {
  padding: 12px 14px;
  border-radius: 10px;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-top: 10px;
  font-size: 13px;
}

.dialog-test-alert.CONNECTED {
  background: rgba(52, 199, 89, 0.1);
  color: #34c759;
}

.dialog-test-alert.AUTH_FAILED,
.dialog-test-alert.MODEL_NOT_FOUND,
.dialog-test-alert.NETWORK_ERROR,
.dialog-test-alert.OTHER_ERROR {
  background: rgba(255, 59, 48, 0.1);
  color: #ff3b30;
}

.dialog-test-alert.TIMEOUT {
  background: rgba(255, 149, 0, 0.1);
  color: #ff9500;
}

.test-text b {
  display: block;
}

.test-text p {
  margin: 2px 0 0;
  font-size: 12px;
}

.health-indicators-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.health-card {
  padding: 16px;
  background: #f9f9fb;
  border-radius: 14px;
  display: flex;
  align-items: center;
  gap: 14px;
}

.health-card .h-icon {
  font-size: 24px;
}

.health-card .h-icon.green {
  color: #34c759;
}

.health-card b {
  font-size: 14px;
  color: #1c1c1e;
}

.health-card p {
  margin: 2px 0 0;
  font-size: 12px;
  color: #8e8e93;
}

.tool-tag {
  background: rgba(88, 86, 214, 0.1);
  color: #5856d6;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 11px;
}

.apple-code-block {
  background: #1c1c1e;
  color: #f5f5f7;
  padding: 10px;
  border-radius: 8px;
  font-size: 11px;
  overflow-x: auto;
}
</style>
