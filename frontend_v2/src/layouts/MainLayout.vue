<template>
  <el-container class="main-container">
    <el-aside :width="sidebarCollapsed ? '64px' : '220px'" class="sidebar">
      <div class="logo" @click="$router.push('/dashboard')">
        <el-icon><CircleCloseFilled /></el-icon>
        <span v-if="!sidebarCollapsed" class="logo-text">INN 隐写系统</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        :collapse="sidebarCollapsed"
        :collapse-transition="false"
        router
        class="sidebar-menu"
      >
        <el-menu-item index="/dashboard">
          <el-icon><HomeFilled /></el-icon>
          <template #title>首页</template>
        </el-menu-item>
        
        <el-sub-menu index="encrypt-group">
          <template #title>
            <el-icon><Lock /></el-icon>
            <span>混沌加密</span>
          </template>
          <el-menu-item index="/encrypt">加密</el-menu-item>
          <el-menu-item index="/decrypt">解密</el-menu-item>
        </el-sub-menu>
        
        <el-sub-menu index="stego-group">
          <template #title>
            <el-icon><PictureFilled /></el-icon>
            <span>图像隐写</span>
          </template>
          <el-menu-item index="/encode">编码</el-menu-item>
          <el-menu-item index="/decode">解码</el-menu-item>
        </el-sub-menu>
        
        <el-menu-item index="/training">
          <el-icon><Cpu /></el-icon>
          <template #title>模型训练</template>
        </el-menu-item>
        
        <el-menu-item index="/datasets">
          <el-icon><FolderOpened /></el-icon>
          <template #title>数据集</template>
        </el-menu-item>
        
        <el-menu-item index="/models">
          <el-icon><Box /></el-icon>
          <template #title>模型管理</template>
        </el-menu-item>
        
        <el-menu-item index="/history">
          <el-icon><Clock /></el-icon>
          <template #title>历史记录</template>
        </el-menu-item>
        
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <template #title>系统设置</template>
        </el-menu-item>
      </el-menu>
    </el-aside>
    
    <el-container>
      <el-header class="header">
        <div class="header-left">
          <el-icon class="toggle-btn" @click="toggleSidebar">
            <Fold v-if="!sidebarCollapsed" />
            <Expand v-else />
          </el-icon>
          <span class="page-title">{{ currentPageTitle }}</span>
        </div>
        <div class="header-right">
          <el-dropdown @command="handleCommand">
            <div class="user-info">
              <el-avatar :size="32" class="user-avatar">
                <el-icon><UserFilled /></el-icon>
              </el-avatar>
              <span class="username">{{ userStore.user?.username }}</span>
              <el-icon><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">个人信息</el-dropdown-item>
                <el-dropdown-item command="settings">设置</el-dropdown-item>
                <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useAppStore } from '@/stores/app'
import { ElMessage, ElMessageBox } from 'element-plus'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const appStore = useAppStore()

const sidebarCollapsed = computed(() => appStore.sidebarCollapsed)
const toggleSidebar = () => appStore.toggleSidebar()

const activeMenu = computed(() => route.path)

const currentPageTitle = computed(() => {
  const title = route.meta.title as string
  return title || 'INN 图像隐写系统'
})

const handleCommand = async (command: string) => {
  switch (command) {
    case 'profile':
      router.push('/settings')
      break
    case 'settings':
      router.push('/settings')
      break
    case 'logout':
      try {
        await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        })
        await userStore.logout()
        router.push('/login')
        ElMessage.success('已退出登录')
      } catch {
        // 用户取消
      }
      break
  }
}
</script>

<style scoped>
.main-container {
  height: 100vh;
}

.sidebar {
  background-color: #1f2937;
  transition: width 0.3s ease;
  display: flex;
  flex-direction: column;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  cursor: pointer;
  border-bottom: 1px solid #374151;
}

.logo .el-icon {
  color: #f97316;
  font-size: 28px;
}

.logo-text {
  color: #fff;
  font-size: 16px;
  font-weight: bold;
}

.sidebar-menu {
  border: none;
  background-color: #1f2937;
  flex: 1;
}

.sidebar-menu :deep(.el-menu-item),
.sidebar-menu :deep(.el-sub-menu__title) {
  color: #9ca3af;
}

.sidebar-menu :deep(.el-menu-item:hover),
.sidebar-menu :deep(.el-sub-menu__title:hover) {
  color: #fff;
  background-color: #374151;
}

.sidebar-menu :deep(.el-menu-item.is-active) {
  color: #f97316;
  background-color: rgba(249, 115, 22, 0.1);
}

.header {
  background-color: #fff;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.toggle-btn {
  font-size: 20px;
  cursor: pointer;
  color: #6b7280;
  transition: color 0.3s;
}

.toggle-btn:hover {
  color: #f97316;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
}

.header-right {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}

.user-avatar {
  background-color: #f97316;
}

.username {
  font-size: 14px;
  color: #374151;
}

.main-content {
  background-color: #f3f4f6;
  padding: 20px;
  overflow-y: auto;
}
</style>
