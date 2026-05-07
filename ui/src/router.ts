import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

import HomeView from './views/HomeView.vue'
import AuthErrorView from './views/AuthErrorView.vue'
import ProjectsView from './views/ProjectsView.vue'
import ProjectDetailView from './views/ProjectDetailView.vue'
import OverviewTab from './views/project-detail/OverviewTab.vue'
import VoiceTab from './views/project-detail/VoiceTab.vue'
import ComplianceTab from './views/project-detail/ComplianceTab.vue'
import EeatTab from './views/project-detail/EeatTab.vue'
import TargetsTab from './views/project-detail/TargetsTab.vue'
import IntegrationsTab from './views/project-detail/IntegrationsTab.vue'
import ClustersView from './views/ClustersView.vue'
import TopicsView from './views/TopicsView.vue'
import ArticlesView from './views/ArticlesView.vue'
import ArticleDetailView from './views/ArticleDetailView.vue'
import InterlinksView from './views/InterlinksView.vue'
import GscView from './views/GscView.vue'
import DriftView from './views/DriftView.vue'
import RunsView from './views/RunsView.vue'
import ProceduresView from './views/ProceduresView.vue'

// Routes per PLAN.md L185-L194 plus the extras spelled out in the M5.A
// brief. Project-detail tabs are nested children so the URL preserves
// the active tab on refresh + back/forward.
const routes: RouteRecordRaw[] = [
  { path: '/', name: 'home', component: HomeView },
  { path: '/auth-error', name: 'auth-error', component: AuthErrorView },
  { path: '/projects', name: 'projects', component: ProjectsView },
  {
    path: '/projects/:id',
    component: ProjectDetailView,
    redirect: (to) => ({ path: `/projects/${to.params.id}/overview` }),
    children: [
      { path: 'overview', name: 'project-detail-overview', component: OverviewTab },
      { path: 'voice', name: 'project-detail-voice', component: VoiceTab },
      { path: 'compliance', name: 'project-detail-compliance', component: ComplianceTab },
      { path: 'eeat', name: 'project-detail-eeat', component: EeatTab },
      { path: 'targets', name: 'project-detail-targets', component: TargetsTab },
      { path: 'integrations', name: 'project-detail-integrations', component: IntegrationsTab },
    ],
  },
  { path: '/projects/:id/clusters', name: 'project-clusters', component: ClustersView },
  { path: '/projects/:id/topics', name: 'project-topics', component: TopicsView },
  { path: '/projects/:id/articles', name: 'project-articles', component: ArticlesView },
  {
    path: '/projects/:id/articles/:aid',
    name: 'project-article-detail',
    component: ArticleDetailView,
  },
  { path: '/projects/:id/interlinks', name: 'project-interlinks', component: InterlinksView },
  { path: '/projects/:id/gsc', name: 'project-gsc', component: GscView },
  { path: '/projects/:id/drift', name: 'project-drift', component: DriftView },
  { path: '/projects/:id/runs', name: 'project-runs', component: RunsView },
  { path: '/projects/:id/procedures', name: 'project-procedures', component: ProceduresView },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
