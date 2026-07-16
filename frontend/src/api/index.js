import axios from 'axios'

export const API_BASE_URL = '/api'

export const buildApiUrl = (path) => {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${API_BASE_URL}${normalizedPath}`
}

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  },
)

// 响应拦截器
apiClient.interceptors.response.use(
  (response) => {
    return response
  },
  (error) => {
    if (error.response?.status === 401) {
      // 未授权，清除本地存储的token
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

export default apiClient

// 导出用户相关API
export const userApi = {
  // 登录API需要使用表单格式参数
  login: (data) => {
    const params = new URLSearchParams()
    params.append('user_name', data.user_name)
    params.append('password', data.password)
    return apiClient.post('/v1/user/login', params, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    })
  },
  logout: () => apiClient.post('/v1/user/logout'),
  register: (data) => apiClient.post('/v1/user/register', data),
  // 获取用户信息
  getUserInfo: (id) => apiClient.get(`/v1/user/${id}`),
}
