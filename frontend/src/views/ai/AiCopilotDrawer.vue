<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  ChatDotRound, CircleClose, Close, Delete,
  Loading, Opportunity, Plus, Promotion, Refresh, Service, VideoPause
} from '@element-plus/icons-vue'
import { useAuthStore } from '../../stores/auth'
import {
  createConversation,
  deleteConversation,
  fetchConversationMessages,
  fetchConversations,
  fetchSuggestedPrompts,
  formatMarkdown,
  streamChat,
  type Conversation,
  type Message,
} from './aiApi'

const props = defineProps<{
  modelValue: boolean
  currentMeetId?: number | null
  currentEventId?: number | null
  currentPage?: string | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
}>()

const auth = useAuthStore()
const user = computed(() => auth.user || {})
const role = computed(() => user.value.role || 'STUDENT')
const roleLabel: Record<string, string> = {
  DEVELOPER: '系统管理员',
  SPORTS_TEACHER: '体育部主管',
  REFEREE: '裁判员',
  SCORER: '计分员',
  REFEREE_SCORER: '裁判兼计分员',
  STUDENT: '参赛学生',
}

const conversations = ref<Conversation[]>([])
const currentConvId = ref<string | null>(null)
const messages = ref<Message[]>([])
const inputText = ref('')
const isGenerating = ref(false)
const abortController = ref<AbortController | null>(null)
const suggestedPrompts = ref<string[]>([])
const activeToolNotice = ref<string | null>(null)
const chatScrollArea = ref<HTMLElement | null>(null)

async function loadConversations() {
  try {
    const list = await fetchConversations()
    conversations.value = list
    const first = list[0]
    if (first && !currentConvId.value) {
      currentConvId.value = first.id
      await loadMessages(first.id)
    } else if (list.length === 0) {
      await handleNewConversation()
    }
  } catch (e) {
    console.error(e)
  }
}

async function loadMessages(convId: string) {
  try {
    messages.value = await fetchConversationMessages(convId)
    scrollToBottom()
  } catch (e) {
    console.error(e)
  }
}

async function handleSelectConv(id: string) {
  currentConvId.value = id
  await loadMessages(id)
}

async function handleNewConversation() {
  try {
    const newConv = await createConversation({
      title: '新协同会话',
      meet_id: props.currentMeetId,
    })
    conversations.value.unshift(newConv)
    currentConvId.value = newConv.id
    messages.value = []
    activeToolNotice.value = null
  } catch (e) {
    ElMessage.error('创建新会话失败')
  }
}

async function handleDeleteCurrentConv() {
  if (!currentConvId.value) return
  try {
    await deleteConversation(currentConvId.value)
    conversations.value = conversations.value.filter(c => c.id !== currentConvId.value)
    const first = conversations.value[0]
    if (first) {
      currentConvId.value = first.id
      await loadMessages(first.id)
    } else {
      await handleNewConversation()
    }
    ElMessage.success('对话已清除')
  } catch (e) {
    ElMessage.error('删除对话失败')
  }
}

async function loadPrompts() {
  try {
    const res = await fetchSuggestedPrompts()
    suggestedPrompts.value = res.prompts || []
  } catch (e) {
    console.error(e)
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (chatScrollArea.value) {
      chatScrollArea.value.scrollTop = chatScrollArea.value.scrollHeight
    }
  })
}

function handlePromptClick(promptText: string) {
  inputText.value = promptText
  handleSendMessage()
}

async function handleSendMessage() {
  const query = inputText.value.trim()
  if (!query || isGenerating.value) return

  inputText.value = ''
  isGenerating.value = true
  activeToolNotice.value = null

  // Push temporary user message to UI
  const tempUserMsg: Message = {
    id: Date.now(),
    conversation_id: currentConvId.value || '',
    role: 'user',
    content: query,
    created_at: new Date().toISOString(),
  }
  messages.value.push(tempUserMsg)

  // Push empty assistant message to receive tokens
  const tempAssistantMsg: Message = {
    id: Date.now() + 1,
    conversation_id: currentConvId.value || '',
    role: 'assistant',
    content: '',
    created_at: new Date().toISOString(),
  }
  messages.value.push(tempAssistantMsg)
  scrollToBottom()

  abortController.value = new AbortController()

  await streamChat(
    {
      conversation_id: currentConvId.value,
      message: query,
      meet_id: props.currentMeetId,
      event_id: props.currentEventId,
      page_context: props.currentPage,
    },
    {
      onStart(convId) {
        currentConvId.value = convId
      },
      onToken(text) {
        tempAssistantMsg.content += text
        scrollToBottom()
      },
      onToolStart(toolName) {
        activeToolNotice.value = `正在检索系统工具 [${toolName}]...`
        scrollToBottom()
      },
      onToolDone(toolName) {
        activeToolNotice.value = `系统数据已检索完毕`
        setTimeout(() => {
          activeToolNotice.value = null
        }, 3000)
        scrollToBottom()
      },
      onDone(_msgId, content, usage) {
        tempAssistantMsg.content = content
        tempAssistantMsg.token_usage = usage
        isGenerating.value = false
        activeToolNotice.value = null
        scrollToBottom()
      },
      onError(err) {
        tempAssistantMsg.content += `\n\n[提示：${err}]`
        isGenerating.value = false
        activeToolNotice.value = null
        scrollToBottom()
      },
    },
    abortController.value.signal,
  )
}

function handleStopGeneration() {
  if (abortController.value) {
    abortController.value.abort()
    isGenerating.value = false
    activeToolNotice.value = null
    ElMessage.info('已停止生成')
  }
}

function handleKeyDown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSendMessage()
  }
}

watch(
  () => props.modelValue,
  (val) => {
    if (val) {
      loadConversations()
      loadPrompts()
    }
  },
)

onMounted(() => {
  if (props.modelValue) {
    loadConversations()
    loadPrompts()
  }
})
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    size="520px"
    :with-header="false"
    class="apple-copilot-drawer"
    destroy-on-close
  >
    <div class="copilot-container">
      <!-- 1. 页面顶栏 -->
      <header class="copilot-header">
        <div class="header-left">
          <div class="ai-avatar-badge">
            <el-icon><ChatDotRound/></el-icon>
          </div>
          <div>
            <div class="title-row">
              <h3>AI 赛事协同中心</h3>
              <span class="role-chip">{{ roleLabel[role] || role }}</span>
            </div>
            <p class="subtitle">校园运动会赛事成绩管理系统 · AI 赛事协同</p>
          </div>
        </div>

        <div class="header-right">
          <button class="icon-action-btn" @click="handleNewConversation" title="新建会话">
            <el-icon><Plus/></el-icon>
          </button>
          <button class="icon-action-btn" @click="handleDeleteCurrentConv" title="清除当前会话">
            <el-icon><Delete/></el-icon>
          </button>
          <button class="icon-action-btn close" @click="emit('update:modelValue', false)" title="关闭">
            <el-icon><Close/></el-icon>
          </button>
        </div>
      </header>

      <!-- 会话快速选择与上下文胶囊 -->
      <div class="copilot-context-bar">
        <el-select
          v-model="currentConvId"
          size="small"
          placeholder="历史会话"
          class="conv-select"
          @change="handleSelectConv"
        >
          <el-option
            v-for="c in conversations"
            :key="c.id"
            :label="c.title"
            :value="c.id"
          />
        </el-select>

        <div class="context-tag" v-if="currentMeetId || currentEventId">
          <span v-if="currentMeetId">📍 运动会 #{{ currentMeetId }}</span>
          <span v-if="currentEventId">· 项目 #{{ currentEventId }}</span>
        </div>
      </div>

      <!-- 2. 消息展示区域 -->
      <div class="copilot-messages-wrap" ref="chatScrollArea">
        <!-- 亲切迎宾卡片 -->
        <div class="welcome-card" v-if="messages.length === 0">
          <div class="welcome-icon">🏅</div>
          <h4>你好，{{ user.display_name || '同学' }}！</h4>
          <p>
            我是运动会智能协同助手。我已同步你的【{{ roleLabel[role] || role }}】身份与当前赛事上下文。
            你可以直接向我用自然语言查询赛程、成绩、分析数据或解答规则。
          </p>

          <div class="suggested-box" v-if="suggestedPrompts.length > 0">
            <div class="suggested-label">
              <el-icon><Opportunity/></el-icon> 快捷业务提问推荐
            </div>
            <div class="prompt-chips">
              <button
                v-for="p in suggestedPrompts"
                :key="p"
                class="prompt-chip"
                @click="handlePromptClick(p)"
              >
                {{ p }}
              </button>
            </div>
          </div>
        </div>

        <!-- 历史消息列表 -->
        <template v-else>
          <div
            v-for="msg in messages"
            :key="msg.id"
            :class="['message-item', msg.role]"
          >
            <div v-if="msg.role === 'assistant'" class="msg-avatar ai">AI</div>
            <div class="message-bubble-wrap">
              <div
                v-if="msg.role === 'assistant'"
                class="message-bubble assistant"
                v-html="formatMarkdown(msg.content)"
              />
              <div
                v-else-if="msg.role === 'user'"
                class="message-bubble user"
              >
                {{ msg.content }}
              </div>
              <div v-if="msg.created_at" class="msg-time">
                {{ new Date(msg.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }}
              </div>
            </div>
            <div v-if="msg.role === 'user'" class="msg-avatar user">我</div>
          </div>
        </template>

        <!-- 工具调用实时通知胶囊 -->
        <div v-if="activeToolNotice" class="tool-notice-capsule">
          <el-icon class="is-loading"><Loading/></el-icon>
          <span>{{ activeToolNotice }}</span>
        </div>

        <!-- 流式打字指示器 -->
        <div v-if="isGenerating" class="typing-indicator">
          <span></span><span></span><span></span>
        </div>
      </div>

      <!-- 3. 底部输入与快捷发送区域 -->
      <footer class="copilot-footer">
        <div class="quick-pills-bar" v-if="messages.length > 0 && suggestedPrompts.length > 0">
          <button
            v-for="p in suggestedPrompts.slice(0, 3)"
            :key="p"
            class="mini-pill"
            @click="handlePromptClick(p)"
            :disabled="isGenerating"
          >
            {{ p }}
          </button>
        </div>

        <div class="input-glass-box">
          <textarea
            v-model="inputText"
            rows="2"
            placeholder="输入你的业务问题（如：我下一场比赛几点？查待审核成绩...）"
            @keydown="handleKeyDown"
            :disabled="isGenerating"
          />
          <div class="box-actions">
            <span class="shortcut-tip">Enter 发送 · Shift+Enter 换行</span>
            <button
              v-if="isGenerating"
              class="stop-btn"
              @click="handleStopGeneration"
            >
              <el-icon><VideoPause/></el-icon> 停止
            </button>
            <button
              v-else
              class="send-btn"
              :disabled="!inputText.trim()"
              @click="handleSendMessage"
            >
              <el-icon><Promotion/></el-icon>
            </button>
          </div>
        </div>
      </footer>
    </div>
  </el-drawer>
</template>

<style scoped>
:deep(.el-drawer__body) {
  padding: 0 !important;
  background: #fbfbfd;
}

.copilot-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fbfbfd;
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", "Segoe UI", sans-serif;
}

/* 1. Header */
.copilot-header {
  height: 64px;
  padding: 0 20px;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(20px) saturate(180%);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.ai-avatar-badge {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: linear-gradient(135deg, #007aff 0%, #5856d6 100%);
  color: #ffffff;
  display: grid;
  place-items: center;
  font-size: 18px;
  box-shadow: 0 4px 12px rgba(88, 86, 214, 0.25);
}

.title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.title-row h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: #1c1c1e;
}

.role-chip {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 9999px;
  background: rgba(0, 122, 255, 0.1);
  color: #007aff;
}

.subtitle {
  margin: 1px 0 0;
  font-size: 11px;
  color: #8e8e93;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 6px;
}

.icon-action-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid rgba(0, 0, 0, 0.05);
  background: #ffffff;
  color: #3a3a3c;
  cursor: pointer;
  display: grid;
  place-items: center;
  font-size: 14px;
  transition: all 0.2s;
}

.icon-action-btn:hover {
  background: #f2f2f7;
}

.icon-action-btn.close {
  color: #8e8e93;
}

/* Context Bar */
.copilot-context-bar {
  padding: 8px 18px;
  background: #f5f5f7;
  border-bottom: 1px solid rgba(0, 0, 0, 0.04);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.conv-select {
  width: 220px;
}

.context-tag {
  font-size: 11px;
  color: #8e8e93;
  white-space: nowrap;
}

/* 2. Messages */
.copilot-messages-wrap {
  flex: 1;
  overflow-y: auto;
  padding: 20px 18px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.welcome-card {
  background: #ffffff;
  border-radius: 18px;
  padding: 24px 20px;
  border: 1px solid rgba(0, 0, 0, 0.05);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.02);
  text-align: center;
}

.welcome-icon {
  font-size: 38px;
  margin-bottom: 8px;
}

.welcome-card h4 {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  color: #1c1c1e;
}

.welcome-card p {
  margin: 8px 0 16px;
  font-size: 13px;
  line-height: 1.5;
  color: #636366;
}

.suggested-box {
  text-align: left;
  background: #f9f9fb;
  border-radius: 12px;
  padding: 12px 14px;
}

.suggested-label {
  font-size: 12px;
  font-weight: 700;
  color: #8e8e93;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.prompt-chips {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.prompt-chip {
  text-align: left;
  padding: 8px 12px;
  background: #ffffff;
  border: 1px solid rgba(0, 0, 0, 0.05);
  border-radius: 8px;
  font-size: 12px;
  color: #1c1c1e;
  cursor: pointer;
  transition: all 0.2s;
}

.prompt-chip:hover {
  border-color: #007aff;
  color: #007aff;
  transform: translateX(2px);
}

/* Chat Bubbles */
.message-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.message-item.user {
  justify-content: flex-end;
}

.msg-avatar {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 700;
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.msg-avatar.ai {
  background: linear-gradient(135deg, #007aff 0%, #5856d6 100%);
  color: #ffffff;
}

.msg-avatar.user {
  background: #007aff;
  color: #ffffff;
}

.message-bubble-wrap {
  max-width: 82%;
  display: flex;
  flex-direction: column;
}

.message-item.user .message-bubble-wrap {
  align-items: flex-end;
}

.message-bubble {
  padding: 12px 16px;
  border-radius: 16px;
  font-size: 13.5px;
  line-height: 1.6;
  word-break: break-word;
}

.message-bubble.user {
  background: #007aff;
  color: #ffffff;
  border-bottom-right-radius: 4px;
}

.message-bubble.assistant {
  background: #ffffff;
  color: #1c1c1e;
  border: 1px solid rgba(0, 0, 0, 0.05);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.02);
  border-bottom-left-radius: 4px;
}

.msg-time {
  font-size: 10px;
  color: #aeaeb2;
  margin-top: 4px;
}

/* Tool notice capsule */
.tool-notice-capsule {
  align-self: center;
  padding: 6px 14px;
  border-radius: 9999px;
  background: rgba(88, 86, 214, 0.1);
  color: #5856d6;
  font-size: 12px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% { opacity: 0.8; }
  50% { opacity: 1; }
  100% { opacity: 0.8; }
}

/* Typing Indicator */
.typing-indicator {
  align-self: flex-start;
  margin-left: 42px;
  display: flex;
  gap: 4px;
}

.typing-indicator span {
  width: 6px;
  height: 6px;
  background: #c7c7cc;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
.typing-indicator span:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

/* 3. Footer */
.copilot-footer {
  padding: 12px 18px 16px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20px);
  border-top: 1px solid rgba(0, 0, 0, 0.05);
}

.quick-pills-bar {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
  overflow-x: auto;
  padding-bottom: 2px;
}

.mini-pill {
  white-space: nowrap;
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 9999px;
  border: 1px solid rgba(0, 122, 255, 0.2);
  background: rgba(0, 122, 255, 0.06);
  color: #007aff;
  cursor: pointer;
  transition: all 0.2s;
}

.mini-pill:hover {
  background: rgba(0, 122, 255, 0.15);
}

.input-glass-box {
  background: #ffffff;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 14px;
  padding: 10px 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.02);
  display: flex;
  flex-direction: column;
}

.input-glass-box textarea {
  border: none;
  outline: none;
  resize: none;
  font-size: 13px;
  line-height: 1.4;
  color: #1c1c1e;
  font-family: inherit;
  width: 100%;
}

.box-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 6px;
  padding-top: 4px;
  border-top: 1px solid rgba(0, 0, 0, 0.04);
}

.shortcut-tip {
  font-size: 11px;
  color: #aeaeb2;
}

.send-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: none;
  background: #007aff;
  color: #ffffff;
  cursor: pointer;
  display: grid;
  place-items: center;
  font-size: 15px;
  transition: opacity 0.2s;
}

.send-btn:disabled {
  background: #e5e5ea;
  color: #aeaeb2;
  cursor: not-allowed;
}

.stop-btn {
  padding: 4px 10px;
  border-radius: 8px;
  border: 1px solid rgba(255, 59, 48, 0.3);
  background: rgba(255, 59, 48, 0.1);
  color: #ff3b30;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
}

/* Markdown Formatted Elements */
:deep(.ai-p) {
  margin: 0 0 6px;
}

:deep(.ai-p:last-child) {
  margin-bottom: 0;
}

:deep(.ai-h2), :deep(.ai-h3), :deep(.ai-h4) {
  margin: 10px 0 4px;
  color: #1c1c1e;
  font-weight: 700;
}

:deep(.ai-li) {
  margin-left: 18px;
  margin-bottom: 3px;
}

:deep(.apple-inline-code) {
  font-family: ui-monospace, SFMono-Regular, monospace;
  background: rgba(0, 0, 0, 0.06);
  color: #d12f1b;
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 12px;
}

:deep(.apple-code-block) {
  font-family: ui-monospace, SFMono-Regular, monospace;
  background: #1c1c1e;
  color: #f5f5f7;
  padding: 10px 12px;
  border-radius: 10px;
  font-size: 11px;
  overflow-x: auto;
  margin: 6px 0;
}

:deep(.apple-table-wrap) {
  overflow-x: auto;
  margin: 8px 0;
  border-radius: 8px;
  border: 1px solid rgba(0, 0, 0, 0.08);
}

:deep(.apple-ai-table) {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

:deep(.apple-ai-table th) {
  background: #f2f2f7;
  padding: 6px 10px;
  text-align: left;
  font-weight: 600;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

:deep(.apple-ai-table td) {
  padding: 6px 10px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.04);
}
</style>
