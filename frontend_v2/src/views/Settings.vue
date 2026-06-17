<template>
  <div class="settings-page">
    <el-card class="section-card">
      <template #header>
        <div class="card-header">
          <span>个人信息</span>
        </div>
      </template>
      
      <el-form
        :model="userForm"
        label-width="120px"
        class="settings-form"
      >
        <el-form-item label="用户名">
          <el-input v-model="userForm.username" disabled />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="userForm.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="userForm.fullName" placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleUpdateProfile" :icon="Check">
            保存修改
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
    
    <el-card class="section-card mt-4">
      <template #header>
        <div class="card-header">
          <span>修改密码</span>
        </div>
      </template>
      
      <el-form
        ref="passwordFormRef"
        :model="passwordForm"
        :rules="passwordRules"
        label-width="120px"
        class="settings-form"
      >
        <el-form-item label="当前密码" prop="oldPassword">
          <el-input
            v-model="passwordForm.oldPassword"
            type="password"
            show-password
            placeholder="请输入当前密码"
          />
        </el-form-item>
        <el-form-item label="新密码" prop="newPassword">
          <el-input
            v-model="passwordForm.newPassword"
            type="password"
            show-password
            placeholder="请输入新密码"
          />
          <div class="form-hint">密码长度至少 6 位</div>
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input
            v-model="passwordForm.confirmPassword"
            type="password"
            show-password
            placeholder="请再次输入新密码"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleChangePassword" :icon="Lock">
            修改密码
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
    
    <el-card class="section-card mt-4">
      <template #header>
        <div class="card-header">
          <span>系统设置</span>
        </div>
      </template>
      
      <el-form label-width="150px" class="settings-form">
        <el-form-item label="默认训练轮数">
          <el-input-number
            v-model="systemSettings.defaultEpochs"
            :min="1"
            :max="10000"
            :step="100"
          />
        </el-form-item>
        <el-form-item label="默认批次大小">
          <el-input-number
            v-model="systemSettings.defaultBatchSize"
            :min="1"
            :max="64"
          />
        </el-form-item>
        <el-form-item label="默认学习率">
          <el-select
            v-model="systemSettings.defaultLearningRate"
            style="width: 150px"
          >
            <el-option :value="0.001" label="1e-3" />
            <el-option :value="0.0001" label="1e-4" />
            <el-option :value="0.00001" label="1e-5" />
            <el-option :value="0.000001" label="1e-6" />
          </el-select>
        </el-form-item>
        <el-form-item label="图像最大尺寸">
          <el-select
            v-model="systemSettings.maxImageSize"
            style="width: 150px"
          >
            <el-option :value="512" label="512 px" />
            <el-option :value="1024" label="1024 px" />
            <el-option :value="2048" label="2048 px" />
          </el-select>
          <div class="form-hint">超过此尺寸的图像将自动缩放</div>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSaveSettings" :icon="Save">
            保存设置
          </el-button>
          <el-button @click="handleResetSettings" :icon="Refresh">
            恢复默认
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
    
    <el-card class="section-card mt-4">
      <template #header>
        <div class="card-header">
          <span>系统信息</span>
        </div>
      </template>
      
      <el-descriptions :column="2" border>
        <el-descriptions-item label="系统版本">
          <el-tag>2.0.0</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="前端框架">
          <el-tag type="info">Vue 3 + TypeScript</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="后端框架">
          <el-tag type="info">FastAPI</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="深度学习框架">
          <el-tag type="info">PyTorch</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="神经网络模型" :span="2">
          <el-tag type="primary">HiNet (Invertible Neural Network)</el-tag>
        </el-descriptions-item>
      </el-descriptions>
      
      <el-alert
        title="关于系统"
        type="info"
        :closable="false"
        class="mt-4"
      >
        <template #default>
          <p>本系统是一个基于可逆神经网络（Invertible Neural Network, INN）的图像加密和隐写系统。</p>
          <p>主要功能包括：</p>
          <ul class="feature-list">
            <li>Logistic 混沌映射加密/解密</li>
            <li>HiNet 可逆神经网络隐写编码/解码</li>
            <li>模型训练管理</li>
            <li>数据集管理</li>
            <li>模型权重管理</li>
          </ul>
          <p class="copyright">© 2026 INN Image Steganography System</p>
        </template>
      </el-alert>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed, onMounted } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const passwordFormRef = ref<FormInstance>()

const userForm = reactive({
  username: '',
  email: '',
  fullName: ''
})

const passwordForm = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})

const systemSettings = reactive({
  defaultEpochs: 1000,
  defaultBatchSize: 8,
  defaultLearningRate: 0.00001,
  maxImageSize: 1024
})

const validateConfirmPassword = (rule: any, value: string, callback: any) => {
  if (value !== passwordForm.newPassword) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const passwordRules: FormRules = {
  oldPassword: [
    { required: true, message: '请输入当前密码', trigger: 'blur' }
  ],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码长度至少 6 位', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ]
}

const handleUpdateProfile = () => {
  ElMessage.success('个人信息已更新')
}

const handleChangePassword = async () => {
  if (!passwordFormRef.value) return
  
  await passwordFormRef.value.validate(async (valid) => {
    if (!valid) return
    
    ElMessage.success('密码修改成功，请重新登录')
    
    passwordForm.oldPassword = ''
    passwordForm.newPassword = ''
    passwordForm.confirmPassword = ''
  })
}

const handleSaveSettings = () => {
  localStorage.setItem('inn_settings', JSON.stringify(systemSettings))
  ElMessage.success('系统设置已保存')
}

const handleResetSettings = () => {
  systemSettings.defaultEpochs = 1000
  systemSettings.defaultBatchSize = 8
  systemSettings.defaultLearningRate = 0.00001
  systemSettings.maxImageSize = 1024
  ElMessage.success('已恢复默认设置')
}

const loadSettings = () => {
  const saved = localStorage.getItem('inn_settings')
  if (saved) {
    try {
      const settings = JSON.parse(saved)
      Object.assign(systemSettings, settings)
    } catch {
      // ignore
    }
  }
}

onMounted(() => {
  if (userStore.user) {
    userForm.username = userStore.user.username
    userForm.email = userStore.user.email || ''
    userForm.fullName = userStore.user.fullName || ''
  }
  
  loadSettings()
})
</script>

<style scoped>
.settings-page {
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

.settings-form {
  max-width: 500px;
}

.form-hint {
  font-size: 12px;
  color: #6b7280;
  margin-top: 4px;
}

.feature-list {
  list-style: none;
  padding: 0;
  margin: 8px 0 0 0;
}

.feature-list li {
  margin-bottom: 4px;
  font-size: 13px;
}

.copyright {
  margin-top: 16px;
  font-size: 12px;
  color: #9ca3af;
}
</style>
