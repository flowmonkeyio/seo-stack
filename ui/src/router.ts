import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import HomeView from './views/HomeView.vue'

// M0 scaffold: only "/" exists. Real views (Projects, Clusters, Topics,
// Articles, Interlinks, Gsc, Drift, Runs, Procedures, ...) land in M6.
const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: HomeView,
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
