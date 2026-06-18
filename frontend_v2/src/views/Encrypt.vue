<template>
  <div class="encrypt-page">
    <el-card class="section-card">
      <template #header>
        <div class="card-header">
          <span>混沌加密</span>
          <el-tag type="info">Logistic 映射</el-tag>
        </div>
      </template>
      
      <el-row :gutter="20">
        <el-col :span="12">
          <el-upload
            class="image-uploader"
            drag
            :auto-upload="false"
            :show-file-list="false"
            :on-change="handleImageChange"
            accept="image/*"
          >
            <div v-if="!originalImage" class="upload-placeholder">
              <el-icon class="upload-icon"><Upload /></el-icon>
              <div class="upload-text">点击或拖拽上传图像</div>
              <div class="upload-hint">支持 JPG、PNG、BMP 等格式</div>
            </div>
            <div v-else class="image-preview">
              <img :src="originalImage" alt="原始图像" />
            </div>
          </el-upload>
          
          <div class="action-bar" v-if="originalImage">
            <el-button type="primary" @click="handleClear" :icon="Refresh">
              重新选择
            </el-button>
          </div>
        </el-col>
        
        <el-col :span="12">
          <el-form label-width="120px">
            <el-form-item label="控制参数 r">
              <el-slider
                v-model="params.r"
                :min="3.57"
                :max="4.0"
                :step="0.0001"
                :show-input="true"
              />
              <div class="form-hint">推荐值: 3.9991</div>
            </el-form-item>
            
            <el-form-item label="初始值 x₀">
              <el-slider
                v-model="params.x0"
                :min="0.01"
                :max="0.99"
                :step="0.0001"
                :show-input="true"
              />
              <div class="form-hint">推荐值: 0.37291</div>
            </el-form-item>
            
            <el-form-item label="预热步数">
              <el-input-number
                v-model="params.n0"
                :min="0"
                :max="5000"
                :step="100"
              />
              <div class="form-hint">推荐值: 500</div>
            </el-form-item>
            
            <el-form-item label="加密轮数">
              <el-input-number
                v-model="params.rounds"
                :min="1"
                :max="10"
              />
              <div class="form-hint">推荐值: 2</div>
            </el-form-item>
            
            <el-form-item>
              <el-button
                type="primary"
                size="large"
                :loading="encrypting"
                :disabled="!originalImage"
                @click="handleEncrypt"
                :icon="Lock"
              >
                执行加密
              </el-button>
              <el-button
                size="large"
                @click="resetParams"
                :icon="Refresh"
              >
                重置参数
              </el-button>
            </el-form-item>
          </el-form>
        </el-col>
      </el-row>
    </el-card>
    
    <el-card class="section-card mt-4" v-if="encryptedImage">
      <template #header>
        <div class="card-header">
          <span>加密结果</span>
        </div>
      </template>
      
      <el-row :gutter="20">
        <el-col :span="12">
          <div class="result-image-wrapper">
            <div class="image-label">原始图像</div>
            <el-image
              :src="originalImage"
              fit="contain"
              class="result-image"
              :preview-src-list="[originalImage]"
              :initial-index="0"
            />
          </div>
        </el-col>
        
        <el-col :span="12">
          <div class="result-image-wrapper">
            <div class="image-label">加密后图像</div>
            <el-image
              :src="encryptedImage"
              fit="contain"
              class="result-image"
              :preview-src-list="[encryptedImage]"
              :initial-index="0"
            />
          </div>
        </el-col>
      </el-row>
      
      <el-row :gutter="20" class="mt-4">
        <el-col :span="24">
          <div class="action-bar">
            <el-button type="success" @click="handleDownload" :icon="Download">
              下载加密图像
            </el-button>
            <el-button type="primary" @click="handleCopyKey" :icon="DocumentCopy">
              复制密钥
            </el-button>
            <el-button type="warning" @click="handleDownloadKey" :icon="Download">
              下载密钥文件
            </el-button>
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
        <el-col :span="6">
          <el-statistic title="原始信息熵" :value="metrics.entropy_original" :precision="4">
            <template #suffix>
              <span class="stat-unit">bits</span>
            </template>
          </el-statistic>
        </el-col>
        <el-col :span="6">
          <el-statistic title="加密后信息熵" :value="metrics.entropy_encrypted" :precision="4">
            <template #suffix>
              <span class="stat-unit">bits</span>
            </template>
          </el-statistic>
        </el-col>
        <el-col :span="6">
          <el-statistic title="NPCR" :value="metrics.npcr" :precision="2">
            <template #suffix>
              <span class="stat-unit">%</span>
            </template>
          </el-statistic>
        </el-col>
        <el-col :span="6">
          <el-statistic title="UACI" :value="metrics.uaci" :precision="2">
            <template #suffix>
              <span class="stat-unit">%</span>
            </template>
          </el-statistic>
        </el-col>
      </el-row>
      
      <el-alert
        title="指标说明"
        type="info"
        :closable="false"
        class="mt-4"
      >
        <template #default>
          <ul class="metric-info">
            <li><strong>信息熵：</strong>值越接近 8.0 表示加密效果越好</li>
            <li><strong>NPCR：</strong>像素变化率，理想值约 99.6%</li>
            <li><strong>UACI：</strong>平均变化强度，理想值约 33.4%</li>
          </ul>
        </template>
      </el-alert>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { encryptApi } from '@/api/encrypt'
import { historyApi } from '@/api/history'

const originalImage = ref<string>('')
const encryptedImage = ref<string>('')
const originalFile = ref<File | null>(null)
const encrypting = ref(false)
const metrics = ref<{
  entropy_original: number
  entropy_encrypted: number
  npcr: number
  uaci: number
} | null>(null)
const currentKey = ref<any>(null)

const params = reactive({
  r: 3.9991,
  x0: 0.37291,
  n0: 500,
  rounds: 2
})

const handleImageChange = (file: any) => {
  const reader = new FileReader()
  reader.onload = (e) => {
    originalImage.value = e.target?.result as string
  }
  reader.readAsDataURL(file.raw)
  originalFile.value = file.raw
}

const handleClear = () => {
  originalImage.value = ''
  encryptedImage.value = ''
  originalFile.value = null
  metrics.value = null
  currentKey.value = null
}

const resetParams = () => {
  params.r = 3.9991
  params.x0 = 0.37291
  params.n0 = 500
  params.rounds = 2
}

const handleEncrypt = async () => {
  if (!originalFile.value) {
    ElMessage.warning('请先上传图像')
    return
  }
  
  encrypting.value = true
  try {
    const result = await encryptApi.encrypt(
      originalFile.value,
      params.r,
      params.x0,
      params.n0,
      params.rounds
    )
    
    encryptedImage.value = `data:image/png;base64,${result.encrypted_image}`
    metrics.value = result.metrics
    currentKey.value = result.key
    
    ElMessage.success('加密成功！')
  } catch (error: any) {
    const message = error.response?.data?.detail || '加密失败'
    ElMessage.error(message)
  } finally {
    encrypting.value = false
  }
}

const handleDownload = () => {
  if (!encryptedImage.value) return
  
  const link = document.createElement('a')
  link.href = encryptedImage.value
  link.download = `encrypted_${Date.now()}.png`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

const handleCopyKey = () => {
  if (!currentKey.value) return
  
  const keyText = JSON.stringify(currentKey.value, null, 2)
  navigator.clipboard.writeText(keyText).then(() => {
    ElMessage.success('密钥已复制到剪贴板')
  }).catch(() => {
    ElMessage.error('复制失败，请手动复制')
  })
}

const handleDownloadKey = async () => {
  if (!currentKey.value) return
  
  try {
    const keyText = JSON.stringify(currentKey.value)
    await historyApi.downloadKeyDirect(keyText, 'encrypt')
    ElMessage.success('密钥文件下载成功')
  } catch (error: any) {
    const keyText = JSON.stringify(currentKey.value, null, 2)
    const blob = new Blob([keyText], { type: 'application/json' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `encrypt_key_${Date.now()}.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('密钥文件下载成功')
  }
}
</script>

<style scoped>
.encrypt-page {
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

.image-uploader {
  width: 100%;
  height: 300px;
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
  font-size: 48px;
  color: #9ca3af;
  margin-bottom: 16px;
}

.upload-text {
  font-size: 16px;
  font-weight: 500;
  color: #374151;
  margin-bottom: 8px;
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
  margin-top: 16px;
  display: flex;
  gap: 12px;
}

.form-hint {
  font-size: 12px;
  color: #9ca3af;
  margin-top: 4px;
}

.result-image-wrapper {
  text-align: center;
}

.image-label {
  font-weight: 500;
  color: #374151;
  margin-bottom: 12px;
}

.result-image {
  width: 100%;
  height: 250px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}

.stat-unit {
  font-size: 14px;
  font-weight: normal;
  color: #6b7280;
}

.metric-info {
  list-style: none;
  padding: 0;
  margin: 0;
  font-size: 13px;
}

.metric-info li {
  margin-bottom: 4px;
}
</style>
