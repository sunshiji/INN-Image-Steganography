<template>
  <div class="encode-page">
    <el-card class="section-card">
      <template #header>
        <div class="card-header">
          <span>隐写编码</span>
          <div class="header-tags">
            <el-tag v-if="currentModelInfo?.weights_loaded" type="success">
              已加载模型: {{ currentModelName }}
            </el-tag>
            <el-tag v-else type="info">
              使用默认模型
            </el-tag>
            <el-tag v-if="currentModelInfo?.device" type="primary">
              {{ currentModelInfo.device }}
            </el-tag>
          </div>
        </div>
      </template>
      
      <el-form label-width="120px" class="config-form">
        <el-form-item label="选择模型">
          <el-select
            v-model="selectedModel"
            placeholder="选择模型权重（可选）"
            style="width: 300px"
            @change="handleModelChange"
          >
            <el-option label="默认模型（随机初始化）" value="" />
            <el-option
              v-for="model in models"
              :key="model.name"
              :label="`${model.name} (${model.size_mb} MB)`"
              :value="model.name"
            />
          </el-select>
          <el-button
            type="primary"
            link
            @click="fetchModels"
            :icon="Refresh"
            style="margin-left: 12px"
          >
            刷新模型列表
          </el-button>
        </el-form-item>
      </el-form>
      
      <el-row :gutter="20">
        <el-col :span="12">
          <div class="section-title">
            <span class="title-icon" style="background: #dbeafe; color: #3b82f6;">
              <el-icon><Image /></el-icon>
            </span>
            载体图像 (Cover)
          </div>
          <el-upload
            class="image-uploader"
            drag
            :auto-upload="false"
            :show-file-list="false"
            :on-change="handleCoverChange"
            accept="image/*"
          >
            <div v-if="!coverImage" class="upload-placeholder">
              <el-icon class="upload-icon"><Upload /></el-icon>
              <div class="upload-text">上传载体图像</div>
              <div class="upload-hint">秘密图像将隐藏到此图像中</div>
            </div>
            <div v-else class="image-preview">
              <img :src="coverImage" alt="载体图像" />
            </div>
          </el-upload>
        </el-col>
        
        <el-col :span="12">
          <div class="section-title">
            <span class="title-icon" style="background: #fed7aa; color: #f97316;">
              <el-icon><Lock /></el-icon>
            </span>
            秘密图像 (Secret)
          </div>
          <el-upload
            class="image-uploader"
            drag
            :auto-upload="false"
            :show-file-list="false"
            :on-change="handleSecretChange"
            accept="image/*"
          >
            <div v-if="!secretImage" class="upload-placeholder">
              <el-icon class="upload-icon"><Upload /></el-icon>
              <div class="upload-text">上传秘密图像</div>
              <div class="upload-hint">需要隐藏的秘密内容</div>
            </div>
            <div v-else class="image-preview">
              <img :src="secretImage" alt="秘密图像" />
            </div>
          </el-upload>
        </el-col>
      </el-row>
      
      <el-row class="mt-4">
        <el-col :span="24">
          <div class="action-bar">
            <el-button
              type="primary"
              size="large"
              :loading="encoding"
              :disabled="!coverImage || !secretImage"
              @click="handleEncode"
              :icon="PictureFilled"
            >
              执行隐写编码
            </el-button>
            <el-button
              size="large"
              @click="handleClear"
              :icon="Refresh"
            >
              清空重选
            </el-button>
          </div>
        </el-col>
      </el-row>
    </el-card>
    
    <el-card class="section-card mt-4" v-if="stegoImage">
      <template #header>
        <div class="card-header">
          <span>编码结果</span>
        </div>
      </template>
      
      <el-row :gutter="20">
        <el-col :span="8">
          <div class="result-image-wrapper">
            <div class="image-label">载体图像</div>
            <el-image
              :src="coverImage"
              fit="contain"
              class="result-image"
              :preview-src-list="[coverImage]"
            />
          </div>
        </el-col>
        
        <el-col :span="8">
          <div class="result-image-wrapper">
            <div class="image-label">秘密图像</div>
            <el-image
              :src="secretImage"
              fit="contain"
              class="result-image"
              :preview-src-list="[secretImage]"
            />
          </div>
        </el-col>
        
        <el-col :span="8">
          <div class="result-image-wrapper">
            <div class="image-label stego-label">
              <el-icon><Check /></el-icon>
              隐写图像
            </div>
            <el-image
              :src="stegoImage"
              fit="contain"
              class="result-image result-image-stego"
              :preview-src-list="[stegoImage]"
            />
          </div>
        </el-col>
      </el-row>
      
      <el-row class="mt-4" v-if="recoveryImage">
        <el-col :span="12">
          <div class="result-image-wrapper">
            <div class="image-label">预恢复图像（验证用）</div>
            <el-image
              :src="recoveryImage"
              fit="contain"
              class="result-image"
              :preview-src-list="[recoveryImage]"
            />
            <div class="image-desc">
              使用 stego_key 可精确恢复此图像
            </div>
          </div>
        </el-col>
      </el-row>
    </el-card>
    
    <el-card class="section-card mt-4" v-if="metrics">
      <template #header>
        <div class="card-header">
          <span>质量指标</span>
        </div>
      </template>
      
      <el-row :gutter="20">
        <el-col :span="12">
          <el-statistic title="PSNR (峰值信噪比)" :value="metrics.psnr_cover_stego" :precision="2">
            <template #suffix>
              <span class="stat-unit">dB</span>
            </template>
          </el-statistic>
          <el-progress
            :percentage="Math.min((metrics.psnr_cover_stego / 60) * 100, 100)"
            :color="metrics.psnr_cover_stego >= 40 ? '#10b981' : '#f97316'"
            class="mt-2"
          />
          <div class="progress-desc">
            越高越好，40dB 以上表示视觉上几乎无差异
          </div>
        </el-col>
        
        <el-col :span="12">
          <el-statistic title="SSIM (结构相似度)" :value="metrics.ssim_cover_stego" :precision="4">
          </el-statistic>
          <el-progress
            :percentage="metrics.ssim_cover_stego * 100"
            :color="metrics.ssim_cover_stego >= 0.99 ? '#10b981' : '#f97316'"
            class="mt-2"
          />
          <div class="progress-desc">
            越接近 1.0 越好，0.99 以上表示结构高度相似
          </div>
        </el-col>
      </el-row>
    </el-card>
    
    <el-card class="section-card mt-4" v-if="stegoKey">
      <template #header>
        <div class="card-header">
          <span>解码密钥 (Stego Key)</span>
          <el-tag type="warning">重要 - 请妥善保存</el-tag>
        </div>
      </template>
      
      <el-alert
        title="此密钥包含隐写时生成的噪声张量 z，用于精确解码"
        type="warning"
        :closable="false"
        show-icon
      >
        <template #default>
          如果不提供此密钥，解码时将使用近似模式，恢复质量会下降。
        </template>
      </el-alert>
      
      <div class="key-actions mt-4">
        <el-button type="primary" @click="handleCopyKey" :icon="DocumentCopy">
          复制密钥 (Base64)
        </el-button>
        <el-button type="success" @click="handleDownloadStego" :icon="Download">
          下载隐写图像
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { steganographyApi } from '@/api/steganography'
import { trainingApi, type ModelInfo, type CurrentModelInfo } from '@/api/training'

const coverImage = ref<string>('')
const secretImage = ref<string>('')
const stegoImage = ref<string>('')
const recoveryImage = ref<string>('')
const coverFile = ref<File | null>(null)
const secretFile = ref<File | null>(null)
const encoding = ref(false)
const stegoKey = ref<string>('')

const models = ref<ModelInfo[]>([])
const selectedModel = ref<string>('')
const currentModelInfo = ref<CurrentModelInfo | null>(null)

const currentModelName = computed(() => {
  if (!currentModelInfo.value?.current_weights_path) return ''
  const path = currentModelInfo.value.current_weights_path
  const match = path.match(/[/\\]([^/\\]+)\.(pt|pth|ckpt)$/i)
  return match ? match[1] : path.split(/[/\\]/).pop() || ''
})

const fetchModels = async () => {
  try {
    const result = await trainingApi.listModels()
    models.value = result.models || []
  } catch (error) {
    console.error('获取模型列表失败:', error)
  }
}

const fetchCurrentModelInfo = async () => {
  try {
    currentModelInfo.value = await trainingApi.getCurrentModelInfo()
  } catch (error) {
    console.error('获取当前模型信息失败:', error)
  }
}

const handleModelChange = async (modelName: string) => {
  if (modelName) {
    try {
      await trainingApi.switchModel(modelName, true)
      ElMessage.success(`已切换到模型: ${modelName}`)
      fetchCurrentModelInfo()
    } catch (error: any) {
      const message = error.response?.data?.detail || '切换模型失败'
      ElMessage.error(message)
    }
  }
}

const metrics = ref<{
  psnr_cover_stego: number
  ssim_cover_stego: number
} | null>(null)

const handleCoverChange = (file: any) => {
  const reader = new FileReader()
  reader.onload = (e) => {
    coverImage.value = e.target?.result as string
  }
  reader.readAsDataURL(file.raw)
  coverFile.value = file.raw
}

const handleSecretChange = (file: any) => {
  const reader = new FileReader()
  reader.onload = (e) => {
    secretImage.value = e.target?.result as string
  }
  reader.readAsDataURL(file.raw)
  secretFile.value = file.raw
}

const handleClear = () => {
  coverImage.value = ''
  secretImage.value = ''
  stegoImage.value = ''
  recoveryImage.value = ''
  coverFile.value = null
  secretFile.value = null
  metrics.value = null
  stegoKey.value = ''
}

const handleEncode = async () => {
  if (!coverFile.value || !secretFile.value) {
    ElMessage.warning('请先上传载体图像和秘密图像')
    return
  }
  
  encoding.value = true
  try {
    const params: { modelName?: string; forceReload?: boolean } = {}
    if (selectedModel.value) {
      params.modelName = selectedModel.value
    }
    
    const result = await steganographyApi.encode(coverFile.value, secretFile.value, params)
    
    stegoImage.value = `data:image/png;base64,${result.stego_image}`
    recoveryImage.value = `data:image/png;base64,${result.recovery_image}`
    stegoKey.value = result.stego_key
    metrics.value = result.metrics
    
    ElMessage.success('隐写编码成功！')
  } catch (error: any) {
    const message = error.response?.data?.detail || '编码失败'
    ElMessage.error(message)
  } finally {
    encoding.value = false
  }
}

const handleCopyKey = () => {
  if (!stegoKey.value) return
  
  navigator.clipboard.writeText(stegoKey.value).then(() => {
    ElMessage.success('密钥已复制到剪贴板')
  }).catch(() => {
    ElMessage.error('复制失败')
  })
}

const handleDownloadStego = () => {
  if (!stegoImage.value) return
  
  const link = document.createElement('a')
  link.href = stegoImage.value
  link.download = `stego_${Date.now()}.png`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

onMounted(() => {
  fetchModels()
  fetchCurrentModelInfo()
})
</script>

<style scoped>
.encode-page {
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

.header-tags {
  display: flex;
  gap: 12px;
}

.config-form {
  margin-bottom: 20px;
  padding-bottom: 20px;
  border-bottom: 1px solid #e5e7eb;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 500;
  color: #374151;
  margin-bottom: 12px;
}

.title-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.image-uploader {
  width: 100%;
  height: 220px;
}

.image-uploader :deep(.el-upload-dragger) {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.upload-placeholder {
  text-align: center;
}

.upload-icon {
  font-size: 40px;
  color: #9ca3af;
  margin-bottom: 12px;
}

.upload-text {
  font-size: 15px;
  font-weight: 500;
  color: #374151;
  margin-bottom: 6px;
}

.upload-hint {
  font-size: 12px;
  color: #9ca3af;
}

.image-preview {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.image-preview img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.action-bar {
  display: flex;
  gap: 12px;
}

.result-image-wrapper {
  text-align: center;
}

.image-label {
  font-weight: 500;
  color: #374151;
  margin-bottom: 12px;
}

.stego-label {
  color: #10b981;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.result-image {
  width: 100%;
  height: 200px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}

.result-image-stego {
  border-color: #10b981;
  border-width: 2px;
}

.image-desc {
  font-size: 12px;
  color: #6b7280;
  margin-top: 8px;
}

.stat-unit {
  font-size: 14px;
  font-weight: normal;
  color: #6b7280;
}

.progress-desc {
  font-size: 12px;
  color: #6b7280;
  margin-top: 4px;
}

.key-actions {
  display: flex;
  gap: 12px;
}
</style>
