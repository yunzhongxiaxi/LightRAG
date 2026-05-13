/**
 * Prompt Management Feature
 *
 * Provides UI for managing prompt templates, versions, and user configurations.
 */

import { useState, useEffect } from 'react'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Textarea } from '@/components/ui/Textarea'
import { Badge } from '@/components/ui/Badge'
import {
  PlusIcon,
  EditIcon,
  TrashIcon,
  HistoryIcon,
  CheckIcon,
  CopyIcon
} from 'lucide-react'
import { toast } from 'sonner'

interface PromptTemplate {
  id: number
  name: string
  description: string | null
  type: string
  created_by: string
  created_at: string
  updated_at: string
  is_template: boolean
}

interface PromptVersion {
  id: number
  version: number
  content: Record<string, string>
  created_at: string
  created_by: string
  comment: string | null
}

const PromptManagement = () => {
  const [templates, setTemplates] = useState<PromptTemplate[]>([])
  const [selectedTemplate, setSelectedTemplate] = useState<number | null>(null)
  const [versions, setVersions] = useState<PromptVersion[]>([])
  const [loading, setLoading] = useState(false)
  const [view, setView] = useState<'list' | 'edit' | 'versions'>('list')

  // Fetch templates
  const fetchTemplates = async () => {
    setLoading(true)
    try {
      const response = await fetch('/api/prompts/templates')
      if (!response.ok) throw new Error('Failed to fetch templates')
      const data = await response.json()
      setTemplates(data)
    } catch (error) {
      toast.error('Failed to load templates')
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  // Fetch versions for a template
  const fetchVersions = async (templateId: number) => {
    setLoading(true)
    try {
      const response = await fetch(`/api/prompts/templates/${templateId}/versions`)
      if (!response.ok) throw new Error('Failed to fetch versions')
      const data = await response.json()
      setVersions(data)
    } catch (error) {
      toast.error('Failed to load versions')
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  // Activate template for current user
  const activateTemplate = async (templateId: number) => {
    try {
      const userId = localStorage.getItem('user_id') || 'default_user'
      const response = await fetch('/api/prompts/user/activate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, template_id: templateId })
      })
      if (!response.ok) throw new Error('Failed to activate template')
      toast.success('Template activated successfully')
    } catch (error) {
      toast.error('Failed to activate template')
      console.error(error)
    }
  }

  // Delete template
  const deleteTemplate = async (templateId: number) => {
    if (!confirm('Are you sure you want to delete this template?')) return

    try {
      const response = await fetch(`/api/prompts/templates/${templateId}`, {
        method: 'DELETE'
      })
      if (!response.ok) throw new Error('Failed to delete template')
      toast.success('Template deleted successfully')
      fetchTemplates()
    } catch (error) {
      toast.error('Failed to delete template')
      console.error(error)
    }
  }

  // Rollback to version
  const rollbackToVersion = async (templateId: number, version: number) => {
    if (!confirm(`Rollback to version ${version}?`)) return

    try {
      const username = localStorage.getItem('username') || 'user'
      const response = await fetch(`/api/prompts/templates/${templateId}/rollback/${version}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rolled_back_by: username })
      })
      if (!response.ok) throw new Error('Failed to rollback')
      toast.success('Rolled back successfully')
      fetchVersions(templateId)
    } catch (error) {
      toast.error('Failed to rollback')
      console.error(error)
    }
  }

  useEffect(() => {
    fetchTemplates()
  }, [])

  // List view
  if (view === 'list') {
    return (
      <div className="container mx-auto p-6">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold">Prompt Management</h1>
          <Button onClick={() => setView('edit')}>
            <PlusIcon className="w-4 h-4 mr-2" />
            New Template
          </Button>
        </div>

        {loading ? (
          <div className="text-center py-12">Loading...</div>
        ) : (
          <div className="grid gap-4">
            {templates.map((template) => (
              <Card key={template.id} className="p-4">
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <h3 className="text-lg font-semibold">{template.name}</h3>
                      <Badge variant={template.type === 'system' ? 'default' : 'secondary'}>
                        {template.type}
                      </Badge>
                      {template.is_template && (
                        <Badge variant="outline">Template</Badge>
                      )}
                    </div>
                    {template.description && (
                      <p className="text-sm text-muted-foreground mb-2">
                        {template.description}
                      </p>
                    )}
                    <div className="text-xs text-muted-foreground">
                      Created by {template.created_by} •
                      Updated {new Date(template.updated_at).toLocaleDateString()}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setSelectedTemplate(template.id)
                        fetchVersions(template.id)
                        setView('versions')
                      }}
                    >
                      <HistoryIcon className="w-4 h-4" />
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => activateTemplate(template.id)}
                    >
                      <CheckIcon className="w-4 h-4" />
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setSelectedTemplate(template.id)
                        setView('edit')
                      }}
                    >
                      <EditIcon className="w-4 h-4" />
                    </Button>
                    {template.type !== 'system' && (
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => deleteTemplate(template.id)}
                      >
                        <TrashIcon className="w-4 h-4" />
                      </Button>
                    )}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    )
  }

  // Versions view
  if (view === 'versions' && selectedTemplate) {
    return (
      <div className="container mx-auto p-6">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold">Version History</h1>
          <Button variant="outline" onClick={() => setView('list')}>
            Back to List
          </Button>
        </div>

        {loading ? (
          <div className="text-center py-12">Loading...</div>
        ) : (
          <div className="grid gap-4">
            {versions.map((version) => (
              <Card key={version.id} className="p-4">
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <h3 className="text-lg font-semibold">Version {version.version}</h3>
                      {version.comment && (
                        <span className="text-sm text-muted-foreground">
                          - {version.comment}
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-muted-foreground mb-3">
                      Created by {version.created_by} •
                      {new Date(version.created_at).toLocaleString()}
                    </div>
                    <div className="text-sm">
                      <strong>Prompts:</strong> {Object.keys(version.content).length} configured
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => rollbackToVersion(selectedTemplate, version.version)}
                  >
                    Rollback
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    )
  }

  // Edit view (simplified - full implementation would use Monaco Editor)
  return (
    <div className="container mx-auto p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">
          {selectedTemplate ? 'Edit Template' : 'New Template'}
        </h1>
        <Button variant="outline" onClick={() => setView('list')}>
          Cancel
        </Button>
      </div>
      <Card className="p-6">
        <p className="text-muted-foreground">
          Full editor implementation with Monaco Editor coming soon...
        </p>
      </Card>
    </div>
  )
}

export default PromptManagement
