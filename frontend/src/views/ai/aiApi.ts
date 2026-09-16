import api, { errorMessage } from '../../api'

export interface ModelConfig {
  id: number
  provider_name: string
  provider_type: string
  base_url: string
  api_key_masked: string
  model_name: string
  temperature: number
  max_tokens: number
  timeout: number
  is_enabled: boolean
  is_default: boolean
  is_fallback: boolean
  created_at: string
  updated_at: string
}

export interface Conversation {
  id: string
  title: string
  user_id: number
  user_role: string
  meet_id?: number | null
  created_at: string
  updated_at: string
  message_count: number
}

export interface Message {
  id: number
  conversation_id: string
  role: 'system' | 'user' | 'assistant' | 'tool'
  content: string
  model_name?: string
  provider_type?: string
  tool_calls?: any
  token_usage?: any
  created_at: string
}

export interface ConnectionTestResult {
  status: string
  code: string
  latency_ms: number
  message: string
}

export interface AnomalyItem {
  result_id: number
  event_id: number
  event_name: string
  round_name: string
  participant_name: string
  student_no?: string
  college?: string
  field: string
  value: any
  anomaly_level: 'LOW' | 'MEDIUM' | 'HIGH'
  issue_type: string
  reason: string
  suggested_action: string
}

export interface AnomalyReport {
  total_scanned: number
  anomaly_count: number
  high_count: number
  medium_count: number
  low_count: number
  items: AnomalyItem[]
}

// -----------------------------------------------------------------------------
// API Calls
// -----------------------------------------------------------------------------

export async function fetchAiModels(): Promise<ModelConfig[]> {
  const { data } = await api.get('/ai/models')
  return data
}

export async function createAiModel(payload: any): Promise<ModelConfig> {
  const { data } = await api.post('/ai/models', payload)
  return data
}

export async function updateAiModel(id: number, payload: any): Promise<ModelConfig> {
  const { data } = await api.put(`/ai/models/${id}`, payload)
  return data
}

export async function deleteAiModel(id: number): Promise<void> {
  await api.delete(`/ai/models/${id}`)
}

export async function testAiConnection(payload: any): Promise<ConnectionTestResult> {
  const { data } = await api.post('/ai/models/test-connection', payload)
  return data
}

export async function fetchConversations(): Promise<Conversation[]> {
  const { data } = await api.get('/ai/conversations')
  return data
}

export async function createConversation(payload: { title?: string; meet_id?: number | null }): Promise<Conversation> {
  const { data } = await api.post('/ai/conversations', payload)
  return data
}

export async function deleteConversation(id: string): Promise<void> {
  await api.delete(`/ai/conversations/${id}`)
}

export async function fetchConversationMessages(convId: string): Promise<Message[]> {
  const { data } = await api.get(`/ai/conversations/${convId}/messages`)
  return data
}

export async function sendNonStreamChat(payload: {
  conversation_id?: string | null
  message: string
  meet_id?: number | null
  event_id?: number | null
  page_context?: string | null
}) {
  const { data } = await api.post('/ai/chat', payload)
  return data
}

export async function fetchSuggestedPrompts(): Promise<{ role: string; prompts: string[] }> {
  const { data } = await api.get('/ai/suggested-prompts')
  return data
}

export async function fetchAnomalies(eventId?: number | null, meetId?: number | null): Promise<AnomalyReport> {
  const params: any = {}
  if (eventId) params.event_id = eventId
  if (meetId) params.meet_id = meetId
  const { data } = await api.get('/ai/anomalies', { params })
  return data
}

export async function fetchAiAuditLogs(limit = 50): Promise<any[]> {
  const { data } = await api.get('/ai/audit-logs', { params: { limit } })
  return data
}

export async function fetchAiStats(): Promise<any> {
  const { data } = await api.get('/ai/stats')
  return data
}

// -----------------------------------------------------------------------------
// SSE Streaming Chat Reader
// -----------------------------------------------------------------------------
export async function streamChat(
  payload: {
    conversation_id?: string | null
    message: string
    meet_id?: number | null
    event_id?: number | null
    page_context?: string | null
  },
  callbacks: {
    onStart?: (convId: string) => void
    onToken?: (text: string) => void
    onToolStart?: (toolName: string, args: any) => void
    onToolDone?: (toolName: string, summary: string) => void
    onDone?: (msgId: number, content: string, usage: any) => void
    onError?: (err: string) => void
  },
  signal?: AbortSignal,
) {
  const token = localStorage.getItem('sports_token')
  const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1'

  try {
    const res = await fetch(`${baseUrl}/ai/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: token ? `Bearer ${token}` : '',
      },
      body: JSON.stringify(payload),
      signal,
    })

    if (!res.ok) {
      const errText = await res.text()
      try {
        const errJson = JSON.parse(errText)
        throw new Error(errJson.detail || errJson.message || `请求失败 (${res.status})`)
      } catch {
        throw new Error(`服务异常 (${res.status}): ${errText.slice(0, 100)}`)
      }
    }

    const reader = res.body?.getReader()
    if (!reader) throw new Error('流式读取不可用')

    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      let currentEvent = 'message'
      for (const rawLine of lines) {
        const line = rawLine.trim()
        if (!line) continue
        if (line.startsWith('event: ')) {
          currentEvent = line.slice(7).trim()
        } else if (line.startsWith('data: ')) {
          const dataStr = line.slice(6).trim()
          try {
            const dataObj = JSON.parse(dataStr)
            if (currentEvent === 'start') {
              callbacks.onStart?.(dataObj.conversation_id)
            } else if (currentEvent === 'token') {
              callbacks.onToken?.(dataObj.text)
            } else if (currentEvent === 'tool_start') {
              callbacks.onToolStart?.(dataObj.tool_name, dataObj.arguments)
            } else if (currentEvent === 'tool_done') {
              callbacks.onToolDone?.(dataObj.tool_name, dataObj.summary)
            } else if (currentEvent === 'done') {
              callbacks.onDone?.(dataObj.message_id, dataObj.content, dataObj.token_usage)
            } else if (currentEvent === 'error') {
              callbacks.onError?.(dataObj.error)
            }
          } catch (e) {
            console.error('SSE parse error:', e, dataStr)
          }
        }
      }
    }
  } catch (err: any) {
    if (err.name === 'AbortError') {
      return
    }
    callbacks.onError?.(errorMessage(err))
  }
}

// -----------------------------------------------------------------------------
// Safe Markdown Formatter
// -----------------------------------------------------------------------------
export function formatMarkdown(mdText: string): string {
  if (!mdText) return ''

  let text = mdText
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  // Code blocks: ```lang ... ```
  text = text.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (_match, _lang, code) => {
    return `<pre class="apple-code-block"><code>${code.trim()}</code></pre>`
  })

  // Inline code: `code`
  text = text.replace(/`([^`]+)`/g, '<code class="apple-inline-code">$1</code>')

  // Headers
  text = text.replace(/^### (.*$)/gim, '<h4 class="ai-h4">$1</h4>')
  text = text.replace(/^## (.*$)/gim, '<h3 class="ai-h3">$1</h3>')
  text = text.replace(/^# (.*$)/gim, '<h2 class="ai-h2">$1</h2>')

  // Bold & Italic
  text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  text = text.replace(/\*([^*]+)\*/g, '<em>$1</em>')

  // Bullet points
  text = text.replace(/^\s*[-*]\s+(.*)$/gim, '<li class="ai-li">$1</li>')

  // Tables: simple markdown table parsing
  const tableRegex = /((?:\|.+?\|\r?\n)+)/g
  text = text.replace(tableRegex, (tableBlock) => {
    const rows = tableBlock.trim().split('\n')
    if (rows.length < 2 || !rows[0]) return tableBlock
    const headers = rows[0].split('|').filter(c => c.trim()).map(c => `<th>${c.trim()}</th>`).join('')
    let bodyRows = ''
    for (let i = 2; i < rows.length; i++) {
      const row = rows[i]
      if (row) {
        const cells = row.split('|').filter(c => c.trim()).map(c => `<td>${c.trim()}</td>`).join('')
        if (cells) bodyRows += `<tr>${cells}</tr>`
      }
    }
    return `<div class="apple-table-wrap"><table class="apple-ai-table"><thead><tr>${headers}</tr></thead><tbody>${bodyRows}</tbody></table></div>`
  })

  // Paragraphs
  text = text.split('\n\n').map(p => {
    if (p.startsWith('<pre') || p.startsWith('<h') || p.startsWith('<div class="apple-table') || p.startsWith('<li')) {
      return p
    }
    return `<p class="ai-p">${p.replace(/\n/g, '<br/>')}</p>`
  }).join('')

  return text
}
