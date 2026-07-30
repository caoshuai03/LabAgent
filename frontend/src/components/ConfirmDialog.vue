<!--
  @author: caoshuai.cs
  @date: 2026-07-31 01:42
  @description: 项目级确认弹窗，提供统一的视觉、文案和无障碍交互
-->
<template>
  <Teleport to="body">
    <Transition name="confirm-dialog">
      <div
        v-if="dialog"
        class="confirm-overlay"
        role="presentation"
        @mousedown.self="cancelAction"
      >
        <section
          ref="dialogElement"
          class="confirm-panel"
          role="alertdialog"
          aria-modal="true"
          :aria-labelledby="titleId"
          :aria-describedby="descriptionId"
          @keydown.esc.prevent="cancelAction"
          @keydown.tab="handleTab"
        >
          <div :class="['confirm-icon', `is-${dialog.tone}`]" aria-hidden="true">
            <svg
              width="22"
              height="22"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path d="M12 9v4" />
              <path d="M12 17h.01" />
              <path d="M10.3 3.9 2.2 18a2 2 0 0 0 1.7 3h16.2a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
            </svg>
          </div>

          <div class="confirm-content">
            <h2 :id="titleId">{{ dialog.title }}</h2>
            <p :id="descriptionId" class="confirm-message">{{ dialog.message }}</p>
            <p v-if="dialog.description" class="confirm-description">
              {{ dialog.description }}
            </p>
          </div>

          <div class="confirm-actions">
            <button ref="cancelButton" type="button" class="button secondary" @click="cancelAction">
              {{ dialog.cancel_text }}
            </button>
            <button
              type="button"
              :class="['button', 'primary', `is-${dialog.tone}`]"
              @click="confirmAction"
            >
              {{ dialog.confirm_text }}
            </button>
          </div>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { nextTick, ref, watch } from 'vue'
import { useConfirm } from '../composables/useConfirm'

const { dialog, confirmAction, cancelAction } = useConfirm()
const dialogElement = ref(null)
const cancelButton = ref(null)
const titleId = 'global-confirm-title'
const descriptionId = 'global-confirm-description'
let previouslyFocusedElement = null

const handleTab = (event) => {
  const focusableElements = dialogElement.value?.querySelectorAll('button:not(:disabled)')
  if (!focusableElements?.length) return

  const firstElement = focusableElements[0]
  const lastElement = focusableElements[focusableElements.length - 1]
  if (event.shiftKey && document.activeElement === firstElement) {
    event.preventDefault()
    lastElement.focus()
  } else if (!event.shiftKey && document.activeElement === lastElement) {
    event.preventDefault()
    firstElement.focus()
  }
}

watch(dialog, async (currentDialog) => {
  if (currentDialog) {
    previouslyFocusedElement = document.activeElement
    await nextTick()
    cancelButton.value?.focus()
    return
  }

  previouslyFocusedElement?.focus?.()
  previouslyFocusedElement = null
})
</script>

<style lang="scss" scoped>
.confirm-overlay {
  position: fixed;
  inset: 0;
  z-index: 11000;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgba(24, 20, 28, 0.38);
  backdrop-filter: blur(3px);
  -webkit-backdrop-filter: blur(3px);
}

.confirm-panel {
  width: min(420px, 100%);
  padding: 24px;
  border: 1px solid color-mix(in srgb, var(--border-color, #e5e5e5) 82%, transparent);
  border-radius: 14px;
  background: var(--bg-primary, #fff);
  color: var(--text-primary, #353740);
  box-shadow:
    0 24px 64px rgba(31, 22, 34, 0.2),
    0 4px 16px rgba(31, 22, 34, 0.08);
}

.confirm-icon {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  margin-bottom: 18px;
  border-radius: 12px;
  background: rgba(144, 19, 139, 0.09);
  color: var(--primary-color, #90138b);

  &.is-danger {
    background: rgba(220, 38, 38, 0.09);
    color: #dc2626;
  }
}

.confirm-content {
  h2 {
    margin: 0;
    color: var(--text-primary, #353740);
    font-size: 17px;
    font-weight: 600;
    line-height: 1.45;
  }
}

.confirm-message {
  margin: 8px 0 0;
  color: var(--text-secondary, #6e6e80);
  font-size: 14px;
  line-height: 1.65;
  overflow-wrap: anywhere;
}

.confirm-description {
  margin: 6px 0 0;
  color: var(--text-tertiary, #8e8ea0);
  font-size: 13px;
  line-height: 1.55;
}

.confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 24px;
}

.button {
  min-width: 76px;
  padding: 9px 16px;
  border: 1px solid transparent;
  border-radius: 8px;
  font: inherit;
  font-size: 14px;
  font-weight: 500;
  line-height: 1.3;
  cursor: pointer;
  transition:
    background-color 0.18s ease,
    border-color 0.18s ease,
    box-shadow 0.18s ease,
    transform 0.18s ease;

  &:focus-visible {
    outline: 2px solid rgba(144, 19, 139, 0.35);
    outline-offset: 2px;
  }

  &:active {
    transform: translateY(1px);
  }

  &.secondary {
    border-color: var(--border-color, #e5e5e5);
    background: var(--bg-primary, #fff);
    color: var(--text-secondary, #6e6e80);

    &:hover {
      border-color: var(--border-color-hover, #d1d1d1);
      background: var(--bg-hover, #e5e5e5);
      color: var(--text-primary, #353740);
    }
  }

  &.primary {
    background: var(--primary-color, #90138b);
    color: #fff;

    &:hover {
      background: #a01ba0;
      box-shadow: 0 5px 14px rgba(144, 19, 139, 0.2);
    }

    &.is-danger {
      background: #dc2626;

      &:hover {
        background: #c81e1e;
        box-shadow: 0 5px 14px rgba(220, 38, 38, 0.2);
      }
    }
  }
}

.confirm-dialog-enter-active,
.confirm-dialog-leave-active {
  transition: opacity 0.2s ease;

  .confirm-panel {
    transition:
      opacity 0.2s ease,
      transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  }
}

.confirm-dialog-enter-from,
.confirm-dialog-leave-to {
  opacity: 0;

  .confirm-panel {
    opacity: 0;
    transform: translateY(8px) scale(0.98);
  }
}

@media (max-width: 480px) {
  .confirm-panel {
    padding: 22px 20px 20px;
  }

  .confirm-actions {
    flex-direction: column-reverse;
  }

  .button {
    width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .confirm-dialog-enter-active,
  .confirm-dialog-leave-active,
  .confirm-dialog-enter-active .confirm-panel,
  .confirm-dialog-leave-active .confirm-panel {
    transition: none;
  }
}
</style>
