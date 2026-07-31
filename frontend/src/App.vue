<template>
  <el-container class="app-layout">
    <!-- 侧边栏导航 -->
    <el-aside :width="isCollapse ? '64px' : '220px'" class="app-aside">
      <!-- 侧边栏顶部品牌区 + 展开/收缩按钮 -->
      <div class="aside-header">
        <div class="brand-left">
          <div class="logo-badge">KM</div>
          <span v-if="!isCollapse" class="brand-text">KnowMate</span>
        </div>
        <!-- 移到了顶部 Logo 旁边的切换按钮 -->
        <button class="collapse-btn" @click="isCollapse = !isCollapse" :title="isCollapse ? '展开侧边栏' : '收起侧边栏'">
          <span class="btn-icon" :class="{ 'is-collapsed': isCollapse }">◀</span>
        </button>
      </div>

      <!-- 侧边栏菜单 -->
      <el-menu
        :default-active="$route.path"
        class="aside-menu"
        :collapse="isCollapse"
        router
      >
        <el-menu-item index="/">
          <span class="menu-icon">💬</span>
          <template #title>对话问答</template>
        </el-menu-item>
        <el-menu-item index="/knowledge">
          <span class="menu-icon">📚</span>
          <template #title>知识库管理</template>
        </el-menu-item>
        <el-menu-item index="/status">
          <span class="menu-icon">📊</span>
          <template #title>系统状态</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <!-- 右侧主区域 -->
    <el-container class="main-container">
      <!-- 顶部 Header（标题居中） -->
      <el-header class="app-header">
        <div class="header-center">
          <h2 class="app-title">
            KnowMate <span class="tag">RAG Assistant</span>
          </h2>
        </div>
      </el-header>

      <!-- 视图路由主体 -->
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref } from 'vue'

// 控制侧边栏展开/收缩状态
const isCollapse = ref(false)
</script>

<style scoped>
/* 全局页面容器 */
.app-layout {
  height: 100vh;
  background-color: #131417;
  color: #ececec;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  overflow: hidden;
}
/* 1. 消除页面默认边距，锁定视口高度为 100% 网页屏高 */
html, body {
  margin: 0;
  padding: 0;
  width: 100vw;
  height: 100vh;
  overflow: hidden; /* ❌ 彻底禁止外层页面出现滚动条 */
  background-color: #1e1f23; /* 设为你的主题深色，防止加载时闪白 */
}

/* 2. 确保 Vue 根节点挂载元素撑满全屏 */
#app {
  width: 100vw;
  height: 100vh;
  margin: 0;
  padding: 0;
  overflow: hidden;
}
/* 侧边栏容器 */
.app-aside {
  background-color: #18191c;
  border-right: 1px solid #28292d;
  display: flex;
  flex-direction: column;
  transition: width 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  user-select: none;
  z-index: 10;
}

/* 侧边栏顶部品牌区域 */
.aside-header {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.brand-left {
  display: flex;
  align-items: center;
  gap: 10px;
  overflow: hidden;
}


.logo-badge {
  width: 32px;
  height: 32px;
  margin-left :10px;
  background: linear-gradient(135deg, #2e3035, #18191c); /* 深灰渐变 */
  border: 1px solid rgba(255, 255, 255, 0.15);           /* 微亮细边框 */
  color: #c8e338;                                        /* 荧光黄绿文字 */
  font-weight: 800;
  font-size: 14px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}


.brand-text {
  font-size: 16px;
  font-weight: 700;
  color: #f3f4f6;
  letter-spacing: -0.3px;
  white-space: nowrap;
}

/* 顶部收缩按钮样式 */
.collapse-btn {
  background: transparent;
  border: none;
  color: #8e8ea0;
  width: 32px;
  height: 32px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
  padding: 0;
  flex-shrink: 0;
}

.collapse-btn:hover {
  background-color: rgba(255, 255, 255, 0.08);
  color: #ffffff;
}

.btn-icon {
  font-size: 11px;
  display: inline-block;
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

/* 侧边栏折叠时旋转图标 */
.btn-icon.is-collapsed {
  transform: rotate(180deg);
}

/* 侧边栏菜单样式 */
.aside-menu {
  border-right: none !important;
  background: transparent !important;
  flex: 1;
  padding-top: 12px;
}

.aside-menu :deep(.el-menu-item) {
  color: #9ca3af !important;
  height: 48px;
  line-height: 48px;
  font-size: 16px !important;       /* 字号加大（默认一般是 14px） */
  font-weight: 600 !important;
  margin: 4px 8px;
  border-radius: 8px;
  transition: all 0.2s ease;
}

.aside-menu :deep(.el-menu-item:hover) {
  color: #b8c1d1 !important;
  background-color: rgba(255, 255, 255, 0.05) !important;
}

.aside-menu :deep(.el-menu-item.is-active) {
  color: #000000 !important;
  background-color: #c8e338 !important;
  font-weight: 600;
  box-shadow: 0 2px 10px rgba(37, 99, 235, 0.3);
}

.menu-icon {
  margin-right: 12px;
  font-size: 16px;
}

/* 右侧主容器 */
.main-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

/* 顶栏 Header（主标题居中） */
.app-header {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #131417;
  border-bottom: 1px solid #232428;
  position: relative;
}

.header-center {
  text-align: center;
}

.app-title {
  color: #f3f4f6;
  font-size:30px;
  font-weight: 600;
  margin: 0;
  letter-spacing: -0.2px;
}

.app-title .tag {
  font-size: 15px;
  color: #c8e338;
  background-color: rgba(45, 46, 39, 0.08);
  border: 1px solid rgba(179, 207, 19, 0.25);
  padding: 3px 8px;
  border-radius: 6px; /* 小圆角矩形 */
  vertical-align: middle;
  margin-left: 10px;
}
/* 内容区域 */
.app-main {
  background-color: #131417;
  padding: 0;
  overflow: hidden;
  height: calc(100vh - 60px);
}
</style>

<style>
/* 全局样式：修正 body 默认边距与滚动条 */
html, body {
  margin: 0 !important;
  padding: 0 !important;
  width: 100%;
  height: 100%;
  overflow: hidden !important;
  background-color: #1e1f23;
}

#app {
  width: 100%;
  height: 100%;
  margin: 0;
  padding: 0;
  overflow: hidden;
}
</style>
