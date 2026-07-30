<template>
  <el-container style="height: 100vh">
    <el-header style="display: flex; align-items: center; background: #1e1f20; border-bottom: 1px solid #333">
      <h2 style="color: #e3e3e3; margin: 0">KnowMate RAG Assistant</h2>
      <el-menu
        mode="horizontal"
        :ellipsis="false"
        style="margin-left: 40px; background: transparent; border-bottom: none"
        router
      >
        <el-menu-item index="/">💬 聊天</el-menu-item>
        <el-menu-item index="/knowledge">📚 知识库</el-menu-item>
        <el-menu-item index="/status">📊 状态</el-menu-item>
      </el-menu>
    </el-header>
    <el-main style="background: #131314; color: #e3e3e3">
      <router-view />
    </el-main>
  </el-container>
</template>