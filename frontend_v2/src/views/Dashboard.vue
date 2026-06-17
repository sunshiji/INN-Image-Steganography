<template>
  <div class="dashboard">
    <el-row :gutter="20">
      <el-col :span="6">
        <el-card class="stat-card stat-card-1">
          <div class="stat-content">
            <div class="stat-icon">
              <el-icon><Lock /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.encryptCount }}</div>
              <div class="stat-label">加密次数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="stat-card stat-card-2">
          <div class="stat-content">
            <div class="stat-icon">
              <el-icon><PictureFilled /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.encodeCount }}</div>
              <div class="stat-label">隐写编码</div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="stat-card stat-card-3">
          <div class="stat-content">
            <div class="stat-icon">
              <el-icon><Cpu /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.modelCount }}</div>
              <div class="stat-label">已训练模型</div>
            </div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="stat-card stat-card-4">
          <div class="stat-content">
            <div class="stat-icon">
              <el-icon><FolderOpened /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.datasetCount }}</div>
              <div class="stat-label">数据集</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="mt-4">
      <el-col :span="12">
        <el-card class="section-card">
          <template #header>
            <div class="card-header">
              <span>快速操作</span>
            </div>
          </template>
          <el-row :gutter="16">
            <el-col :span="12">
              <router-link to="/encrypt" class="action-card action-encrypt">
                <div class="action-icon">
                  <el-icon><Lock /></el-icon>
                </div>
                <div class="action-text">
                  <div class="action-title">混沌加密</div>
                  <div class="action-desc">使用 Logistic 映射加密图像</div>
                </div>
              </router-link>
            </el-col>
            <el-col :span="12">
              <router-link to="/encode" class="action-card action-encode">
                <div class="action-icon">
                  <el-icon><PictureFilled /></el-icon>
                </div>
                <div class="action-text">
                  <div class="action-title">隐写编码</div>
                  <div class="action-desc">将秘密图像隐藏到载体中</div>
                </div>
              </router-link>
            </el-col>
            <el-col :span="12">
              <router-link to="/training" class="action-card action-training">
                <div class="action-icon">
                  <el-icon><Cpu /></el-icon>
                </div>
                <div class="action-text">
                  <div class="action-title">模型训练</div>
                  <div class="action-desc">训练自定义 HiNet 模型</div>
                </div>
              </router-link>
            </el-col>
            <el-col :span="12">
              <router-link to="/datasets" class="action-card action-dataset">
                <div class="action-icon">
                  <el-icon><Upload /></el-icon>
                </div>
                <div class="action-text">
                  <div class="action-title">上传数据集</div>
                  <div class="action-desc">管理训练数据集</div>
                </div>
              </router-link>
            </el-col>
          </el-row>
        </el-card>
      </el-col>
      
      <el-col :span="12">
        <el-card class="section-card">
          <template #header>
            <div class="card-header">
              <span>系统状态</span>
            </div>
          </template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="Python 版本">
              <el-tag>{{ systemStatus.pythonVersion || '检测中...' }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="PyTorch 版本">
              <el-tag type="primary">{{ systemStatus.pytorchVersion || '检测中...' }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="CUDA 可用">
              <el-tag :type="systemStatus.cudaAvailable ? 'success' : 'warning'">
                {{ systemStatus.cudaAvailable ? '是' : '否' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="模型状态">
              <el-tag :type="systemStatus.modelLoaded ? 'success' : 'info'">
                {{ systemStatus.modelLoaded ? '已加载' : '未加载' }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="mt-4">
      <el-col :span="24">
        <el-card class="section-card">
          <template #header>
            <div class="card-header">
              <span>系统介绍</span>
            </div>
          </template>
          <el-row :gutter="20">
            <el-col :span="8">
              <div class="feature-item">
                <div class="feature-icon feature-icon-1">
                  <el-icon><Lock /></el-icon>
                </div>
                <h3>双重加密保护</h3>
                <p>结合 Logistic 混沌加密和 HiNet 可逆神经网络隐写，提供双重安全保障</p>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="feature-item">
                <div class="feature-icon feature-icon-2">
                  <el-icon><MagicStick /></el-icon>
                </div>
                <h3>可逆神经网络</h3>
                <p>基于 HiNet 架构的可逆神经网络，支持精确无损恢复秘密图像</p>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="feature-item">
                <div class="feature-icon feature-icon-3">
                  <el-icon><Cpu /></el-icon>
                </div>
                <h3>自定义训练</h3>
                <p>支持上传自定义数据集，训练专属模型参数，适应不同场景需求</p>
              </div>
            </el-col>
          </el-row>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api'

const stats = ref({
  encryptCount: 0,
  encodeCount: 0,
  modelCount: 0,
  datasetCount: 0
})

const systemStatus = ref({
  pythonVersion: '',
  pytorchVersion: '',
  cudaAvailable: false,
  modelLoaded: false
})

const fetchSystemStatus = async () => {
  try {
    const response = await api.get('/status')
    systemStatus.value = {
      pythonVersion: response.data.python_version || '未知',
      pytorchVersion: response.data.pytorch_version || '未知',
      cudaAvailable: response.data.cuda_available || false,
      modelLoaded: response.data.model_loaded || false
    }
  } catch (error) {
    console.error('获取系统状态失败:', error)
  }
}

onMounted(() => {
  fetchSystemStatus()
})
</script>

<style scoped>
.dashboard {
  padding: 0;
}

.mt-4 {
  margin-top: 20px;
}

.stat-card {
  border-radius: 12px;
  border: none;
  overflow: hidden;
}

.stat-card-1 {
  background: linear-gradient(135deg, #f97316, #fb923c);
}

.stat-card-2 {
  background: linear-gradient(135deg, #3b82f6, #60a5fa);
}

.stat-card-3 {
  background: linear-gradient(135deg, #10b981, #34d399);
}

.stat-card-4 {
  background: linear-gradient(135deg, #8b5cf6, #a78bfa);
}

.stat-content {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px;
}

.stat-icon {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-icon .el-icon {
  font-size: 28px;
  color: #fff;
}

.stat-info {
  color: #fff;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
}

.stat-label {
  font-size: 14px;
  opacity: 0.9;
  margin-top: 4px;
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

.action-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-radius: 10px;
  margin-bottom: 12px;
  transition: all 0.3s;
  text-decoration: none;
}

.action-encrypt {
  background: linear-gradient(135deg, #fff7ed, #ffedd5);
  border: 1px solid #fed7aa;
}

.action-encrypt:hover {
  background: linear-gradient(135deg, #ffedd5, #fed7aa);
}

.action-encode {
  background: linear-gradient(135deg, #eff6ff, #dbeafe);
  border: 1px solid #bfdbfe;
}

.action-encode:hover {
  background: linear-gradient(135deg, #dbeafe, #bfdbfe);
}

.action-training {
  background: linear-gradient(135deg, #ecfdf5, #d1fae5);
  border: 1px solid #a7f3d0;
}

.action-training:hover {
  background: linear-gradient(135deg, #d1fae5, #a7f3d0);
}

.action-dataset {
  background: linear-gradient(135deg, #faf5ff, #f3e8ff);
  border: 1px solid #e9d5ff;
}

.action-dataset:hover {
  background: linear-gradient(135deg, #f3e8ff, #e9d5ff);
}

.action-icon {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.action-encrypt .action-icon {
  background: #f97316;
}

.action-encode .action-icon {
  background: #3b82f6;
}

.action-training .action-icon {
  background: #10b981;
}

.action-dataset .action-icon {
  background: #8b5cf6;
}

.action-icon .el-icon {
  font-size: 24px;
  color: #fff;
}

.action-title {
  font-size: 15px;
  font-weight: 600;
  color: #1f2937;
}

.action-desc {
  font-size: 12px;
  color: #6b7280;
  margin-top: 2px;
}

.feature-item {
  text-align: center;
  padding: 20px;
}

.feature-icon {
  width: 64px;
  height: 64px;
  margin: 0 auto 16px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.feature-icon-1 {
  background: linear-gradient(135deg, #fff7ed, #ffedd5);
}

.feature-icon-2 {
  background: linear-gradient(135deg, #eff6ff, #dbeafe);
}

.feature-icon-3 {
  background: linear-gradient(135deg, #ecfdf5, #d1fae5);
}

.feature-icon .el-icon {
  font-size: 32px;
}

.feature-icon-1 .el-icon {
  color: #f97316;
}

.feature-icon-2 .el-icon {
  color: #3b82f6;
}

.feature-icon-3 .el-icon {
  color: #10b981;
}

.feature-item h3 {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 8px;
}

.feature-item p {
  font-size: 14px;
  color: #6b7280;
  line-height: 1.6;
}
</style>
