<template>
  <div class="training-page">
    <el-card class="section-card">
      <template #header>
        <div class="card-header">
          <span>模型训练</span>
          <el-tag type="info">HiNet</el-tag>
        </div>
      </template>
      
      <el-tabs v-model="activeTab">
        <el-tab-pane label="配置训练" name="config">
          <el-form
            ref="configFormRef"
            :model="trainConfig"
            :rules="trainRules"
            label-width="150px"
          >
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="任务名称" prop="job_name">
                  <el-input v-model="trainConfig.job_name" placeholder="输入训练任务名称" />
                </el-form-item>
                
                <el-form-item label="数据集" prop="dataset_path">
                  <el-select
                    v-model="trainConfig.dataset_path"
                    placeholder="选择数据集"
                    class="full-width"
                    @change="handleDatasetChange"
                  >
                    <el-option
                      v-for="ds in datasets"
                      :key="ds.name"
                      :label="`${ds.name} (训练: ${ds.train_count}, 验证: ${ds.val_count})`"
                      :value="ds.path"
                    />
                  </el-select>
                  <div class="form-hint">
                    如无可用数据集，请先在"数据集管理"页面上传
                  </div>
                </el-form-item>
                
                <el-form-item label="训练轮数">
                  <el-input-number
                    v-model="trainConfig.epochs"
                    :min="1"
                    :max="10000"
                    :step="100"
                    class="full-width"
                  />
                </el-form-item>
                
                <el-form-item label="批次大小">
                  <el-input-number
                    v-model="trainConfig.batch_size"
                    :min="1"
                    :max="64"
                    class="full-width"
                  />
                </el-form-item>
              </el-col>
              
              <el-col :span="12">
                <el-form-item label="学习率">
                  <el-select
                    v-model="trainConfig.learning_rate"
                    class="full-width"
                  >
                    <el-option :value="0.001" label="1e-3" />
                    <el-option :value="0.0001" label="1e-4" />
                    <el-option :value="0.00001" label="1e-5 (推荐)" />
                    <el-option :value="0.000001" label="1e-6" />
                  </el-select>
                </el-form-item>
                
                <el-form-item label="验证频率">
                  <el-input-number
                    v-model="trainConfig.val_freq"
                    :min="1"
                    :max="100"
                    class="full-width"
                  />
                  <div class="form-hint">每 N 轮进行一次验证</div>
                </el-form-item>
                
                <el-form-item label="保存频率">
                  <el-input-number
                    v-model="trainConfig.save_freq"
                    :min="1"
                    :max="100"
                    class="full-width"
                  />
                  <div class="form-hint">每 N 轮保存一次检查点</div>
                </el-form-item>
              </el-col>
            </el-row>
            
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="预训练模型">
                  <el-select
                    v-model="trainConfig.pretrained_model_name"
                    placeholder="选择预训练模型（可选）"
                    class="full-width"
                    clearable
                  >
                    <el-option label="不使用预训练模型" value="" />
                    <el-option
                      v-for="model in pretrainedModels"
                      :key="model.name"
                      :label="`${model.name} (${model.size_mb} MB)`"
                      :value="model.name"
                    />
                  </el-select>
                  <div class="form-hint">
                    选择已上传的模型权重继续训练，支持 HiNetcp 格式
                  </div>
                </el-form-item>
              </el-col>
              
              <el-col :span="12">
                <el-form-item label="加载优化器状态">
                  <el-switch
                    v-model="trainConfig.load_optimizer_state"
                    active-text="是"
                    inactive-text="否"
                  />
                  <div class="form-hint mt-2">
                    加载优化器状态可实现断点续训，恢复之前的训练进度
                  </div>
                </el-form-item>
              </el-col>
            </el-row>
            
            <el-form-item>
              <el-button
                type="primary"
                size="large"
                :loading="starting"
                :disabled="!trainConfig.dataset_path"
                @click="handleStartTraining"
              >
                <el-icon><Cpu /></el-icon>
                开始训练
              </el-button>
              <el-button size="large" @click="handleResetConfig">
                重置配置
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
        
        <el-tab-pane label="训练任务" name="jobs">
          <el-table :data="jobs" v-loading="loadingJobs" stripe>
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="job_name" label="任务名称" />
            <el-table-column prop="status" label="状态" width="120">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)">
                  {{ getStatusText(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="进度" width="200">
              <template #default="{ row }">
                <el-progress
                  :percentage="row.total_epochs ? (row.current_epoch / row.total_epochs) * 100 : 0"
                  :format="(p) => `${row.current_epoch}/${row.total_epochs}`"
                />
              </template>
            </el-table-column>
            <el-table-column prop="best_psnr" label="最佳 PSNR" width="120">
              <template #default="{ row }">
                {{ row.best_psnr ? `${row.best_psnr.toFixed(2)} dB` : '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="180">
              <template #default="{ row }">
                {{ formatTime(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button
                  v-if="row.status === 'running'"
                  type="danger"
                  size="small"
                  @click="handleStopJob(row.id)"
                >
                  停止
                </el-button>
                <span v-else>-</span>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>
    
    <el-card class="section-card mt-4" v-if="currentJob">
      <template #header>
        <div class="card-header">
          <span>训练监控 - {{ currentJob.job_name }}</span>
          <el-tag :type="getStatusType(currentJob.status)">
            {{ getStatusText(currentJob.status) }}
          </el-tag>
        </div>
      </template>
      
      <el-row :gutter="20">
        <el-col :span="6">
          <el-statistic title="当前轮数" :value="currentJob.current_epoch">
            <template #suffix>
              <span class="stat-unit">/ {{ currentJob.total_epochs }}</span>
            </template>
          </el-statistic>
        </el-col>
        <el-col :span="6">
          <el-statistic title="最佳 PSNR" :value="currentJob.best_psnr || 0" :precision="2">
            <template #suffix>
              <span class="stat-unit">dB</span>
            </template>
          </el-statistic>
        </el-col>
        <el-col :span="6">
          <el-statistic title="最佳 SSIM" :value="currentJob.best_ssim || 0" :precision="4" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="最佳 Loss" :value="currentJob.best_loss || 0" :precision="4" />
        </el-col>
      </el-row>
      
      <el-row :gutter="20" class="mt-4">
        <el-col :span="12">
          <div class="chart-placeholder">
            <div class="placeholder-text">
              <el-icon><LineChart /></el-icon>
              <p>Loss 曲线</p>
              <p class="hint">训练过程中可实时查看</p>
            </div>
          </div>
        </el-col>
        <el-col :span="12">
          <div class="chart-placeholder">
            <div class="placeholder-text">
              <el-icon><LineChart /></el-icon>
              <p>PSNR 曲线</p>
              <p class="hint">验证时记录</p>
            </div>
          </div>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { trainingApi, type DatasetInfo, type TrainingJobInfo, type ModelInfo } from '@/api/training'

const activeTab = ref<string>('config')
const configFormRef = ref<FormInstance>()
const starting = ref(false)
const loadingJobs = ref(false)

const datasets = ref<DatasetInfo[]>([])
const jobs = ref<TrainingJobInfo[]>([])
const currentJob = ref<TrainingJobInfo | null>(null)
const pretrainedModels = ref<ModelInfo[]>([])

const trainConfig = reactive({
  job_name: 'HiNet Training',
  epochs: 1000,
  batch_size: 8,
  learning_rate: 0.00001,
  val_freq: 20,
  save_freq: 20,
  dataset_path: '',
  pretrained_model_name: '',
  load_optimizer_state: false
})

const trainRules: FormRules = {
  job_name: [
    { required: true, message: '请输入任务名称', trigger: 'blur' }
  ],
  dataset_path: [
    { required: true, message: '请选择数据集', trigger: 'change' }
  ]
}

const getStatusType = (status: string) => {
  const types: Record<string, string> = {
    pending: 'info',
    running: 'warning',
    completed: 'success',
    failed: 'danger',
    stopped: 'info'
  }
  return types[status] || 'info'
}

const getStatusText = (status: string) => {
  const texts: Record<string, string> = {
    pending: '等待中',
    running: '训练中',
    completed: '已完成',
    failed: '失败',
    stopped: '已停止'
  }
  return texts[status] || status
}

const formatTime = (time: string) => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

const fetchDatasets = async () => {
  try {
    const result = await trainingApi.listDatasets()
    datasets.value = result.datasets || []
  } catch (error) {
    console.error('获取数据集列表失败:', error)
  }
}

const fetchJobs = async () => {
  loadingJobs.value = true
  try {
    jobs.value = await trainingApi.listJobs(20)
  } catch (error) {
    console.error('获取任务列表失败:', error)
  } finally {
    loadingJobs.value = false
  }
}

const fetchPretrainedModels = async () => {
  try {
    const result = await trainingApi.listModels()
    pretrainedModels.value = result.models || []
  } catch (error) {
    console.error('获取预训练模型列表失败:', error)
  }
}

const handleDatasetChange = () => {
  // 可以在这里添加数据集详情加载
}

const handleStartTraining = async () => {
  if (!configFormRef.value) return
  
  await configFormRef.value.validate(async (valid) => {
    if (!valid) return
    
    starting.value = true
    try {
      const trainingParams: any = {
        job_name: trainConfig.job_name,
        epochs: trainConfig.epochs,
        batch_size: trainConfig.batch_size,
        learning_rate: trainConfig.learning_rate,
        val_freq: trainConfig.val_freq,
        save_freq: trainConfig.save_freq,
        dataset_path: trainConfig.dataset_path
      }
      
      if (trainConfig.pretrained_model_name) {
        trainingParams.pretrained_model_name = trainConfig.pretrained_model_name
        trainingParams.load_optimizer_state = trainConfig.load_optimizer_state
      }
      
      const job = await trainingApi.startTraining(trainingParams)
      
      currentJob.value = job
      activeTab.value = 'jobs'
      ElMessage.success('训练任务已启动')
      
      setTimeout(fetchJobs, 1000)
    } catch (error: any) {
      const message = error.response?.data?.detail || '启动训练失败'
      ElMessage.error(message)
    } finally {
      starting.value = false
    }
  })
}

const handleStopJob = async (jobId: number) => {
  try {
    await trainingApi.stopTraining(jobId)
    ElMessage.success('已发送停止信号')
    fetchJobs()
  } catch (error: any) {
    const message = error.response?.data?.detail || '操作失败'
    ElMessage.error(message)
  }
}

const handleResetConfig = () => {
  trainConfig.job_name = 'HiNet Training'
  trainConfig.epochs = 1000
  trainConfig.batch_size = 8
  trainConfig.learning_rate = 0.00001
  trainConfig.val_freq = 20
  trainConfig.save_freq = 20
  trainConfig.dataset_path = ''
  trainConfig.pretrained_model_name = ''
  trainConfig.load_optimizer_state = false
}

onMounted(() => {
  fetchDatasets()
  fetchJobs()
  fetchPretrainedModels()
})
</script>

<style scoped>
.training-page {
  padding: 0;
}

.mt-4 {
  margin-top: 20px;
}

.section-card {
  border-radius: 12px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
}

.full-width {
  width: 100%;
}

.form-hint {
  font-size: 12px;
  color: #6b7280;
  margin-top: 4px;
}

.stat-unit {
  font-size: 14px;
  font-weight: normal;
  color: #6b7280;
}

.chart-placeholder {
  height: 280px;
  border: 1px dashed #d1d5db;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f9fafb;
}

.placeholder-text {
  text-align: center;
  color: #9ca3af;
}

.placeholder-text .el-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.placeholder-text p {
  margin: 0;
  font-size: 14px;
}

.placeholder-text .hint {
  font-size: 12px;
  color: #6b7280;
  margin-top: 4px;
}
</style>
