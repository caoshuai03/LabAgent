import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { tooltipDirective } from './directives/tooltip'
import { clickOutsideDirective } from './directives/clickOutside'

const app = createApp(App)

app.directive('tooltip', tooltipDirective)
app.directive('click-outside', clickOutsideDirective)

app.use(createPinia())
app.use(router)
app.mount('#app')
