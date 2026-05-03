<template>
  <div class="history-page">
    <el-card class="section-card">
      <template #header>
        <div class="card-header">
          <span>历史记录</span>
          <div class="header-actions">
            <el-select
              v-model="filterType"
              placeholder="选择类型"
              clearable
              style="width: 150px"
              @change="handleFilterChange"
            >
              <el-option label="全部" value="" />
              <el-option label="加密" value="encrypt" />
              <el-option label="解密" value="decrypt" />
              <el-option label="编码" value="encode" />
              <el-option label="解码" value="decode" />
            </el-select>
            <el-button @click="fetchHistory" :icon="Refresh">
              刷新
            </el-button>
          </div>
        </div>
      </template>
      
      <el-table
        :data="historyList"
        v-loading="loading"
        stripe
        empty-text="暂无历史记录"
      >
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="task_type" label="操作类型" width="120">
          <template #default="{ row }">
            <el-tag :type="getTaskTypeTag(row.task_type)">
              {{ getTaskTypeText(row.task_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'completed' ? 'success' : 'danger'">
              {{ row.status === 'completed' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="质量指标" width="200">
          <template #default="{ row }">
            <div class="metrics">
              <span v-if="row.psnr" class="metric-item">
                PSNR: <strong>{{ row.psnr.toFixed(2) }} dB</strong>
              </span>
              <span v-if="row.ssim" class="metric-item">
                SSIM: <strong>{{ row.ssim.toFixed(4) }}</strong>
              </span>
              <span v-if="row.npcr" class="metric-item">
                NPCR: <strong>{{ row.npcr.toFixed(2) }}%</strong>
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="执行时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              type="primary"
              @click="handleViewDetail(row)"
              :icon="View"
            >
              详情
            </el-button>
            <el-button
              size="small"
              type="danger"
              @click="handleDeleteTask(row)"
              :icon="Delete"
              :loading="deletingId === row.id"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50, 100]"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        class="mt-4"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </el-card>
    
    <el-dialog v-model="showDetailDialog" title="操作详情" width="800px">
      <div v-if="currentDetail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="操作类型">
            <el-tag :type="getTaskTypeTag(currentDetail.task_type)">
              {{ getTaskTypeText(currentDetail.task_type) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="currentDetail.status === 'completed' ? 'success' : 'danger'">
              {{ currentDetail.status === 'completed' ? '成功' : '失败' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="执行时间" :span="2">
            {{ formatTime(currentDetail.created_at) }}
          </el-descriptions-item>
        </el-descriptions>
        
        <el-divider>相关图像</el-divider>
        
        <el-row :gutter="20" v-if="hasImages">
          <el-col :span="8" v-if="currentDetail.input_image_path || isEncryptOrDecrypt">
            <div class="image-card">
              <div class="image-label">输入图像</div>
              <el-image
                :src="getImageUrl('input')"
                fit="contain"
                class="detail-image"
                :preview-src-list="[getImageUrl('input')]"
                :initial-index="0"
                placeholder="加载中..."
              >
                <template #error>
                  <div class="image-placeholder">
                    <el-icon :size="40"><Picture /></el-icon>
                    <span class="placeholder-text">图像不存在</span>
                  </div>
                </template>
              </el-image>
            </div>
          </el-col>
          <el-col :span="8" v-if="currentDetail.cover_image_path || isEncodeOrDecode">
            <div class="image-card">
              <div class="image-label">载体图像</div>
              <el-image
                :src="getImageUrl('cover')"
                fit="contain"
                class="detail-image"
                :preview-src-list="[getImageUrl('cover')]"
                :initial-index="0"
                placeholder="加载中..."
              >
                <template #error>
                  <div class="image-placeholder">
                    <el-icon :size="40"><Picture /></el-icon>
                    <span class="placeholder-text">图像不存在</span>
                  </div>
                </template>
              </el-image>
            </div>
          </el-col>
          <el-col :span="8" v-if="currentDetail.secret_image_path">
            <div class="image-card">
              <div class="image-label">秘密图像</div>
              <el-image
                :src="getImageUrl('secret')"
                fit="contain"
                class="detail-image"
                :preview-src-list="[getImageUrl('secret')]"
                :initial-index="0"
                placeholder="加载中..."
              >
                <template #error>
                  <div class="image-placeholder">
                    <el-icon :size="40"><Picture /></el-icon>
                    <span class="placeholder-text">图像不存在</span>
                  </div>
                </template>
              </el-image>
            </div>
          </el-col>
          <el-col :span="12" v-if="currentDetail.output_image_path">
            <div class="image-card">
              <div class="image-label output-label">
                <el-icon><Check /></el-icon>
                输出图像
              </div>
              <el-image
                :src="getImageUrl('output')"
                fit="contain"
                class="detail-image"
                :preview-src-list="[getImageUrl('output')]"
                :initial-index="0"
                placeholder="加载中..."
              >
                <template #error>
                  <div class="image-placeholder">
                    <el-icon :size="40"><Picture /></el-icon>
                    <span class="placeholder-text">图像不存在</span>
                  </div>
                </template>
              </el-image>
            </div>
          </el-col>
        </el-row>
        
        <el-empty v-else description="无图像数据" />
        
        <el-divider>质量指标</el-divider>
        
        <el-row :gutter="20" v-if="hasMetrics">
          <el-col :span="6" v-if="currentDetail.psnr">
            <el-card class="metric-card">
              <div class="metric-card-label">PSNR (峰值信噪比)</div>
              <div class="metric-card-value">
                {{ currentDetail.psnr.toFixed(2) }}
                <span class="metric-card-unit">dB</span>
              </div>
              <el-progress
                :percentage="Math.min((currentDetail.psnr / 60) * 100, 100)"
                :color="currentDetail.psnr >= 40 ? '#10b981' : '#f97316'"
              />
              <div class="metric-card-hint">
                越高越好，40dB 以上表示视觉上几乎无差异
              </div>
            </el-card>
          </el-col>
          <el-col :span="6" v-if="currentDetail.ssim">
            <el-card class="metric-card">
              <div class="metric-card-label">SSIM (结构相似度)</div>
              <div class="metric-card-value">
                {{ currentDetail.ssim.toFixed(4) }}
              </div>
              <el-progress
                :percentage="currentDetail.ssim * 100"
                :color="currentDetail.ssim >= 0.99 ? '#10b981' : '#f97316'"
              />
              <div class="metric-card-hint">
                越接近 1.0 越好，0.99 以上表示结构高度相似
              </div>
            </el-card>
          </el-col>
          <el-col :span="6" v-if="currentDetail.entropy_encrypted">
            <el-card class="metric-card">
              <div class="metric-card-label">加密后信息熵</div>
              <div class="metric-card-value">
                {{ currentDetail.entropy_encrypted.toFixed(4) }}
                <span class="metric-card-unit">bits</span>
              </div>
              <el-progress
                :percentage="(currentDetail.entropy_encrypted / 8) * 100"
                :color="currentDetail.entropy_encrypted >= 7.9 ? '#10b981' : '#f97316'"
              />
              <div class="metric-card-hint">
                越接近 8.0 表示加密效果越好
              </div>
            </el-card>
          </el-col>
          <el-col :span="6" v-if="currentDetail.npcr">
            <el-card class="metric-card">
              <div class="metric-card-label">NPCR (像素变化率)</div>
              <div class="metric-card-value">
                {{ currentDetail.npcr.toFixed(2) }}
                <span class="metric-card-unit">%</span>
              </div>
              <el-progress
                :percentage="(currentDetail.npcr / 99.6) * 100"
                :color="currentDetail.npcr >= 99 ? '#10b981' : '#f97316'"
              />
              <div class="metric-card-hint">
                理想值约 99.6%
              </div>
            </el-card>
          </el-col>
        </el-row>
        
        <el-empty v-else description="无质量指标数据" />
        
        <el-divider>执行参数</el-divider>
        
        <div v-if="currentDetail.parameters" class="code-block">
          <pre><code>{{ formatParameters(currentDetail.parameters) }}</code></pre>
        </div>
        <el-empty v-else description="无参数数据" />
        
        <el-divider v-if="currentDetail.key_data">密钥信息</el-divider>
        
        <div v-if="currentDetail.key_data" class="key-section">
          <el-alert
            title="此任务已保存密钥，可下载用于后续解密/解码"
            type="warning"
            :closable="false"
            show-icon
          />
          <div class="key-actions mt-4">
            <el-button type="primary" @click="handleDownloadKey" :icon="Download">
              下载密钥文件
            </el-button>
            <el-button type="info" @click="handleCopyKey" :icon="DocumentCopy">
              复制密钥 (不推荐用于大密钥)
            </el-button>
          </div>
        </div>
        
        <el-divider v-if="currentDetail.error_message">错误信息</el-divider>
        
        <el-alert
          v-if="currentDetail.error_message"
          title="执行失败"
          type="error"
          :closable="false"
        >
          <template #default>
            {{ currentDetail.error_message }}
          </template>
        </el-alert>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { historyApi, type TaskDetail } from '@/api/history'

const loading = ref(false)
const filterType = ref('')
const showDetailDialog = ref(false)
const currentDetail = ref<TaskDetail | null>(null)
const deletingId = ref<number | null>(null)

const imageUrls = ref<Record<string, string>>({})
const imageLoading = ref(false)

const historyList = ref<TaskDetail[]>([])
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)

const getTaskTypeTag = (type: string) => {
  const tags: Record<string, string> = {
    encrypt: 'warning',
    decrypt: 'info',
    encode: 'primary',
    decode: 'success',
    pipeline_encrypt_encode: 'danger',
    pipeline_decode_decrypt: ''
  }
  return tags[type] || 'info'
}

const getTaskTypeText = (type: string) => {
  const texts: Record<string, string> = {
    encrypt: '加密',
    decrypt: '解密',
    encode: '编码',
    decode: '解码',
    pipeline_encrypt_encode: '加密+编码',
    pipeline_decode_decrypt: '解码+解密'
  }
  return texts[type] || type
}

const formatTime = (time: string) => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

const formatParameters = (params: string) => {
  try {
    const parsed = JSON.parse(params)
    return JSON.stringify(parsed, null, 2)
  } catch {
    return params
  }
}

const hasMetrics = computed(() => {
  if (!currentDetail.value) return false
  return currentDetail.value.psnr || 
         currentDetail.value.ssim || 
         currentDetail.value.entropy_encrypted || 
         currentDetail.value.npcr
})

const hasImages = computed(() => {
  if (!currentDetail.value) return false
  return currentDetail.value.input_image_path ||
         currentDetail.value.cover_image_path ||
         currentDetail.value.secret_image_path ||
         currentDetail.value.output_image_path
})

const isEncryptOrDecrypt = computed(() => {
  if (!currentDetail.value) return false
  const type = currentDetail.value.task_type
  return type === 'encrypt' || type === 'decrypt'
})

const isEncodeOrDecode = computed(() => {
  if (!currentDetail.value) return false
  const type = currentDetail.value.task_type
  return type === 'encode' || type === 'decode' || 
         type === 'pipeline_encrypt_encode' || type === 'pipeline_decode_decrypt'
})

const getImageUrl = (imageType: string) => {
  if (!currentDetail.value) return ''
  const key = `${currentDetail.value.id}_${imageType}`
  return imageUrls.value[key] || ''
}

const loadImageWithAuth = async (imageType: string): Promise<string> => {
  if (!currentDetail.value) return ''
  
  const key = `${currentDetail.value.id}_${imageType}`
  if (imageUrls.value[key]) {
    return imageUrls.value[key]
  }
  
  const token = localStorage.getItem('token')
  const baseUrl = historyApi.getTaskImageUrl(currentDetail.value.id, imageType)
  
  try {
    const response = await fetch(baseUrl, {
      headers: token ? { 'Authorization': `Bearer ${token}` } : {}
    })
    
    if (!response.ok) {
      throw new Error('Failed to load image')
    }
    
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    imageUrls.value[key] = url
    return url
  } catch (error) {
    console.error('Failed to load image:', error)
    return ''
  }
}

const loadAllImages = async () => {
  if (!currentDetail.value) return
  
  imageLoading.value = true
  imageUrls.value = {}
  
  const imageTypes: string[] = []
  if (currentDetail.value.input_image_path) imageTypes.push('input')
  if (currentDetail.value.cover_image_path) imageTypes.push('cover')
  if (currentDetail.value.secret_image_path) imageTypes.push('secret')
  if (currentDetail.value.output_image_path) imageTypes.push('output')
  
  for (const type of imageTypes) {
    await loadImageWithAuth(type)
  }
  
  imageLoading.value = false
}

const fetchHistory = async () => {
  loading.value = true
  try {
    const result = await historyApi.getTaskList(
      filterType.value || undefined,
      currentPage.value,
      pageSize.value
    )
    historyList.value = result.tasks
    total.value = result.total
  } catch (error) {
    console.error('获取历史记录失败:', error)
    ElMessage.error('获取历史记录失败')
  } finally {
    loading.value = false
  }
}

const handleViewDetail = (row: TaskDetail) => {
  currentDetail.value = row
  showDetailDialog.value = true
  loadAllImages()
}

const handleDeleteTask = async (row: TaskDetail) => {
  try {
    await ElMessageBox.confirm(
      '确定要删除此任务记录吗？此操作不可恢复。',
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    deletingId.value = row.id
    await historyApi.deleteTask(row.id)
    
    ElMessage.success('删除成功')
    fetchHistory()
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('删除失败:', error)
      ElMessage.error('删除失败')
    }
  } finally {
    deletingId.value = null
  }
}

const handleFilterChange = () => {
  currentPage.value = 1
  fetchHistory()
}

const handleSizeChange = (val: number) => {
  pageSize.value = val
  currentPage.value = 1
  fetchHistory()
}

const handleCurrentChange = (val: number) => {
  currentPage.value = val
  fetchHistory()
}

const handleDownloadKey = () => {
  if (!currentDetail.value?.key_data) return
  
  const url = historyApi.getKeyDownloadUrl(currentDetail.value.id)
  const token = localStorage.getItem('token')
  
  fetch(url, {
    headers: token ? { 'Authorization': `Bearer ${token}` } : {}
  })
  .then(response => response.blob())
  .then(blob => {
    const downloadUrl = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = downloadUrl
    link.download = `${currentDetail.value!.task_type}_key_${currentDetail.value!.id}.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(downloadUrl)
    ElMessage.success('密钥文件下载成功')
  })
  .catch(error => {
    console.error('下载密钥失败:', error)
    ElMessage.error('下载密钥失败')
  })
}

const handleCopyKey = () => {
  if (!currentDetail.value?.key_data) return
  
  const keyData = currentDetail.value.key_data
  
  if (keyData.length > 10000) {
    ElMessage.warning('密钥较大，复制可能导致卡顿，建议使用下载方式')
  }
  
  navigator.clipboard.writeText(keyData).then(() => {
    ElMessage.success('密钥已复制到剪贴板')
  }).catch(() => {
    ElMessage.error('复制失败，请下载密钥文件')
  })
}

onMounted(() => {
  fetchHistory()
})
</script>

<style scoped>
.history-page {
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

.header-actions {
  display: flex;
  gap: 12px;
}

.metrics {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.metric-item {
  font-size: 12px;
  color: #6b7280;
}

.metric-card {
  text-align: center;
}

.metric-card-label {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 12px;
}

.metric-card-value {
  font-size: 28px;
  font-weight: 700;
  color: #1f2937;
}

.metric-card-unit {
  font-size: 14px;
  font-weight: normal;
  color: #6b7280;
}

.metric-card-hint {
  font-size: 12px;
  color: #9ca3af;
  margin-top: 8px;
}

.code-block {
  background-color: #1f2937;
  border-radius: 8px;
  padding: 16px;
  overflow-x: auto;
}

.code-block pre {
  margin: 0;
  padding: 0;
}

.code-block code {
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  color: #e5e7eb;
  white-space: pre;
}

.image-card {
  text-align: center;
}

.image-label {
  font-weight: 500;
  color: #374151;
  margin-bottom: 12px;
}

.output-label {
  color: #10b981;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.detail-image {
  width: 100%;
  height: 180px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}

.image-placeholder {
  width: 100%;
  height: 180px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background-color: #f3f4f6;
  border-radius: 8px;
  border: 1px dashed #d1d5db;
  color: #9ca3af;
}

.placeholder-text {
  font-size: 12px;
  margin-top: 8px;
}

.key-section {
  margin-top: 16px;
}

.key-actions {
  display: flex;
  gap: 12px;
}
</style>
