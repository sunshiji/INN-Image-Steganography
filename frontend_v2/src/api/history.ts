import api from './index'

export interface TaskDetail {
  id: number
  user_id: number | null
  task_type: string
  input_image_path: string | null
  cover_image_path: string | null
  secret_image_path: string | null
  output_image_path: string | null
  parameters: string | null
  psnr: number | null
  ssim: number | null
  entropy_original: number | null
  entropy_encrypted: number | null
  npcr: number | null
  uaci: number | null
  key_data: string | null
  status: string
  error_message: string | null
  created_at: string
  completed_at: string | null
}

export interface TaskListResponse {
  tasks: TaskDetail[]
  total: number
  page: number
  page_size: number
}

export const historyApi = {
  async getTaskList(
    taskType?: string,
    page: number = 1,
    pageSize: number = 10
  ): Promise<TaskListResponse> {
    const params: Record<string, any> = {
      page,
      page_size: pageSize
    }
    if (taskType) {
      params.task_type = taskType
    }
    
    const response = await api.get('/history', { params })
    return response.data
  },

  async getTaskDetail(taskId: number): Promise<TaskDetail> {
    const response = await api.get(`/history/${taskId}`)
    return response.data
  },

  async deleteTask(taskId: number): Promise<void> {
    await api.delete(`/history/${taskId}`)
  },

  getTaskImageUrl(taskId: number, imageType: string): string {
    const token = localStorage.getItem('token')
    const authHeader = token ? `Bearer ${token}` : ''
    return `/api/history/${taskId}/image/${imageType}`
  },

  getKeyDownloadUrl(taskId: number): string {
    return `/api/history/${taskId}/key/download`
  },

  async downloadKeyDirect(key: string, taskType: string = 'encrypt'): Promise<void> {
    const formData = new FormData()
    formData.append('key', key)
    formData.append('task_type', taskType)

    const response = await api.post(
      taskType === 'encode' ? '/steganography/key/download' : '/encrypt/key/download',
      formData,
      {
        responseType: 'blob',
        headers: { 'Content-Type': 'multipart/form-data' }
      }
    )

    const blob = new Blob([response.data], { 
      type: taskType === 'encode' ? 'text/plain' : 'application/json' 
    })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    const timestamp = Date.now()
    link.download = `${taskType}_key_${timestamp}.${taskType === 'encode' ? 'txt' : 'json'}`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  }
}
