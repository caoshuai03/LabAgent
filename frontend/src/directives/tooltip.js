export const tooltipDirective = {
  mounted(el, binding) {
    if (!binding.value) return

    let tooltipTimer = null
    let tooltipEl = null

    const createTooltip = (text) => {
      tooltipEl = document.createElement('div')
      tooltipEl.className = 'global-tooltip'
      tooltipEl.textContent = text
      tooltipEl.style.visibility = 'hidden'
      document.body.appendChild(tooltipEl)

      const rect = el.getBoundingClientRect()
      const padding = 12
      const gap = 8

      requestAnimationFrame(() => {
        if (!tooltipEl) return

        const tooltipRect = tooltipEl.getBoundingClientRect()
        const halfWidth = tooltipRect.width / 2

        // 水平方向居中展示，并避开视口边缘
        let x = rect.left + rect.width / 2
        x = Math.max(padding + halfWidth, x)
        x = Math.min(window.innerWidth - padding - halfWidth, x)

        const hasEnoughTopSpace = rect.top - tooltipRect.height - gap >= padding
        const placement = hasEnoughTopSpace ? 'top' : 'bottom'
        const y = hasEnoughTopSpace ? rect.top - gap : rect.bottom + gap

        tooltipEl.classList.toggle('below', placement === 'bottom')
        tooltipEl.style.top = `${y}px`
        tooltipEl.style.left = `${x}px`
        tooltipEl.style.visibility = 'visible'
      })
    }

    const removeTooltip = () => {
      if (tooltipTimer) {
        clearTimeout(tooltipTimer)
        tooltipTimer = null
      }
      if (tooltipEl) {
        tooltipEl.remove()
        tooltipEl = null
      }
    }

    const onMouseEnter = () => {
      if (!el._tooltipValue) return
      removeTooltip()
      tooltipTimer = setTimeout(() => {
        createTooltip(el._tooltipValue)
      }, 400) // Delay showing
    }

    const onMouseLeave = () => {
      removeTooltip()
    }

    const onClick = () => {
      removeTooltip()
    }

    el._tooltipValue = binding.value
    el.addEventListener('mouseenter', onMouseEnter)
    el.addEventListener('mouseleave', onMouseLeave)
    el.addEventListener('click', onClick)

    el._tooltipHandlers = { onMouseEnter, onMouseLeave, onClick, removeTooltip }
  },
  updated(el, binding) {
    el._tooltipValue = binding.value
    if (el._tooltipHandlers && document.querySelector('.global-tooltip')) {
      const tooltipEl = document.querySelector('.global-tooltip')
      // Only update if this element's tooltip is currently showing
      if (tooltipEl && el.matches(':hover')) {
        tooltipEl.textContent = binding.value
      }
    }
  },
  unmounted(el) {
    if (el._tooltipHandlers) {
      el.removeEventListener('mouseenter', el._tooltipHandlers.onMouseEnter)
      el.removeEventListener('mouseleave', el._tooltipHandlers.onMouseLeave)
      el.removeEventListener('click', el._tooltipHandlers.onClick)
      el._tooltipHandlers.removeTooltip()
      delete el._tooltipHandlers
    }
    delete el._tooltipValue
  },
}
