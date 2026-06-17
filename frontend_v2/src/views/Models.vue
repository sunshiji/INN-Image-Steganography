<template>
  <div class="models-page">
    <el-card class="section-card">
      <template #header>
        <div class="card-header">
          <span>模型管理</span>
          <div class="header-actions">
            <el-tag :type="activeModel ? 'success' : 'info'">
              {{ activeModel ? '已加载模型' : '使用默认模型' }}
            </el-tag>
          </div>
        </div>
      </template>
      
      <el-alert
        title="模型说明"
        type="info"
        :closable="false"
        class="mb-4"
      >
        <template #default>
          HiNet 模型支持两种模式：
          <br />1. <strong>默认模式：</strong>使用随机初始化的权重，无需训练即可使用（适合测试）
          <br />2. <strong>训练模式：</strong>使用您自己的数据集训练的模型，效果更佳
        </template>
      </el-alert>
      
      <el-table :data="models" v-loading="loading" stripe empty-text="暂无已训练模型">
        <el-table-column prop="name" label="模型名称" />
        <el-table-column prop="size_bytes" label="文件大小" width="120">
          <template #default="{ row }">
            {{ formatSize(row.size_bytes) }}
          </template>
        </el-table-column>
        <el-table-column prop="modified_at" label="修改时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.modified_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleDownload(row)" :icon="Download">
              下载
            </el-button>
            <el-button
              size="small"
              type="primary"
              :disabled="isActiveModel(row.name)"
              @click="handleSetActive(row)"
              :icon="Check"
            >
              {{ isActiveModel(row.name) ? '已激活' : '设为激活' }}
            </el-button>
            <el-button
              size="small"
              type="danger"
              @click="handleDelete(row)"
              :icon="Delete"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    
    <el-card class="section-card mt-4">
      <template #header>
        <div class="card-header">
          <span>上传模型权重</span>
        </div>
      </template>
      
      <el-upload
        class="upload-area"
        drag
        :auto-upload="false"
        :on-change="handleModelFileChange"
        :show-file-list="false"
        accept=".pt,.pth,.ckpt"
      >
        <div class="upload-placeholder">
          <el-icon class="upload-icon"><Upload /></el-icon>
          <div class="upload-text">拖拽模型文件到此处或点击上传</div>
          <div class="upload-hint">支持 .pt、.pth、.ckpt 格式的 PyTorch 权重文件</div>
        </div>
      </el-upload>
      
      <div class="selected-model" v-if="selectedModelFile">
        <div class="file-info">
          <el-icon><Document /></el-icon>
          <span class="filename">{{ selectedModelFile.name }}</span>
          <span class="filesize">{{ formatSize(selectedModelFile.size) }}</span>
        </div>
        <el-button
          type="primary"
          :loading="uploadingModel"
          @click="handleUploadModel"
          :icon="Upload"
        >
          上传并加载
        </el-button>
        <el-button @click="selectedModelFile = null" :icon="Close">
          取消
        </el-button>
      </div>
      
      <el-alert
        title="模型格式要求"
        type="warning"
        :closable="false"
        class="mt-4"
      >
        <template #default>
          <ul class="requirements">
            <li>必须是 PyTorch 保存的权重文件（.pt/.pth/.ckpt 格式）</li>
            <li>推荐使用本系统训练脚本生成的模型文件</li>
            <li>权重文件应包含 'net' 键的 state_dict</li>
            <li>示例：<code>torch.save({'net': net.state_dict(), 'opt': ...}, 'model.pt')</code></li>
          </ul>
        </template>
      </el-alert>
    </el-card>
    
    <el-card class="section-card mt-4">
      <template #header>
        <div class="card-header">
          <span>常用公开数据集</span>
        </div>
      </template>
      
      <el-row :gutter="20">
        <el-col :span="8">
          <el-card class="dataset-card">
            <div class="dataset-icon" style="background: #dbeafe;">
              <el-icon color="#3b82f6"><Photo /></el-icon>
            </div>
            <h4>DIV2K</h4>
            <p>高质量图像超分辨率数据集，包含 1000 张 2K 分辨率图像</p>
            <el-tag size="small" type="info">推荐</el-tag>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card class="dataset-card">
            <div class="dataset-icon" style="background: #fce7f3;">
              <el-icon color="#ec4899"><Images /></el-icon>
            </div>
            <h4>COCO</h4>
            <p>大规模目标检测数据集，包含超过 33 万张图像</p>
            <el-tag size="small" type="info">大规模</el-tag>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card class="dataset-card">
            <div class="dataset-icon" style="background: #d1fae5;">
              <el-icon color="#10b981"><PictureFilled /></el-icon>
            </div>
            <h4>ILSVRC1k</h4>
            <p>ImageNet 大规模视觉识别挑战赛数据集</p>
            <el-tag size="small" type="info">超大规模</el-tag>
          </el-card>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { trainingApi, type ModelInfo } from '@/api/training'

const loading = ref(false)
const uploadingModel = ref(false)
const models = ref<ModelInfo[]>([])
const selectedModelFile = ref<File | null>(null)
const activeModel = ref<string>('')

const fetchModels = async () => {
  loading.value = true
  try {
    const result = await trainingApi.listModels()
    models.value = result.models || []
  } catch (error) {
    console.error('获取模型列表失败:', error)
  } finally {
    loading.value = false
  }
}

const formatSize = (bytes: number) => {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
}

const formatTime = (time: string) => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

const isActiveModel = (name: string) => {
  return activeModel.value === name
}

const handleModelFileChange = (file: any) => {
  if (file.raw) {
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (!['pt', 'pth', 'ckpt'].includes(ext || '')) {
      ElMessage.warning('请上传 .pt、.pth 或 .ckpt 格式的模型文件')
      return
    }
    selectedModelFile.value = file.raw
  }
}

const handleUploadModel = async () => {
  if (!selectedModelFile.value) return
  
  uploadingModel.value = true
  try {
    ElMessage.success('模型上传功能需要后端支持，请使用训练模块训练模型')
    selectedModelFile.value = null
  } finally {
    uploadingModel.value = false
  }
}

const handleDownload = (model: ModelInfo) => {
  ElMessage.info('模型下载功能开发中')
}

const handleSetActive = async (model: ModelInfo) => {
  try {
    await ElMessageBox.confirm(
      `确定要将 "${model.name}" 设为当前激活模型吗？`,
      '提示',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'info'
      }
    )
    
    activeModel.value = model.name
    ElMessage.success('模型已激活')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败')
    }
  }
}

const handleDelete = async (model: ModelInfo) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除模型 "${model.name}" 吗？此操作不可恢复。`,
      '警告',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await trainingApi.deleteModel(model.name)
    ElMessage.success('删除成功')
    fetchModels()
  } catch (error: any) {
    if (error !== 'cancel') {
      const message = error.response?.data?.detail || '删除失败'
      ElMessage.error(message)
    }
  }
}

onMounted(() => {
  fetchModels()
})
</script>

<style scoped>
.models-page {
  padding: 0;
}

.mb-4 {
  margin-bottom: 16px;
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

.header-actions {
  display: flex;
  gap: 12px;
}

.upload-area {
  width: 100%;
}

.upload-area :deep(.el-upload-dragger) {
  padding: 40px;
}

.upload-placeholder {
  text-align: center;
}

.upload-icon {
  font-size: 48px;
  color: #9ca3af;
  margin-bottom: 16px;
}

.upload-text {
  font-size: 16px;
  color: #374151;
  margin-bottom: 8px;
}

.upload-hint {
  font-size: 12px;
  color: #9ca3af;
}

.selected-model {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 8px;
  margin-top: 16px;
}

.file-info {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
}

.filename {
  font-weight: 500;
  color: #065f46;
}

.filesize {
  font-size: 12px;
  color: #6b7280;
}

.requirements {
  list-style: none;
  padding: 0;
  margin: 0;
  font-size: 13px;
}

.requirements li {
  margin-bottom: 4px;
}

.dataset-card {
  cursor: pointer;
  transition: all 0.3s;
}

.dataset-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
}

.dataset-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;
}

.dataset-icon .el-icon {
  font-size: 24px;
}

.dataset-card h4 {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 8px 0;
}

.dataset-card p {
  font-size: 13px;
  color: #6b7280;
  margin: 0 0 12px 0;
  line-height: 1.5;
}
</style>
