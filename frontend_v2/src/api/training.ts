import api from './index'

export interface TrainingJobInfo {
  id: number
  job_name: string
  description?: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'stopped'
  current_epoch: number
  total_epochs: number
  batch_size: number
  learning_rate: number
  best_psnr?: number
  best_ssim?: number
  best_loss?: number
  created_at: string
  started_at?: string
  completed_at?: string
}

export interface DatasetInfo {
  name: string
  path: string
  train_count: number
  val_count: number
}

export interface ModelInfo {
  name: string
  path: string
  size_bytes: number
  size_mb: number
  modified_at: string
}

export interface CurrentModelInfo {
  current_weights_path: string | null
  cached_models: string[]
  device: string | null
  weights_loaded: boolean
}

export const trainingApi = {
  async getStatus(): Promise<{ jobs: any[] }> {
    const response = await api.get('/training/status')
    return response.data
  },

  async getJobStatus(jobId: number): Promise<any> {
    const response = await api.get(`/training/status/${jobId}`)
    return response.data
  },

  async startTraining(params: {
    job_name: string
    epochs: number
    batch_size: number
    learning_rate: number
    val_freq: number
    save_freq: number
    dataset_path?: string
    pretrained_model_name?: string
    load_optimizer_state?: boolean
  }): Promise<TrainingJobInfo> {
    const response = await api.post('/training/start', params)
    return response.data
  },

  async stopTraining(jobId: number): Promise<void> {
    await api.post(`/training/stop/${jobId}`)
  },

  async listJobs(limit: number = 20): Promise<TrainingJobInfo[]> {
    const response = await api.get('/training/jobs', { params: { limit } })
    return response.data
  },

  async listDatasets(): Promise<{ datasets: DatasetInfo[] }> {
    const response = await api.get('/training/datasets')
    return response.data
  },

  async uploadDataset(
    name: string,
    files: File[],
    splitRatio: number = 0.8
  ): Promise<{ message: string; name: string; train_count: number; val_count: number }> {
    const formData = new FormData()
    formData.append('name', name)
    formData.append('split_ratio', splitRatio.toString())
    files.forEach((file) => formData.append('files', file))

    const response = await api.post('/training/datasets/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    return response.data
  },

  async deleteDataset(name: string): Promise<void> {
    await api.delete(`/training/datasets/${name}`)
  },

  async listModels(): Promise<{ models: ModelInfo[] }> {
    const response = await api.get('/training/models')
    return response.data
  },

  async listAvailableModels(): Promise<{ models: ModelInfo[] }> {
    const response = await api.get('/training/models/available')
    return response.data
  },

  async deleteModel(name: string): Promise<void> {
    await api.delete(`/training/models/${name}`)
  },

  async uploadModel(
    name: string,
    modelFile: File
  ): Promise<{ message: string; name: string; path: string; size_bytes: number; size_mb: number }> {
    const formData = new FormData()
    formData.append('name', name)
    formData.append('model_file', modelFile)

    const response = await api.post('/training/models/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    return response.data
  },

  async getCurrentModelInfo(): Promise<CurrentModelInfo> {
    const response = await api.get('/training/models/info/current')
    return response.data
  },

  async switchModel(modelName: string, forceReload: boolean = true): Promise<{
    message: string
    current_model: string
    device: string
    weights_loaded: boolean
  }> {
    const formData = new FormData()
    formData.append('model_name', modelName)
    formData.append('force_reload', forceReload ? 'true' : 'false')

    const response = await api.post('/training/models/switch', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    return response.data
  },

  async clearModelCache(): Promise<{ message: string }> {
    const response = await api.post('/training/models/cache/clear')
    return response.data
  }
}
