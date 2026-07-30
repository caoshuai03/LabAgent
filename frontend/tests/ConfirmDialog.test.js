/**
 * @author: caoshuai.cs
 * @date: 2026-07-31 01:47
 * @description: 全局确认弹窗的渲染与确认结果测试
 */
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { describe, expect, it } from 'vitest'
import ConfirmDialog from '../src/components/ConfirmDialog.vue'
import { useConfirm } from '../src/composables/useConfirm'

describe('ConfirmDialog', () => {
  it('展示统一文案并返回确认结果', async () => {
    const wrapper = mount(ConfirmDialog, {
      global: {
        stubs: {
          Teleport: true,
        },
      },
    })
    const { confirm } = useConfirm()
    const result = confirm({
      title: '删除文件',
      message: '确定要删除这个文件吗？',
      description: '删除后无法恢复。',
      confirm_text: '确认删除',
      tone: 'danger',
    })

    await nextTick()

    expect(wrapper.get('[role="alertdialog"]').text()).toContain('删除文件')
    expect(wrapper.text()).toContain('删除后无法恢复。')

    const buttons = wrapper.findAll('button')
    expect(buttons.map((button) => button.text())).toEqual(['取消', '确认删除'])
    await buttons[1].trigger('click')

    await expect(result).resolves.toBe(true)
    wrapper.unmount()
  })
})
