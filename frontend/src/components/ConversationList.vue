<template>
  <div
    class="conversation-list"
    :class="{ 'is-scrolling': isScrolling }"
    @scroll="handleScroll"
  >
    <div class="list-container">
      <ConversationItem
        v-for="conversation in chatStore.conversations"
        :key="conversation.id"
        :conversation="conversation"
        :is-active="route.path === '/' && conversation.id === chatStore.currentConversationId"
        :is-streaming="chatStore.isConversationStreaming(conversation.id)"
        :has-unread-completion="chatStore.hasConversationUnreadCompletion(conversation.id)"
        :is-selection-mode="isSelectionMode"
        :is-selected="selectedIds.includes(conversation.id)"
        :is-menu-open="openedMenuConversationId === conversation.id"
        @select="handleSelect"
        @delete="handleDelete"
        @rename="handleRename"
        @toggleSelect="handleToggleSelect"
        @enterBatchMode="handleEnterBatchMode"
        @toggleMenu="handleToggleMenu"
      />
    </div>
  </div>
</template>

<script setup>
import { onUnmounted, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useChatStore } from '../stores/chat'
import { useConfirm } from '../composables/useConfirm'
import ConversationItem from './ConversationItem.vue'

const props = defineProps({
  isSelectionMode: {
    type: Boolean,
    default: false,
  },
  selectedIds: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['update:selectedIds', 'enterBatchMode'])

const router = useRouter()
const route = useRoute()
const chatStore = useChatStore()
const { confirm } = useConfirm()
const openedMenuConversationId = ref(null)
const isScrolling = ref(false)
const lastSelectedConversationId = ref(null)
let scrollbarHideTimer = null

// 历史会话滚动条默认隐藏，滚动时短暂显示
const flashScrollbar = () => {
  isScrolling.value = true
  if (scrollbarHideTimer) clearTimeout(scrollbarHideTimer)
  scrollbarHideTimer = setTimeout(() => {
    isScrolling.value = false
  }, 800)
}

const handleScroll = () => {
  flashScrollbar()
}

watch(
  () => [route.path, chatStore.currentConversationId],
  ([path, conversationId]) => {
    if (path === '/' && conversationId) {
      chatStore.clearConversationCompletion(conversationId)
    }
  },
  { immediate: true },
)

const handleSelect = (conversationId) => {
  openedMenuConversationId.value = null
  chatStore.switchConversation(conversationId)
  // 如果当前不在聊天页面，导航回聊天页面
  if (route.path !== '/') {
    router.push('/')
  }
}

const handleDelete = async (conversationId) => {
  openedMenuConversationId.value = null
  const confirmed = await confirm({
    title: '删除对话',
    message: '确定要删除这个对话吗？',
    description: '删除后，对话内容将无法恢复。',
    confirm_text: '确认删除',
    tone: 'danger',
  })
  if (!confirmed) return

  chatStore.deleteConversation(conversationId)
}

const handleRename = (conversationId, newTitle) => {
  chatStore.renameConversation(conversationId, newTitle)
}

// 统一维护当前展开的会话菜单
const handleToggleMenu = ({ conversationId, nextOpen }) => {
  openedMenuConversationId.value = nextOpen ? conversationId : null
}

const handleToggleSelect = ({ conversationId, isShiftRange = false }) => {
  const newSelectedIds = [...props.selectedIds]
  const currentIndex = chatStore.conversations.findIndex(
    (conversation) => conversation.id === conversationId,
  )

  if (isShiftRange && lastSelectedConversationId.value) {
    const lastIndex = chatStore.conversations.findIndex(
      (conversation) => conversation.id === lastSelectedConversationId.value,
    )

    if (currentIndex !== -1 && lastIndex !== -1) {
      const startIndex = Math.min(currentIndex, lastIndex)
      const endIndex = Math.max(currentIndex, lastIndex)
      const selectedSet = new Set(newSelectedIds)
      chatStore.conversations.slice(startIndex, endIndex + 1).forEach((conversation) => {
        selectedSet.add(conversation.id)
      })
      emit('update:selectedIds', [...selectedSet])
      return
    }
  }

  const index = newSelectedIds.indexOf(conversationId)
  if (index === -1) {
    newSelectedIds.push(conversationId)
  } else {
    newSelectedIds.splice(index, 1)
  }
  lastSelectedConversationId.value = conversationId
  emit('update:selectedIds', newSelectedIds)
}

// 进入批量删除模式
const handleEnterBatchMode = () => {
  openedMenuConversationId.value = null
  lastSelectedConversationId.value = null
  emit('enterBatchMode')
}

onUnmounted(() => {
  if (scrollbarHideTimer) clearTimeout(scrollbarHideTimer)
})
</script>

<style lang="scss" scoped>
.conversation-list {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;

  &::-webkit-scrollbar {
    width: 6px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-thumb {
    background: transparent;
    border-radius: 4px;
    transition: background 0.3s ease;
  }

  &.is-scrolling::-webkit-scrollbar-thumb,
  &:hover::-webkit-scrollbar-thumb {
    background: var(--scrollbar-thumb, #d1d1d1);

    &:hover {
      background: var(--scrollbar-thumb-hover, #b0b0b0);
    }
  }

  .list-container {
    padding: 8px;
    display: flex;
    flex-direction: column;
    gap: 0;
  }
}
</style>
