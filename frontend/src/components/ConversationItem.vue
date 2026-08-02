<template>
  <div
    :class="[
      'conversation-item',
      {
        active: isActive && !isSelectionMode,
        'selection-mode': isSelectionMode,
        selected: isSelectionMode && isSelected,
      },
    ]"
    @click="handleClick"
    @mouseenter="handleMouseEnter"
    @mouseleave="handleMouseLeave"
  >
    <!-- 批量删除模式下通过点击整行切换选中状态，交互与知识库文件列表保持一致 -->
    <div class="content" @dblclick="handleDoubleClick">
      <div
        ref="titleRef"
        :class="['title', { scrollable: isTitleOverflowing }]"
        :style="titleScrollStyle"
      >
        <span ref="titleTextRef" class="title-text">{{ conversation.title }}</span>
      </div>
    </div>

    <span
      v-if="!isSelectionMode && (isStreaming || hasUnreadCompletion)"
      :class="['conversation-status', { streaming: isStreaming }]"
      :aria-label="isStreaming ? '正在输出' : '输出已完成'"
      role="status"
    />

    <div
      v-if="(showActions || isMenuOpen || isCoarsePointer) && !isSelectionMode"
      :class="['actions', { visible: showActions || isMenuOpen || isCoarsePointer }]"
      @click.stop
      ref="menuRef"
    >
      <button
        @click="toggleMenu"
        class="action-button more"
        v-tooltip="'更多操作'"
        ref="menuButtonRef"
      >
        <MoreIcon :size="16" />
      </button>

      <!-- 下拉菜单 -->
      <div v-if="isMenuOpen" class="dropdown-menu" :style="menuStyle" ref="dropdownMenuRef">
        <div class="menu-item" @click="handleDoubleClick">
          <EditIcon :size="14" />
          <span>重命名</span>
        </div>
        <div class="menu-item" @click="handleEnterBatchMode">
          <TrashIcon :size="14" />
          <span>批量删除</span>
        </div>
        <div class="menu-item delete" @click="handleDelete">
          <TrashIcon :size="14" />
          <span>删除此对话</span>
        </div>
      </div>
    </div>

    <input
      v-if="isRenaming"
      v-model="editTitle"
      @blur="handleSave"
      @keyup.enter="handleSave"
      @keyup.esc="handleCancel"
      class="edit-input"
      @click.stop
      ref="editInputRef"
    />
  </div>
</template>

<script setup>
import { ref, nextTick, watch, onMounted, onBeforeUnmount } from 'vue'
import TrashIcon from './icons/TrashIcon.vue'
import MoreIcon from './icons/MoreIcon.vue'
import EditIcon from './icons/EditIcon.vue'

const props = defineProps({
  conversation: {
    type: Object,
    required: true,
  },
  isActive: {
    type: Boolean,
    default: false,
  },
  isStreaming: {
    type: Boolean,
    default: false,
  },
  hasUnreadCompletion: {
    type: Boolean,
    default: false,
  },
  isSelectionMode: {
    type: Boolean,
    default: false,
  },
  isSelected: {
    type: Boolean,
    default: false,
  },
  isMenuOpen: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits([
  'select',
  'delete',
  'rename',
  'toggleSelect',
  'enterBatchMode',
  'toggleMenu',
])

const showActions = ref(false)
const isCoarsePointer = ref(false)
const menuRef = ref(null)
const menuButtonRef = ref(null)
const dropdownMenuRef = ref(null)
const menuStyle = ref({})
const isRenaming = ref(false)
const editTitle = ref('')
const editInputRef = ref(null)
const titleRef = ref(null)
const titleTextRef = ref(null)
const isTitleOverflowing = ref(false)
const titleScrollStyle = ref({})
let titleResizeObserver = null

const updateTitleOverflow = async () => {
  await nextTick()
  if (!titleRef.value || !titleTextRef.value) return

  const overflowDistance = Math.ceil(titleTextRef.value.scrollWidth - titleRef.value.clientWidth)
  isTitleOverflowing.value = overflowDistance > 1
  titleScrollStyle.value = isTitleOverflowing.value
    ? {
        '--title-scroll-distance': `-${overflowDistance}px`,
        '--title-scroll-duration': `${Math.min(10, Math.max(3, overflowDistance / 24))}s`,
      }
    : {}
}

const handleClick = (event) => {
  if (props.isSelectionMode) {
    emit('toggleSelect', {
      conversationId: props.conversation.id,
      isShiftRange: event.shiftKey,
    })
  } else if (!isRenaming.value) {
    emit('select', props.conversation.id)
  }
}

const handleDoubleClick = () => {
  if (props.isSelectionMode) return
  if (props.isMenuOpen) {
    emit('toggleMenu', { conversationId: props.conversation.id, nextOpen: false })
  }
  isRenaming.value = true
  editTitle.value = props.conversation.title
  nextTick(() => {
    editInputRef.value?.focus()
    editInputRef.value?.select()
  })
}

const handleSave = () => {
  if (editTitle.value.trim()) {
    emit('rename', props.conversation.id, editTitle.value.trim())
  }
  isRenaming.value = false
}

const handleCancel = () => {
  isRenaming.value = false
  editTitle.value = ''
}

const handleDelete = () => {
  // 关闭菜单
  emit('toggleMenu', { conversationId: props.conversation.id, nextOpen: false })
  emit('delete', props.conversation.id)
}

// 进入批量删除模式
const handleEnterBatchMode = () => {
  emit('toggleMenu', { conversationId: props.conversation.id, nextOpen: false })
  emit('enterBatchMode')
}

const handleMouseEnter = () => {
  showActions.value = true
  updateTitleOverflow()
}

// 鼠标移出时仅隐藏按钮区域，已展开菜单继续保留，等待外部点击后关闭
const handleMouseLeave = () => {
  if (!props.isMenuOpen) {
    showActions.value = false
  }
}

// 计算菜单位置：默认以三个点按钮为锚点向右上展开，超出屏幕边界时自动调整
const updateMenuPosition = () => {
  if (!menuButtonRef.value || !dropdownMenuRef.value) return

  const buttonRect = menuButtonRef.value.getBoundingClientRect()
  const menuRect = dropdownMenuRef.value.getBoundingClientRect()
  const viewportWidth = window.innerWidth
  const viewportHeight = window.innerHeight
  const gap = 8
  const edgePadding = 12
  let left = buttonRect.right + gap
  let top = buttonRect.bottom - menuRect.height

  if (left + menuRect.width > viewportWidth - edgePadding) {
    left = buttonRect.left - menuRect.width - gap
  }

  if (left < edgePadding) {
    left = Math.max(edgePadding, viewportWidth - edgePadding - menuRect.width)
  }

  if (top < edgePadding) {
    top = buttonRect.top + gap
  }

  if (top + menuRect.height > viewportHeight - edgePadding) {
    top = Math.max(edgePadding, viewportHeight - edgePadding - menuRect.height)
  }

  menuStyle.value = {
    left: `${left}px`,
    top: `${top}px`,
  }
}

const toggleMenu = () => {
  emit('toggleMenu', { conversationId: props.conversation.id, nextOpen: !props.isMenuOpen })
}

// 点击外部关闭菜单
const handleClickOutside = (event) => {
  if (menuRef.value && !menuRef.value.contains(event.target)) {
    emit('toggleMenu', { conversationId: props.conversation.id, nextOpen: false })
  }
}

const handleViewportChange = async () => {
  if (!props.isMenuOpen) return
  await nextTick()
  updateMenuPosition()
}

watch(
  () => props.isMenuOpen,
  async (isOpen) => {
    if (!isOpen) return
    showActions.value = true
    await nextTick()
    updateMenuPosition()
  },
)

watch(() => props.conversation.title, updateTitleOverflow)

onMounted(() => {
  isCoarsePointer.value = window.matchMedia('(hover: none) and (pointer: coarse)').matches
  updateTitleOverflow()
  if (typeof ResizeObserver !== 'undefined') {
    titleResizeObserver = new ResizeObserver(updateTitleOverflow)
    if (titleRef.value) {
      titleResizeObserver.observe(titleRef.value)
    }
  }
  document.addEventListener('click', handleClickOutside)
  window.addEventListener('resize', handleViewportChange)
  window.addEventListener('scroll', handleViewportChange, true)
})

onBeforeUnmount(() => {
  titleResizeObserver?.disconnect()
  document.removeEventListener('click', handleClickOutside)
  window.removeEventListener('resize', handleViewportChange)
  window.removeEventListener('scroll', handleViewportChange, true)
})
</script>

<style lang="scss" scoped>
.conversation-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  cursor: pointer;
  border: 1px solid transparent;
  border-radius: 12px;
  margin-bottom: 4px;
  position: relative;
  transition: all 0.2s;
  height: 36px;

  @media (hover: none) and (pointer: coarse) {
    height: 44px;

    .actions .action-button {
      width: 36px;
      height: 36px;
      padding: 8px;
    }
  }

  &.active {
    background-color: var(--bg-active);
  }

  &:hover,
  &.active:hover {
    background-color: rgba(144, 19, 139, 0.05);
  }

  &.selected {
    background-color: rgba(144, 19, 139, 0.08);
    border-color: rgba(144, 19, 139, 0.2);
  }

  &.selection-mode {
    user-select: none;
    -webkit-user-select: none;

    .content {
      margin-right: 0;
    }
  }

  .content {
    flex: 1;
    min-width: 0;
    margin-right: 24px; // 为操作按钮留出空间

    .title {
      font-size: 14px;
      font-weight: 400;
      white-space: nowrap;
      overflow: hidden;
      color: var(--text-primary);

      .title-text {
        display: block;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      &.scrollable {
        .title-text {
          width: max-content;
          overflow: visible;
        }
      }
    }
  }

  &:hover .title.scrollable .title-text {
    animation: conversation-title-scroll var(--title-scroll-duration) ease-in-out infinite alternate;

    @media (prefers-reduced-motion: reduce) {
      animation: none;
      width: auto;
      overflow: hidden;
      text-overflow: ellipsis;
    }
  }

  .conversation-status {
    position: absolute;
    right: 16px;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--text-tertiary);

    &.streaming {
      width: 12px;
      height: 12px;
      border: 2px solid var(--border-color);
      border-top-color: var(--text-secondary);
      background: transparent;
      animation: conversation-status-spin 0.8s linear infinite;
    }
  }

  &:hover .conversation-status,
  &:has(.actions.visible) .conversation-status {
    display: none;
  }

  .actions {
    position: absolute;
    right: 8px;
    display: flex;
    align-items: center;
    opacity: 0; // 默认隐藏，hover或菜单展开时显示
    transition: opacity 0.2s;
    background: transparent;
    padding-left: 10px;
    z-index: 3;

    &.visible {
      opacity: 1;
    }

    .action-button {
      background-color: transparent;
      border: none;
      cursor: pointer;
      color: var(--text-secondary);
      padding: 4px;
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      transition:
        background-color 0.15s ease,
        color 0.15s ease,
        transform 0.15s ease;

      &:hover {
        background-color: rgba(15, 23, 42, 0.04);
        color: var(--text-primary);
      }

      &:active {
        background-color: rgba(15, 23, 42, 0.1);
        color: var(--text-primary);
        transform: scale(0.97);
      }

      &:focus {
        outline: none;
      }
    }

    // 下拉菜单样式
    .dropdown-menu {
      position: fixed;
      min-width: 140px;
      max-width: min(220px, calc(100vw - 24px));
      z-index: 1200;
      overflow: hidden;
      background-color: var(--bg-secondary);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);

      .menu-item {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 10px 12px;
        cursor: pointer;
        font-size: 13px;
        color: var(--text-primary);
        transition: background-color 0.2s;

        &:hover {
          background-color: var(--bg-hover);
        }

        &.delete {
          color: #dc3545;

          &:hover {
            background-color: rgba(220, 53, 69, 0.1);
          }
        }

        svg {
          flex-shrink: 0;
        }
      }
    }
  }

  .edit-input {
    position: absolute;
    left: 4px;
    right: 4px;
    top: 4px;
    bottom: 4px;
    padding: 0 8px;
    border: 1px solid var(--primary-color);
    border-radius: 4px;
    outline: none;
    font-size: 14px;
    background-color: var(--bg-primary);
    color: var(--text-primary);
    z-index: 2;
  }
}

@keyframes conversation-status-spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes conversation-title-scroll {
  0%,
  15% {
    transform: translateX(0);
  }

  85%,
  100% {
    transform: translateX(var(--title-scroll-distance));
  }
}
</style>
