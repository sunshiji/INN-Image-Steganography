<template>
  <div class="decode-page">
    <el-card class="section-card">
      <template #header>
        <div class="card-header">
          <span>隐写解码</span>
          <el-tag type="primary">HiNet</el-tag>
        </div>
      </template>
      
      <el-row :gutter="20">
        <el-col :span="12">
          <div class="section-title">
            <span class="title-icon" style="background: #d1fae5; color: #10b981;">
              <el-icon><PictureFilled /></el-icon>
            </span>
            隐写图像 (Stego)
          </div>
          <el-upload
            class="image-uploader"
            drag
            :auto-upload="false"
            :show-file-list="false"
            :on-change="handleStegoChange"
            accept="image/*"
          >
            <div v-if="!stegoImage" class="upload-placeholder">
              <el-icon class="upload-icon"><Upload /></el-icon>
              <div class="upload-text">上传隐写图像</div>
              <div class="upload-hint">需要解码的图像</div>
            </div>
            <div v-else class="image-preview">
              <img :src="stegoImage" alt="隐写图像" />
            </div>
          </el-upload>
        </el-col>
        
        <el-col :span="12">
          <div class="section-title">
            <span class="title-icon" style="background: #fce7f3; color: #ec4899;">
              <el-icon><Key /></el-icon>
            </span>
            解码密钥 (Stego Key) - 可选
          </div>
          
          <el-form label-width="100px">
            <el-form-item label="密钥模式">
              <el-radio-group v-model="keyMode">
                <el-radio value="exact">精确解码（推荐）</el-radio>
                <el-radio value="approximate">近似解码</el-radio>
              </el-radio-group>
            </el-form-item>
            
            <el-form-item v-if="keyMode === 'exact'" label="输入密钥">
              <el-input
                v-model="stegoKeyInput"
                type="textarea"
                :rows="6"
                placeholder="请粘贴隐写编码时生成的 stego_key（Base64 格式）"
              />
              <div class="form-hint">
                精确解码需要隐写编码时生成的密钥，可实现无损恢复
              </div>
            </el-form-item>
            
            <el-form-item v-if="keyMode === 'approximate'">
              <el-alert
                title="近似解码模式"
                type="warning"
                :closable="false"
              >
                <template #default>
                  不提供密钥时将使用近似模式，恢复质量会有所下降。
                  建议保存编码时生成的 stego_key 以便精确解码。
                </template>
              </el-alert>
            </el-form-item>
          </el-form>
        </el-col>
      </el-row>
      
      <el-row class="mt-4">
        <el-col :span="24">
          <div class="action-bar">
            <el-button
              type="primary"
              size="large"
              :loading="decoding"
              :disabled="!stegoImage"
              @click="handleDecode"
              :icon="Search"
            >
              执行解码
            </el-button>
            <el-button
              size="large"
              @click="handleClear"
              :icon="Refresh"
            >
              清空
            </el-button>
          </div>
        </el-col>
      </el-row>
    </el-card>
    
    <el-card class="section-card mt-4" v-if="secretImage">
      <template #header>
        <div class="card-header">
          <span>解码结果</span>
          <el-tag :type="decodeMode === 'exact' ? 'success' : 'warning'">
            {{ decodeMode === 'exact' ? '精确模式' : '近似模式' }}
          </el-tag>
        </div>
      </template>
      
      <el-row :gutter="20">
        <el-col :span="12">
          <div class="result-image-wrapper">
            <div class="image-label">隐写图像</div>
            <el-image
              :src="stegoImage"
              fit="contain"
              class="result-image"
              :preview-src-list="[stegoImage]"
            />
          </div>
        </el-col>
        
        <el-col :span="12">
          <div class="result-image-wrapper">
            <div class="image-label secret-label">
              <el-icon><Check /></el-icon>
              恢复的秘密图像
            </div>
            <el-image
              :src="secretImage"
              fit="contain"
              class="result-image result-image-secret"
              :preview-src-list="[secretImage]"
            />
          </div>
        </el-col>
      </el-row>
      
      <el-row class="mt-4">
        <el-col :span="24">
          <div class="action-bar">
            <el-button type="success" @click="handleDownloadSecret" :icon="Download">
              下载恢复图像
            </el-button>
          </div>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { steganographyApi } from '@/api/steganography'

const stegoImage = ref<string>('')
const secretImage = ref<string>('')
const stegoFile = ref<File | null>(null)
const decoding = ref(false)
const keyMode = ref<string>('exact')
const stegoKeyInput = ref<string>('')
const decodeMode = ref<string>('')

const handleStegoChange = (file: any) => {
  const reader = new FileReader()
  reader.onload = (e) => {
    stegoImage.value = e.target?.result as string
  }
  reader.readAsDataURL(file.raw)
  stegoFile.value = file.raw
}

const handleClear = () => {
  stegoImage.value = ''
  secretImage.value = ''
  stegoFile.value = null
  stegoKeyInput.value = ''
  decodeMode.value = ''
}

const handleDecode = async () => {
  if (!stegoFile.value) {
    ElMessage.warning('请先上传隐写图像')
    return
  }
  
  const key = keyMode.value === 'exact' && stegoKeyInput.value.trim() 
    ? stegoKeyInput.value.trim() 
    : undefined
  
  if (keyMode.value === 'exact' && !key) {
    ElMessage.warning('精确模式需要输入密钥，或切换到近似模式')
    return
  }
  
  decoding.value = true
  try {
    const result = await steganographyApi.decode(stegoFile.value, key)
    
    secretImage.value = `data:image/png;base64,${result.secret_image}`
    decodeMode.value = result.mode
    
    ElMessage.success('解码成功！')
  } catch (error: any) {
    const message = error.response?.data?.detail || '解码失败'
    ElMessage.error(message)
  } finally {
    decoding.value = false
  }
}

const handleDownloadSecret = () => {
  if (!secretImage.value) return
  
  const link = document.createElement('a')
  link.href = secretImage.value
  link.download = `secret_recovered_${Date.now()}.png`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}
</script>

<style scoped>
.decode-page {
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

.form-hint {
  font-size: 12px;
  color: #6b7280;
  margin-top: 8px;
}

.result-image-wrapper {
  text-align: center;
}

.image-label {
  font-weight: 500;
  color: #374151;
  margin-bottom: 12px;
}

.secret-label {
  color: #10b981;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.result-image {
  width: 100%;
  height: 250px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}

.result-image-secret {
  border-color: #10b981;
  border-width: 2px;
}
</style>
