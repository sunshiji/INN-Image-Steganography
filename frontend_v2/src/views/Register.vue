<template>
  <div class="register-container">
    <div class="register-box">
      <div class="register-header">
        <div class="logo">
          <el-icon><CircleCloseFilled /></el-icon>
        </div>
        <h1>用户注册</h1>
        <p class="subtitle">创建 INN 图像隐写系统账号</p>
      </div>
      
      <el-form
        ref="registerFormRef"
        :model="registerForm"
        :rules="registerRules"
        class="register-form"
        label-position="top"
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="registerForm.username"
            placeholder="请输入用户名（2-50 个字符）"
            size="large"
          />
        </el-form-item>
        
        <el-form-item label="邮箱（可选）" prop="email">
          <el-input
            v-model="registerForm.email"
            placeholder="请输入邮箱地址"
            size="large"
          />
        </el-form-item>
        
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="registerForm.password"
            type="password"
            placeholder="请输入密码（至少 6 个字符）"
            size="large"
            show-password
          />
        </el-form-item>
        
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input
            v-model="registerForm.confirmPassword"
            type="password"
            placeholder="请再次输入密码"
            size="large"
            show-password
          />
        </el-form-item>
        
        <el-form-item>
          <el-button
            type="primary"
            size="large"
            class="register-btn"
            :loading="loading"
            @click="handleRegister"
          >
            注 册
          </el-button>
        </el-form-item>
      </el-form>
      
      <div class="register-footer">
        <p>
          已有账号？
          <router-link to="/login" class="link">立即登录</router-link>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'

const router = useRouter()
const userStore = useUserStore()

const registerFormRef = ref<FormInstance>()
const loading = ref(false)

const registerForm = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: ''
})

const validateConfirmPassword = (rule: any, value: string, callback: any) => {
  if (value !== registerForm.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const registerRules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 50, message: '用户名长度为 2-50 个字符', trigger: 'blur' }
  ],
  email: [
    { type: 'email', message: '请输入正确的邮箱地址', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ]
}

const handleRegister = async () => {
  if (!registerFormRef.value) return
  
  await registerFormRef.value.validate(async (valid) => {
    if (!valid) return
    
    loading.value = true
    try {
      await userStore.register(
        registerForm.username,
        registerForm.password,
        registerForm.email || undefined
      )
      
      ElMessage.success('注册成功，请登录')
      router.push('/login')
    } catch (error: any) {
      const message = error.response?.data?.detail || '注册失败'
      ElMessage.error(message)
    } finally {
      loading.value = false
    }
  })
}
</script>

<style scoped>
.register-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #fff7ed 0%, #fefce8 50%, #ffedd5 100%);
}

.register-box {
  width: 420px;
  padding: 40px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.1);
}

.register-header {
  text-align: center;
  margin-bottom: 32px;
}

.logo {
  width: 56px;
  height: 56px;
  margin: 0 auto 12px;
  background: linear-gradient(135deg, #f97316, #fb923c);
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo .el-icon {
  font-size: 32px;
  color: #fff;
}

.register-header h1 {
  font-size: 22px;
  font-weight: 700;
  color: #1f2937;
  margin-bottom: 6px;
}

.subtitle {
  font-size: 14px;
  color: #6b7280;
}

.register-form :deep(.el-form-item__label) {
  font-weight: 500;
  color: #374151;
}

.register-btn {
  width: 100%;
  background: linear-gradient(135deg, #f97316, #fb923c);
  border: none;
}

.register-btn:hover {
  background: linear-gradient(135deg, #ea580c, #f97316);
}

.register-footer {
  text-align: center;
}

.register-footer p {
  font-size: 14px;
  color: #6b7280;
}

.link {
  color: #f97316;
  font-weight: 500;
}

.link:hover {
  text-decoration: underline;
}
</style>
