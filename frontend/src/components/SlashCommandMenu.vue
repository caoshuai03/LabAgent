<!--
  @author: caoshuai.cs
  @date: 2026-08-01
  @description: 聊天输入框斜杠命令与技能选择菜单
-->
<template>
  <transition name="slash-menu-fade">
    <div v-if="open" class="slash-command-menu" role="listbox" aria-label="斜杠命令">
      <div v-if="commandItems.length" class="menu-section">
        <div class="section-title">命令</div>
        <button
          v-for="item in commandItems"
          :key="item.id"
          type="button"
          class="menu-item"
          :class="{ active: activeItemId === item.id, disabled: item.disabled }"
          :disabled="item.disabled"
          role="option"
          :aria-selected="activeItemId === item.id"
          @mousedown.prevent
          @mouseenter="activateItem(item)"
          @click="selectItem(item)"
        >
          <span class="item-icon command-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M8 3v5H3"></path>
              <path d="M16 3v5h5"></path>
              <path d="M8 21v-5H3"></path>
              <path d="M16 21v-5h5"></path>
            </svg>
          </span>
          <span class="item-content">
            <span class="item-name">压缩上下文</span>
            <span class="item-description">
              {{ isCompressing ? '正在压缩当前会话' : '主动压缩当前会话较早内容' }}
            </span>
          </span>
        </button>
      </div>

      <div class="menu-section">
        <div class="section-title">技能</div>
        <div v-if="loadingSkills" class="menu-status">正在加载技能...</div>
        <template v-else>
          <button
            v-for="item in skillItems"
            :key="item.id"
            type="button"
            class="menu-item"
            :class="{ active: activeItemId === item.id }"
            role="option"
            :aria-selected="activeItemId === item.id"
            @mousedown.prevent
            @mouseenter="activateItem(item)"
            @click="selectItem(item)"
          >
            <span class="item-icon skill-icon" aria-hidden="true">
              <ToolActivityIcon :tool-name="`skill:${item.skill.name}`" />
            </span>
            <span class="item-content">
              <span class="item-name">{{ item.skill.name }}</span>
              <span class="item-description">{{ item.skill.description }}</span>
            </span>
          </button>
        </template>
        <div v-if="!loadingSkills && !skillItems.length" class="menu-status">
          {{ query ? '没有匹配的技能' : '暂无可用技能' }}
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import ToolActivityIcon from './icons/ToolActivityIcon.vue'

const props = defineProps({
  open: {
    type: Boolean,
    default: false,
  },
  query: {
    type: String,
    default: '',
  },
  skills: {
    type: Array,
    default: () => [],
  },
  selectedSkillNames: {
    type: Array,
    default: () => [],
  },
  canCompress: {
    type: Boolean,
    default: false,
  },
  isCompressing: {
    type: Boolean,
    default: false,
  },
  loadingSkills: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['select', 'close'])
const activeItemId = ref('')

const normalizedQuery = computed(() => props.query.trim().toLowerCase())

const matchesQuery = (...values) => {
  if (!normalizedQuery.value) return true
  return values.some((value) =>
    String(value || '')
      .toLowerCase()
      .includes(normalizedQuery.value),
  )
}

const commandItems = computed(() => {
  if (!matchesQuery('压缩上下文', '压缩', 'compact')) return []
  return [
    {
      id: 'command:compress',
      type: 'compress',
      disabled: !props.canCompress,
    },
  ]
})

const skillItems = computed(() => {
  const selectedNames = new Set(props.selectedSkillNames)
  return props.skills
    .filter((skill) => !selectedNames.has(skill.name))
    .filter((skill) => matchesQuery(skill.name, skill.description))
    .map((skill) => ({
      id: `skill:${skill.name}`,
      type: 'skill',
      disabled: false,
      skill,
    }))
})

const selectableItems = computed(() => {
  return [...commandItems.value, ...skillItems.value].filter((item) => !item.disabled)
})

const resetActiveItem = () => {
  activeItemId.value = selectableItems.value[0]?.id || ''
}

const activateItem = (item) => {
  if (!item.disabled) activeItemId.value = item.id
}

const selectItem = (item) => {
  if (item.disabled) return
  emit('select', item)
}

const moveActiveItem = (offset) => {
  if (!selectableItems.value.length) return
  const currentIndex = selectableItems.value.findIndex((item) => item.id === activeItemId.value)
  const nextIndex =
    (Math.max(currentIndex, 0) + offset + selectableItems.value.length) %
    selectableItems.value.length
  activeItemId.value = selectableItems.value[nextIndex].id
}

const handleKeyDown = (event) => {
  if (!props.open) return false
  if (event.key === 'Escape') {
    event.preventDefault()
    emit('close')
    return true
  }
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault()
    moveActiveItem(event.key === 'ArrowDown' ? 1 : -1)
    return true
  }
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    const selectedItem = selectableItems.value.find((item) => item.id === activeItemId.value)
    if (selectedItem) selectItem(selectedItem)
    return true
  }
  return false
}

watch(
  () => [
    props.open,
    normalizedQuery.value,
    props.skills,
    props.selectedSkillNames,
    props.canCompress,
  ],
  resetActiveItem,
  { immediate: true },
)

defineExpose({ handleKeyDown })
</script>

<style lang="scss" scoped>
.slash-command-menu {
  position: absolute;
  right: 0;
  bottom: calc(100% + 8px);
  left: 0;
  z-index: 1300;
  max-height: min(340px, calc(var(--app-height, 100vh) - 160px));
  padding: 6px;
  overflow-y: auto;
  border: 1px solid rgba(229, 231, 235, 0.96);
  border-radius: 14px;
  background: var(--app-page-bg);
  box-shadow:
    0 18px 46px rgba(17, 24, 39, 0.14),
    0 1px 0 rgba(255, 255, 255, 0.92) inset;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}

.menu-section + .menu-section {
  margin-top: 4px;
}

.section-title {
  padding: 3px 8px 4px;
  color: var(--text-secondary, #737889);
  font-size: 11px;
  font-weight: 600;
}

.menu-item {
  display: grid;
  grid-template-columns: 22px minmax(0, 1fr);
  gap: 8px;
  align-items: center;
  width: 100%;
  min-height: 40px;
  padding: 5px 8px;
  border: 0;
  border-radius: 9px;
  color: var(--text-primary, #242424);
  background: transparent;
  text-align: left;
  cursor: pointer;

  &.active {
    background: rgba(0, 0, 0, 0.055);
  }

  &.disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
}

.item-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  color: #555861;
  background: transparent;

  svg {
    width: 15px;
    height: 15px;
  }
}

.item-content {
  min-width: 0;
}

.item-name,
.item-description {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-name {
  color: #4c4f57;
  font-size: 13px;
  font-weight: 600;
}

.item-description {
  margin-top: 1px;
  color: #a1a3aa;
  font-size: 11px;
}

.menu-status {
  padding: 9px 8px;
  color: var(--text-secondary, #858895);
  font-size: 12px;
}

.slash-menu-fade-enter-active,
.slash-menu-fade-leave-active {
  transition:
    opacity 0.08s ease-out,
    transform 0.08s ease-out;
}

.slash-menu-fade-enter-from,
.slash-menu-fade-leave-to {
  opacity: 0;
  transform: translateY(2px) scale(0.995);
}

@media (max-width: 768px) {
  .slash-command-menu {
    max-height: min(320px, calc(var(--app-height, 100vh) - 140px));
  }

  .menu-item {
    min-height: 44px;
  }
}
</style>
