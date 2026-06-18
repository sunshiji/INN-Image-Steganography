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
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="执行时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              type="primary"
              @click="handleViewDetail(row)"
              :icon="View"
            >
              详情
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
    
    <el-dialog v-model="showDetailDialog" title="操作详情" width="600px">
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
        
        <el-divider>质量指标</el-divider>
        
        <el-row :gutter="20" v-if="hasMetrics">
          <el-col :span="12" v-if="currentDetail.psnr">
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
          <el-col :span="12" v-if="currentDetail.ssim">
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
        </el-row>
        
        <el-empty v-else description="无质量指标数据" />
        
        <el-divider>执行参数</el-divider>
        
        <el-code
          v-if="currentDetail.parameters"
          :code="currentDetail.parameters"
          language="json"
          :high-light="true"
        />
        <el-empty v-else description="无参数数据" />
        
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

const loading = ref(false)
const filterType = ref('')
const showDetailDialog = ref(false)
const currentDetail = ref<any>(null)

const historyList = ref<any[]>([])
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)

const getTaskTypeTag = (type: string) => {
  const tags: Record<string, string> = {
    encrypt: 'warning',
    decrypt: 'info',
    encode: 'primary',
    decode: 'success'
  }
  return tags[type] || 'info'
}

const getTaskTypeText = (type: string) => {
  const texts: Record<string, string> = {
    encrypt: '加密',
    decrypt: '解密',
    encode: '编码',
    decode: '解码'
  }
  return texts[type] || type
}

const formatTime = (time: string) => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

const hasMetrics = computed(() => {
  return currentDetail.value && (currentDetail.value.psnr || currentDetail.value.ssim)
})

const fetchHistory = async () => {
  loading.value = true
  try {
    // 模拟数据
    historyList.value = [
      {
        id: 1,
        task_type: 'encode',
        status: 'completed',
        psnr: 42.56,
        ssim: 0.9987,
        created_at: '2026-04-26T10:30:00Z',
        parameters: JSON.stringify({
          cover: 'lena.png',
          secret: 'secret.png',
          model: 'HiNet'
        }, null, 2)
      },
      {
        id: 2,
        task_type: 'encrypt',
        status: 'completed',
        psnr: null,
        ssim: null,
        created_at: '2026-04-26T10:20:00Z',
        parameters: JSON.stringify({
          r: 3.9991,
          x0: 0.37291,
          rounds: 2
        }, null, 2)
      },
      {
        id: 3,
        task_type: 'decode',
        status: 'completed',
        psnr: null,
        ssim: null,
        created_at: '2026-04-26T09:45:00Z',
        parameters: JSON.stringify({
          mode: 'exact',
          hasKey: true
        }, null, 2)
      }
    ]
    total.value = 3
  } catch (error) {
    console.error('获取历史记录失败:', error)
  } finally {
    loading.value = false
  }
}

const handleViewDetail = (row: any) => {
  currentDetail.value = row
  showDetailDialog.value = true
}

const handleSizeChange = (val: number) => {
  pageSize.value = val
  fetchHistory()
}

const handleCurrentChange = (val: number) => {
  currentPage.value = val
  fetchHistory()
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
</style>
