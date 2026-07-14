<!--
  @author: caoshuai.cs
  @date: 2026-07-14
  @description: 全局 toast 渲染容器，固定在右上角，配合 useToast 使用
-->
<template>
  <Teleport to="body">
    <div class="toast-container">
      <TransitionGroup name="toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          :class="['toast-item', `toast-${toast.type}`]"
          role="alert"
          @click="removeToast(toast.id)"
        >
          <span class="toast-icon" v-html="iconOf(toast.type)"></span>
          <span class="toast-message">{{ toast.message }}</span>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup>
import { useToast } from '../composables/useToast'

const { toasts, removeToast } = useToast()

const iconOf = (type) => {
  const icons = {
    success:
      '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"></path></svg>',
    error:
      '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>',
    warning:
      '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>',
    info:
      '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>',
  }
  return icons[type] || icons.info
}
</script>

<style lang="scss" scoped>
.toast-container {
  position: fixed;
  top: 24px;
  right: 24px;
  z-index: 10000;
  display: flex;
  flex-direction: column;
  gap: 12px;
  pointer-events: none;
}

.toast-item {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 240px;
  max-width: 420px;
  padding: 12px 16px;
  border-radius: 12px;
  background: #fff;
  color: var(--text-primary, #353740);
  font-size: 14px;
  line-height: 1.5;
  cursor: pointer;
  pointer-events: auto;
  border: 1px solid var(--border-color, #e5e5e5);
  border-left: 4px solid var(--primary-color, #90138b);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
}

.toast-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.toast-message {
  flex: 1;
  word-break: break-word;
}

.toast-success {
  border-left-color: #10b981;

  .toast-icon {
    color: #10b981;
  }
}

.toast-error {
  border-left-color: #ef4444;

  .toast-icon {
    color: #ef4444;
  }
}

.toast-warning {
  border-left-color: #f59e0b;

  .toast-icon {
    color: #f59e0b;
  }
}

.toast-info {
  border-left-color: var(--primary-color, #90138b);

  .toast-icon {
    color: var(--primary-color, #90138b);
  }
}

.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(24px);
}

.toast-leave-to {
  opacity: 0;
  transform: translateX(24px);
}

.toast-move {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
</style>
