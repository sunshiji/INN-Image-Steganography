<template>
  <div class="decrypt-page">
    <el-card class="section-card">
      <template #header>
        <div class="card-header">
          <span>混沌解密</span>
          <el-tag type="info">Logistic 映射</el-tag>
        </div>
      </template>
      
      <el-row :gutter="20">
        <el-col :span="12">
          <div class="upload-section">
            <div class="section-title">加密图像</div>
            <el-upload
              class="image-uploader"
              drag
              :auto-upload="false"
              :show-file-list="false"
              :on-change="handleImageChange"
              accept="image/*"
            >
              <div v-if="!encryptedImage" class="upload-placeholder">
                <el-icon class="upload-icon"><Upload /></el-icon>
                <div class="upload-text">点击或拖拽上传加密图像</div>
              </div>
              <div v-else class="image-preview">
                <img :src="encryptedImage" alt="加密图像" />
              </div>
            </el-upload>
          </div>
          
          <div class="action-bar" v-if="encryptedImage">
            <el-button type="primary" @click="handleClear" :icon="Refresh">
              重新选择
            </el-button>
          </div>
        </el-col>
        
        <el-col :span="12">
          <div class="section-title">解密密钥</div>
          
          <el-tabs v-model="keyMode">
            <el-tab-pane label="使用密钥JSON" name="json">
              <el-form-item label="密钥JSON">
                <el-input
                  v-model="keyJson"
                  type="textarea"
                  :rows="8"
                  placeholder='请粘贴密钥，例如:
{
  "r": 3.9991,
  "x0": 0.37291,
  "n0": 500,
  "rounds": 2,
  "H": 512,
  "W": 512,
  "C": 3
}'
                />
              </el-form-item>
            </el-tab-pane>
            
            <el-tab-pane label="手动输入参数" name="manual">
              <el-form label-width="120px">
                <el-form-item label="控制参数 r">
                  <el-input-number
                    v-model="manualParams.r"
                    :min="3.57"
                    :max="4.0"
                    :step="0.0001"
                    :controls="false"
                  />
                </el-form-item>
                
                <el-form-item label="初始值 x₀">
                  <el-input-number
                    v-model="manualParams.x0"
                    :min="0.01"
                    :max="0.99"
                    :step="0.0001"
                    :controls="false"
                  />
                </el-form-item>
                
                <el-form-item label="预热步数">
                  <el-input-number
                    v-model="manualParams.n0"
                    :min="0"
                    :max="5000"
                  />
                </el-form-item>
                
                <el-form-item label="加密轮数">
                  <el-input-number
                    v-model="manualParams.rounds"
                    :min="1"
                    :max="10"
                  />
                </el-form-item>
                
                <el-form-item label="原始高度 H">
                  <el-input-number
                    v-model="manualParams.H"
                    :min="1"
                    :max="10000"
                  />
                </el-form-item>
                
                <el-form-item label="原始宽度 W">
                  <el-input-number
                    v-model="manualParams.W"
                    :min="1"
                    :max="10000"
                  />
                </el-form-item>
                
                <el-form-item label="通道数 C">
                  <el-radio-group v-model="manualParams.C">
                    <el-radio :value="1">灰度</el-radio>
                    <el-radio :value="3">彩色(RGB)</el-radio>
                  </el-radio-group>
                </el-form-item>
              </el-form>
            </el-tab-pane>
          </el-tabs>
          
          <div class="action-bar">
            <el-button
              type="primary"
              size="large"
              :loading="decrypting"
              :disabled="!encryptedImage"
              @click="handleDecrypt"
              :icon="Unlock"
            >
              执行解密
            </el-button>
          </div>
        </el-col>
      </el-row>
    </el-card>
    
    <el-card class="section-card mt-4" v-if="decryptedImage">
      <template #header>
        <div class="card-header">
          <span>解密结果</span>
        </div>
      </template>
      
      <el-row :gutter="20">
        <el-col :span="12">
          <div class="result-image-wrapper">
            <div class="image-label">加密图像</div>
            <el-image
              :src="encryptedImage"
              fit="contain"
              class="result-image"
              :preview-src-list="[encryptedImage]"
            />
          </div>
        </el-col>
        
        <el-col :span="12">
          <div class="result-image-wrapper">
            <div class="image-label">解密后图像</div>
            <el-image
              :src="decryptedImage"
              fit="contain"
              class="result-image"
              :preview-src-list="[decryptedImage]"
            />
          </div>
        </el-col>
      </el-row>
      
      <el-row class="mt-4">
        <el-col :span="24">
          <div class="action-bar">
            <el-button type="success" @click="handleDownload" :icon="Download">
              下载解密图像
            </el-button>
          </div>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { encryptApi } from '@/api/encrypt'

const encryptedImage = ref<string>('')
const decryptedImage = ref<string>('')
const encryptedFile = ref<File | null>(null)
const decrypting = ref(false)
const keyMode = ref<string>('json')

const keyJson = ref<string>('')
const manualParams = reactive({
  r: 3.9991,
  x0: 0.37291,
  n0: 500,
  rounds: 2,
  H: 512,
  W: 512,
  C: 3
})

const handleImageChange = (file: any) => {
  const reader = new FileReader()
  reader.onload = (e) => {
    encryptedImage.value = e.target?.result as string
  }
  reader.readAsDataURL(file.raw)
  encryptedFile.value = file.raw
}

const handleClear = () => {
  encryptedImage.value = ''
  decryptedImage.value = ''
  encryptedFile.value = null
}

const parseKeyJson = () => {
  if (!keyJson.value.trim()) {
    throw new Error('请输入密钥JSON')
  }
  
  try {
    return JSON.parse(keyJson.value)
  } catch {
    throw new Error('密钥JSON格式错误')
  }
}

const handleDecrypt = async () => {
  if (!encryptedFile.value) {
    ElMessage.warning('请先上传加密图像')
    return
  }
  
  let key: any
  
  try {
    if (keyMode.value === 'json') {
      key = parseKeyJson()
    } else {
      key = { ...manualParams }
    }
  } catch (error: any) {
    ElMessage.error(error.message)
    return
  }
  
  decrypting.value = true
  try {
    const result = await encryptApi.decrypt(encryptedFile.value, key)
    
    decryptedImage.value = `data:image/png;base64,${result.decrypted_image}`
    ElMessage.success('解密成功！')
  } catch (error: any) {
    const message = error.response?.data?.detail || '解密失败'
    ElMessage.error(message)
  } finally {
    decrypting.value = false
  }
}

const handleDownload = () => {
  if (!decryptedImage.value) return
  
  const link = document.createElement('a')
  link.href = decryptedImage.value
  link.download = `decrypted_${Date.now()}.png`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}
</script>

<style scoped>
.decrypt-page {
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
  font-weight: 500;
  color: #374151;
  margin-bottom: 12px;
}

.upload-section {
  margin-bottom: 20px;
}

.image-uploader {
  width: 100%;
  height: 200px;
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
  font-size: 14px;
  color: #6b7280;
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
</style>
