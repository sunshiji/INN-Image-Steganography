<template>
  <div class="datasets-page">
    <el-card class="section-card">
      <template #header>
        <div class="card-header">
          <span>数据集管理</span>
          <el-button type="primary" @click="showUploadDialog = true" :icon="Upload">
            上传数据集
          </el-button>
        </div>
      </template>
      
      <el-table :data="datasets" v-loading="loading" stripe empty-text="暂无数据集">
        <el-table-column prop="name" label="数据集名称" width="200" />
        <el-table-column prop="path" label="路径" show-overflow-tooltip />
        <el-table-column prop="train_count" label="训练集数量" width="120" align="center" />
        <el-table-column prop="val_count" label="验证集数量" width="120" align="center" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleViewDataset(row)" :icon="View">
              查看
            </el-button>
            <el-button
              size="small"
              type="danger"
              @click="handleDeleteDataset(row)"
              :icon="Delete"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    
    <el-dialog v-model="showUploadDialog" title="上传数据集" width="600px">
      <el-form label-width="120px">
        <el-form-item label="数据集名称" required>
          <el-input
            v-model="uploadForm.name"
            placeholder="输入数据集名称，如 DIV2K"
          />
        </el-form-item>
        
        <el-form-item label="训练/验证比例">
          <el-slider
            v-model="uploadForm.splitRatio"
            :min="0.5"
            :max="0.95"
            :step="0.05"
            :show-input="true"
          />
          <div class="form-hint">
            将按此比例自动划分训练集和验证集
          </div>
        </el-form-item>
        
        <el-form-item label="选择图像" required>
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
            multiple
            :limit="500"
            accept="image/*"
            drag
          >
            <div class="upload-placeholder">
              <el-icon class="upload-icon"><Upload /></el-icon>
              <div class="upload-text">拖拽图像到此处或点击上传</div>
              <div class="upload-hint">支持 JPG、PNG、BMP 等格式</div>
            </div>
            <template #tip>
              <div class="el-upload__tip">
                已选择 {{ selectedFiles.length }} 个文件
              </div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
        <el-button
          type="primary"
          :loading="uploading"
          :disabled="!uploadForm.name || selectedFiles.length === 0"
          @click="handleUpload"
        >
          开始上传
        </el-button>
      </template>
    </el-dialog>
    
    <el-dialog v-model="showDetailDialog" title="数据集详情" width="800px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="数据集名称">
          {{ currentDataset?.name }}
        </el-descriptions-item>
        <el-descriptions-item label="存储路径">
          {{ currentDataset?.path }}
        </el-descriptions-item>
        <el-descriptions-item label="训练集数量">
          <el-tag type="primary">{{ currentDataset?.train_count }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="验证集数量">
          <el-tag type="info">{{ currentDataset?.val_count }}</el-tag>
        </el-descriptions-item>
      </el-descriptions>
      
      <el-alert
        title="训练建议"
        type="info"
        :closable="false"
        class="mt-4"
      >
        <template #default>
          <ul class="recommendations">
            <li>推荐数据集大小：训练集 800 张以上，验证集 100 张以上</li>
            <li>推荐图像尺寸：至少 256×256 像素</li>
            <li>推荐图像格式：PNG 或 JPG</li>
            <li>常用公开数据集：DIV2K、COCO、ILSVRC1k 等</li>
          </ul>
        </template>
      </el-alert>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type UploadFile, type UploadInstance } from 'element-plus'
import { trainingApi, type DatasetInfo } from '@/api/training'

const loading = ref(false)
const uploading = ref(false)
const showUploadDialog = ref(false)
const showDetailDialog = ref(false)
const datasets = ref<DatasetInfo[]>([])
const currentDataset = ref<DatasetInfo | null>(null)
const selectedFiles = ref<File[]>([])

const uploadRef = ref<UploadInstance>()
const uploadForm = reactive({
  name: '',
  splitRatio: 0.8
})

const fetchDatasets = async () => {
  loading.value = true
  try {
    const result = await trainingApi.listDatasets()
    datasets.value = result.datasets || []
  } catch (error) {
    ElMessage.error('获取数据集列表失败')
  } finally {
    loading.value = false
  }
}

const handleFileChange = (file: UploadFile) => {
  if (file.raw) {
    selectedFiles.value.push(file.raw)
  }
}

const handleFileRemove = (file: UploadFile) => {
  const index = selectedFiles.value.findIndex(f => f.name === file.name)
  if (index > -1) {
    selectedFiles.value.splice(index, 1)
  }
}

const handleUpload = async () => {
  if (!uploadForm.name.trim()) {
    ElMessage.warning('请输入数据集名称')
    return
  }
  
  if (selectedFiles.value.length === 0) {
    ElMessage.warning('请选择至少一个图像文件')
    return
  }
  
  uploading.value = true
  try {
    const result = await trainingApi.uploadDataset(
      uploadForm.name,
      selectedFiles.value,
      uploadForm.splitRatio
    )
    
    ElMessage.success(`上传成功！训练集 ${result.train_count} 张，验证集 ${result.val_count} 张`)
    showUploadDialog.value = false
    fetchDatasets()
  } catch (error: any) {
    const message = error.response?.data?.detail || '上传失败'
    ElMessage.error(message)
  } finally {
    uploading.value = false
  }
}

const handleViewDataset = (dataset: DatasetInfo) => {
  currentDataset.value = dataset
  showDetailDialog.value = true
}

const handleDeleteDataset = async (dataset: DatasetInfo) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除数据集 "${dataset.name}" 吗？此操作不可恢复。`,
      '警告',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await trainingApi.deleteDataset(dataset.name)
    ElMessage.success('删除成功')
    fetchDatasets()
  } catch (error: any) {
    if (error !== 'cancel') {
      const message = error.response?.data?.detail || '删除失败'
      ElMessage.error(message)
    }
  }
}

onMounted(() => {
  fetchDatasets()
})
</script>

<style scoped>
.datasets-page {
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

.upload-placeholder {
  text-align: center;
  padding: 40px;
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

.form-hint {
  font-size: 12px;
  color: #6b7280;
  margin-top: 4px;
}

.recommendations {
  list-style: none;
  padding: 0;
  margin: 0;
  font-size: 13px;
}

.recommendations li {
  margin-bottom: 4px;
}
</style>
