import { createApp } from 'vue';
import { createPinia } from 'pinia';
import naive from 'naive-ui';
import App from './App.vue';
import { router, installUnauthorizedRedirect } from './router';

const app = createApp(App);
app.use(createPinia());
app.use(router);
app.use(naive);
installUnauthorizedRedirect();
app.mount('#app');
