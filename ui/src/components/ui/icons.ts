import type { Component } from 'vue'
import {
  ArrowDownTrayIcon,
  ArrowPathIcon,
  ArrowTopRightOnSquareIcon,
  BoltIcon,
  ChevronDownIcon,
  Cog6ToothIcon,
  DocumentTextIcon,
  ListBulletIcon,
  NoSymbolIcon,
  PlusIcon,
  ShareIcon,
  TrashIcon,
} from '@heroicons/vue/24/outline'

export const UI_ICONS: Record<string, Component> = {
  ban: NoSymbolIcon,
  'chevron-down': ChevronDownIcon,
  'external-link': ArrowTopRightOnSquareIcon,
  'file-text': DocumentTextIcon,
  'git-branch': ShareIcon,
  list: ListBulletIcon,
  plus: PlusIcon,
  'plug-zap': BoltIcon,
  'rotate-ccw': ArrowPathIcon,
  save: ArrowDownTrayIcon,
  settings: Cog6ToothIcon,
  trash: TrashIcon,
}

export function iconComponent(name: string | undefined | null): Component | undefined {
  return name ? UI_ICONS[name] : undefined
}

export function hasIcon(name: string | undefined | null): boolean {
  return Boolean(iconComponent(name))
}
