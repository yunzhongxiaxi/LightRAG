/**
 * Prompt Management Feature - Redesigned
 *
 * 支持订阅机制、逻辑版本号显示、ETag 轮询的 Prompt 管理界面
 */

import { useState, useEffect, useCallback } from 'react'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import {
  PlusIcon,
  EditIcon,
  TrashIcon,
  CheckIcon,
  BellIcon,
  BellOffIcon,
  RefreshCwIcon
} from 'lucide-react'
import { toast } from 'sonner'

interface Template {
  id: number
  creator: string
  version: number  // 真实版本号
  content: Record<string, string>
  is_deleted: boolean
  created_at: string
  updated_at: string
}

interface Subscription {
  user_id: string
  creator: string
  subscribed_version: number | null
  is_auto_update: boolean
  last_synced_at: string
}

const PromptManagement = () => {
  const [creators, setCreators] = useState<string[]>([])
  const [selectedCreator, setSelectedCreator] = useState<string | null>(null)
  const [versions, setVersions] = useState<number[]>([])  // 真实版本号列表
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null)
  const [subscription, setSubscription] = useState<Subscription | null>(null)
  const [loading, setLoading] = useState(false)
  const [etag, setEtag] = useState<string | null>(null)
  const userId = localStorage.getItem('user_id') || 'default_user'

  // 获取版本列表
  const fetchVersions = useCallback(async (creator: string) => {
    setLoading(true)
    try {
      const response = await fetch(`/api/prompts/${creator}/versions`)
      if (!response.ok) throw new Error('Failed to fetch versions')
      const data = await response.json()
      setVersions(data.versions)  // 真实版本号，降序
    } catch (error) {
      toast.error('Failed to load versions')
      console.error(error)
    } finally {
      setLoading(false)
    }
  }, [])

  // 获取模板（支持 ETag）
  const fetchTemplate = useCallback(async (creator: string, version: number) => {
    try {
      const headers: HeadersInit = {}
      if (etag) {
        headers['If-None-Match'] = etag
      }

      const response = await fetch(
        `/api/prompts/${creator}/templates/${version}`,
        { headers }
      )

      if (response.status === 304) {
        // 无更新
        return
      }

      if (!response.ok) throw new Error('Failed to fetch template')

      const newEtag = response.headers.get('ETag')
      if (newEtag) setEtag(newEtag)

      const data = await response.json()
      setSelectedTemplate(data)
    } catch (error) {
      toast.error('Failed to load template')
      console.error(error)
    }
  }, [etag])

  // 获取订阅信息
  const fetchSubscription = useCallback(async (creator: string) => {
    try {
      const response = await fetch(`/api/prompts/subscriptions/${creator}`)
      if (response.status === 404) {
        setSubscription(null)
        return
      }
      if (!response.ok) throw new Error('Failed to fetch subscription')
      const data = await response.json()
      setSubscription(data)
    } catch (error) {
      console.error(error)
    }
  }, [])

  // 订阅模板
  const subscribe = async (creator: string, version: number | null, autoUpdate: boolean) => {
    try {
      const response = await fetch('/api/prompts/subscriptions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          creator,
          version,
          is_auto_update: autoUpdate
        })
      })
      if (!response.ok) throw new Error('Failed to subscribe')
      toast.success('Subscribed successfully')
      fetchSubscription(creator)
    } catch (error) {
      toast.error('Failed to subscribe')
      console.error(error)
    }
  }

  // 取消订阅
  const unsubscribe = async (creator: string) => {
    try {
      const response = await fetch(`/api/prompts/subscriptions/${creator}`, {
        method: 'DELETE'
      })
      if (!response.ok) throw new Error('Failed to unsubscribe')
      toast.success('Unsubscribed successfully')
      setSubscription(null)
    } catch (error) {
      toast.error('Failed to unsubscribe')
      console.error(error)
    }
  }

  // 创建新版本
  const createVersion = async (creator: string, content: Record<string, string>) => {
    try {
      const response = await fetch(`/api/prompts/${creator}/templates`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content })
      })
      if (!response.ok) throw new Error('Failed to create version')
      const data = await response.json()
      toast.success(`Created version ${data.version}`)
      fetchVersions(creator)
    } catch (error) {
      toast.error('Failed to create version')
      console.error(error)
    }
  }

  // 软删除版本
  const deleteVersion = async (creator: string, version: number) => {
    if (!confirm(`Delete version ${version}?`)) return

    try {
      const response = await fetch(
        `/api/prompts/${creator}/templates/${version}`,
        { method: 'DELETE' }
      )
      if (!response.ok) throw new Error('Failed to delete version')
      toast.success('Version deleted')
      fetchVersions(creator)
    } catch (error) {
      toast.error('Failed to delete version')
      console.error(error)
    }
  }

  // 30 秒 ETag 轮询（仅当订阅最新版本时）
  useEffect(() => {
    if (!selectedCreator || !subscription || subscription.subscribed_version !== null) {
      return
    }

    const interval = setInterval(() => {
      if (selectedTemplate) {
        fetchTemplate(selectedCreator, selectedTemplate.version)
      }
    }, 30000)  // 30 秒

    return () => clearInterval(interval)
  }, [selectedCreator, subscription, selectedTemplate, fetchTemplate])

  // 初始化
  useEffect(() => {
    // TODO: 获取创建者列表
    setCreators([userId])
    setSelectedCreator(userId)
  }, [userId])

  useEffect(() => {
    if (selectedCreator) {
      fetchVersions(selectedCreator)
      fetchSubscription(selectedCreator)
    }
  }, [selectedCreator, fetchVersions, fetchSubscription])

  // 逻辑版本号映射
  const getLogicalVersion = (realVersion: number): number => {
    return versions.indexOf(realVersion) + 1
  }

  return (
    <div className="container mx-auto p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Prompt Management</h1>
        <Button onClick={() => createVersion(userId, {})}>
          <PlusIcon className="w-4 h-4 mr-2" />
          New Version
        </Button>
      </div>

      {/* 订阅状态 */}
      {subscription && (
        <Card className="p-4 mb-4 bg-blue-50 dark:bg-blue-900/20">
          <div className="flex justify-between items-center">
            <div>
              <div className="font-semibold">
                Subscribed to {subscription.creator}
                {subscription.subscribed_version
                  ? ` v${getLogicalVersion(subscription.subscribed_version)}`
                  : ' (Latest)'}
              </div>
              {subscription.is_auto_update && (
                <div className="text-sm text-muted-foreground">
                  Auto-update enabled • Last synced: {new Date(subscription.last_synced_at).toLocaleString()}
                </div>
              )}
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={() => unsubscribe(subscription.creator)}
            >
              Unsubscribe
            </Button>
          </div>
        </Card>
      )}

      {/* 版本列表 */}
      {loading ? (
        <div className="text-center py-12">Loading...</div>
      ) : (
        <div className="grid gap-4">
          {versions.map((realVersion, index) => {
            const logicalVersion = index + 1
            const isSubscribed = subscription?.subscribed_version === realVersion ||
                                (subscription?.subscribed_version === null && index === 0)

            return (
              <Card key={realVersion} className="p-4">
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <h3 className="text-lg font-semibold">
                        Version {logicalVersion}
                      </h3>
                      <Badge variant="outline">
                        Real: v{realVersion}
                      </Badge>
                      {index === 0 && (
                        <Badge variant="default">Latest</Badge>
                      )}
                      {isSubscribed && (
                        <Badge variant="secondary">Subscribed</Badge>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => subscribe(selectedCreator!, realVersion, false)}
                      title="Subscribe to this version"
                    >
                      <BellOffIcon className="w-4 h-4" />
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => subscribe(selectedCreator!, null, true)}
                      title="Subscribe to latest (auto-update)"
                      disabled={index !== 0}
                    >
                      <BellIcon className="w-4 h-4" />
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => fetchTemplate(selectedCreator!, realVersion)}
                    >
                      <EditIcon className="w-4 h-4" />
                    </Button>
                    {selectedCreator === userId && (
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => deleteVersion(selectedCreator, realVersion)}
                      >
                        <TrashIcon className="w-4 h-4" />
                      </Button>
                    )}
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}

      {/* 模板详情（简化版） */}
      {selectedTemplate && (
        <Card className="p-6 mt-6">
          <h2 className="text-xl font-bold mb-4">
            Template Details - Version {getLogicalVersion(selectedTemplate.version)}
          </h2>
          <div className="text-sm text-muted-foreground mb-4">
            Real version: {selectedTemplate.version} •
            Updated: {new Date(selectedTemplate.updated_at).toLocaleString()}
          </div>
          <div className="space-y-2">
            <strong>Configured Prompts:</strong>
            <ul className="list-disc list-inside">
              {Object.keys(selectedTemplate.content).map(key => (
                <li key={key}>{key}</li>
              ))}
            </ul>
          </div>
        </Card>
      )}
    </div>
  )
}

export default PromptManagement
