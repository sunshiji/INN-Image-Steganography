import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/Login.vue'),
      meta: { title: '登录', requiresAuth: false }
    },
    {
      path: '/register',
      name: 'Register',
      component: () => import('@/views/Register.vue'),
      meta: { title: '注册', requiresAuth: false }
    },
    {
      path: '/',
      component: () => import('@/layouts/MainLayout.vue'),
      redirect: '/dashboard',
      children: [
        {
          path: 'dashboard',
          name: 'Dashboard',
          component: () => import('@/views/Dashboard.vue'),
          meta: { title: '首页', icon: 'HomeFilled' }
        },
        {
          path: 'encrypt',
          name: 'Encrypt',
          component: () => import('@/views/Encrypt.vue'),
          meta: { title: '混沌加密', icon: 'Lock' }
        },
        {
          path: 'decrypt',
          name: 'Decrypt',
          component: () => import('@/views/Decrypt.vue'),
          meta: { title: '混沌解密', icon: 'Unlock' }
        },
        {
          path: 'encode',
          name: 'Encode',
          component: () => import('@/views/Encode.vue'),
          meta: { title: '隐写编码', icon: 'PictureFilled' }
        },
        {
          path: 'decode',
          name: 'Decode',
          component: () => import('@/views/Decode.vue'),
          meta: { title: '隐写解码', icon: 'Search' }
        },
        {
          path: 'training',
          name: 'Training',
          component: () => import('@/views/Training.vue'),
          meta: { title: '模型训练', icon: 'Cpu' }
        },
        {
          path: 'datasets',
          name: 'Datasets',
          component: () => import('@/views/Datasets.vue'),
          meta: { title: '数据集管理', icon: 'FolderOpened' }
        },
        {
          path: 'models',
          name: 'Models',
          component: () => import('@/views/Models.vue'),
          meta: { title: '模型管理', icon: 'Box' }
        },
        {
          path: 'history',
          name: 'History',
          component: () => import('@/views/History.vue'),
          meta: { title: '历史记录', icon: 'Clock' }
        },
        {
          path: 'settings',
          name: 'Settings',
          component: () => import('@/views/Settings.vue'),
          meta: { title: '系统设置', icon: 'Setting' }
        }
      ]
    }
  ]
})

router.beforeEach(async (to, _from, next) => {
  const userStore = useUserStore()
  document.title = to.meta.title ? `${to.meta.title} - INN 图像隐写系统` : 'INN 图像隐写系统'
  
  if (!userStore.initialized) {
    await userStore.initialize()
  }
  
  if (to.meta.requiresAuth === false) {
    if (to.path === '/login' && userStore.isLoggedIn) {
      next('/')
    } else {
      next()
    }
    return
  }
  
  if (!userStore.isLoggedIn) {
    next({ path: '/login', query: { redirect: to.fullPath } })
    return
  }
  
  next()
})

export default router
