import React, { useRef, useState } from 'react'
import {
  Download,
  FolderOpen,
  MoreVertical,
  Plus,
  ShieldCheck,
  SlidersHorizontal,
  Upload,
} from 'lucide-react'

interface TopBarProps {
  onNewScenario: () => void
  onOpenTemplates: () => void
  onExportJson: () => void
  onImportJson: (file: File) => void
  onValidateScenario: () => void
  onOpenAdvancedConfig: () => void
  serverConnected: boolean | null
  isBusy: boolean
  serverVersion?: string
}

export const TopBar: React.FC<TopBarProps> = ({
  onNewScenario,
  onOpenTemplates,
  onExportJson,
  onImportJson,
  onValidateScenario,
  onOpenAdvancedConfig,
  serverConnected,
  isBusy,
  serverVersion,
}) => {
  const [showMenu, setShowMenu] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      onImportJson(file)
    }
    if (e.target) e.target.value = ''
    setShowMenu(false)
  }

  return (
    <header className="top-bar-minimal">
      {/* Hidden file input for JSON import */}
      <input
        type="file"
        ref={fileInputRef}
        style={{ display: 'none' }}
        accept=".json"
        onChange={handleFileChange}
      />

      {/* Brand: Logo & short name */}
      <div className="top-brand">
        <div className="top-logo-icon">
          <span className="logo-symbol">🐝</span>
        </div>
        <span className="top-app-name">ABC Optimizer</span>
      </div>

      {/* Main navigation actions */}
      <div className="top-nav-actions">
        <button
          id="btn-new-scenario"
          type="button"
          className="btn-top-action"
          onClick={onNewScenario}
          title="Crear un nuevo escenario vacío"
        >
          <Plus className="icon-xs" />
          <span>Nuevo</span>
        </button>

        <button
          id="btn-templates"
          type="button"
          className="btn-top-action"
          onClick={onOpenTemplates}
          title="Abrir galería de plantillas predefinidas"
        >
          <FolderOpen className="icon-xs" />
          <span>Plantillas</span>
        </button>

        {/* More Options Dropdown */}
        <div className="top-menu-wrapper">
          <button
            id="btn-more-options"
            type="button"
            className={`btn-top-icon ${showMenu ? 'active' : ''}`}
            onClick={() => setShowMenu(prev => !prev)}
            title="Más opciones (Importar, Exportar, Validar, Configuración)"
            aria-label="Más opciones"
          >
            <MoreVertical className="icon-xs" />
          </button>

          {showMenu && (
            <div className="top-dropdown-menu" onClick={() => setShowMenu(false)}>
              <button
                type="button"
                className="top-dropdown-item"
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload className="icon-xs" />
                <span>Importar JSON</span>
              </button>
              <button
                type="button"
                className="top-dropdown-item"
                onClick={onExportJson}
              >
                <Download className="icon-xs" />
                <span>Exportar JSON</span>
              </button>
              <div className="dropdown-divider" />
              <button
                type="button"
                className="top-dropdown-item"
                onClick={onValidateScenario}
              >
                <ShieldCheck className="icon-xs" />
                <span>Validar Escenario</span>
              </button>
              <button
                type="button"
                className="top-dropdown-item"
                onClick={onOpenAdvancedConfig}
              >
                <SlidersHorizontal className="icon-xs" />
                <span>Configuración Avanzada</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Connection Status: Discreet dot with tooltip (Requirement 8) */}
      <div className="top-status-indicator">
        <span
          className={`status-dot ${
            serverConnected === true
              ? isBusy
                ? 'status-dot-busy'
                : 'status-dot-connected'
              : serverConnected === false
              ? 'status-dot-disconnected'
              : 'status-dot-checking'
          }`}
          title={
            serverConnected === true
              ? isBusy
                ? 'FastAPI en ejecución (optimizando)'
                : `FastAPI conectado y disponible${serverVersion ? ` (v${serverVersion})` : ''}`
              : serverConnected === false
              ? 'Servidor backend no disponible'
              : 'Verificando conexión con el backend...'
          }
          aria-label="Estado de conexión backend"
        />
      </div>
    </header>
  )
}
