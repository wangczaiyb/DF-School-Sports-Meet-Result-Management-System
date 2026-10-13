import axios from 'axios'

const api = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1', timeout: 15000 })
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('sports_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && localStorage.getItem('sports_token')) {
      localStorage.removeItem('sports_token')
      localStorage.removeItem('sports_user')
      if (!location.pathname.startsWith('/login')) location.href = '/login'
    }
    return Promise.reject(error)
  },
)

export const errorMessage = (error: any) => {
  const detail = error?.response?.data?.detail
  if (error?.response?.status === 404 && detail === 'Not Found') return '后台服务版本过旧，请联系系统负责人重启后台服务'
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    return [detail.message, ...(detail.errors || [])].filter(Boolean).join('；') || '操作失败，请核对输入内容'
  }
  return detail || error?.message || '操作失败，请稍后重试'
}
export default api
