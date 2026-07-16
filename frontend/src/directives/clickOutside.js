/**
 * @author: caoshuai.cs
 * @date: 2026-07-16 16:44
 * @description: 点击元素外部时触发回调的通用指令
 */
export const clickOutsideDirective = {
  mounted(el, binding) {
    el.clickOutsideEvent = (event) => {
      if (!(el === event.target || el.contains(event.target))) {
        binding.value()
      }
    }
    document.addEventListener('click', el.clickOutsideEvent, true)
  },
  unmounted(el) {
    if (el.clickOutsideEvent) {
      document.removeEventListener('click', el.clickOutsideEvent, true)
    }
  },
}
