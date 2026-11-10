import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { TrendingUp, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { NAV_SECTIONS, WORKSPACES, isActiveRoute } from '@/config/navigation';
import { settingsAPI } from '../lib/api';

interface SidebarProps {
  open: boolean;
}

const COLLAPSED_KEY = 'sidebar_collapsed_sections';
const WORKSPACE_KEY = 'sidebar_workspace';

function loadCollapsed(): Record<string, boolean> {
  try { return JSON.parse(localStorage.getItem(COLLAPSED_KEY) || '{}'); }
  catch { return {}; }
}

function loadWorkspace(): string {
  return localStorage.getItem(WORKSPACE_KEY) || 'options';
}

function getModeInfo(mode: string) {
  if (mode === 'LIVE' || mode === 'ZERODHA_LIVE') return { label: 'Live', color: 'bg-red-500' };
  if (mode === 'DRY_RUN' || mode === 'ZERODHA_DRY_RUN') return { label: 'Dry Run', color: 'bg-amber-500' };
  return { label: 'Paper', color: 'bg-emerald-500' };
}

const Sidebar: React.FC<SidebarProps> = ({ open }) => {
  const location = useLocation();
  const [executionMode, setExecutionMode] = useState('PAPER_TRADING');
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>(loadCollapsed);
  const [activeWorkspace, setActiveWorkspace] = useState<string>(loadWorkspace);

  useEffect(() => {
    loadExecutionMode();
    const handler = () => loadExecutionMode();
    window.addEventListener('broker-settings-changed', handler);
    return () => window.removeEventListener('broker-settings-changed', handler);
  }, []);

  const loadExecutionMode = async () => {
    try {
      const response = await settingsAPI.getZerodhaSettings();
      const data = response.data || response;
      setExecutionMode(data.execution_mode || 'PAPER_TRADING');
    } catch { /* silent */ }
  };

  const toggleSection = (id: string) => {
    setCollapsed((prev) => {
      const next = { ...prev, [id]: !prev[id] };
      localStorage.setItem(COLLAPSED_KEY, JSON.stringify(next));
      return next;
    });
  };

  const switchWorkspace = (id: string) => {
    setActiveWorkspace(id);
    localStorage.setItem(WORKSPACE_KEY, id);
  };

  const workspace = WORKSPACES.find((w) => w.id === activeWorkspace) ?? WORKSPACES[0];
  const visibleSections = NAV_SECTIONS.filter((s) => workspace.sectionIds.includes(s.id));
  const mode = getModeInfo(executionMode);

  return (
    <TooltipProvider delayDuration={0}>
      <aside
        className={cn(
          'sidebar-root flex flex-col border-r border-border transition-all duration-300 ease-in-out',
          open ? 'w-56' : 'w-[52px]'
        )}
      >
        {/* Logo */}
        <div className={cn('flex h-14 shrink-0 items-center border-b border-border', open ? 'px-4 gap-3' : 'justify-center')}>
          <Link to="/" className="flex items-center gap-3 min-w-0">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-500 to-blue-500 shadow-sm">
              <TrendingUp className="h-3.5 w-3.5 text-white" />
            </div>
            {open && (
              <div className="min-w-0 leading-none">
                <p className="font-bold text-sm tracking-tight text-foreground">FastTrade</p>
                <p className="text-[10px] text-muted-foreground mt-0.5">Pro Platform</p>
              </div>
            )}
          </Link>
        </div>

        {/* Workspace switcher */}
        <div className={cn(
          'shrink-0 border-b border-border',
          open ? 'px-2 py-2' : 'py-2 flex flex-col items-center gap-1'
        )}>
          {open ? (
            <div className="flex gap-1">
              {WORKSPACES.map((ws) => {
                const Icon = ws.icon;
                const isActive = ws.id === activeWorkspace;
                return (
                  <Tooltip key={ws.id}>
                    <TooltipTrigger asChild>
                      <button
                        onClick={() => switchWorkspace(ws.id)}
                        className={cn(
                          'flex flex-1 flex-col items-center gap-0.5 rounded-md py-1.5 px-1 transition-all duration-150 text-[10px] font-medium',
                          isActive
                            ? `bg-primary/10 ${ws.color} border border-primary/20`
                            : 'text-muted-foreground hover:text-foreground hover:bg-accent/60'
                        )}
                      >
                        <Icon className="h-3.5 w-3.5" />
                        <span>{ws.label}</span>
                      </button>
                    </TooltipTrigger>
                    <TooltipContent side="bottom" className="text-xs">{ws.label}</TooltipContent>
                  </Tooltip>
                );
              })}
            </div>
          ) : (
            WORKSPACES.map((ws) => {
              const Icon = ws.icon;
              const isActive = ws.id === activeWorkspace;
              return (
                <Tooltip key={ws.id}>
                  <TooltipTrigger asChild>
                    <button
                      onClick={() => switchWorkspace(ws.id)}
                      className={cn(
                        'flex h-8 w-8 items-center justify-center rounded-md transition-all duration-150',
                        isActive
                          ? `bg-primary/10 ${ws.color} border border-primary/20`
                          : 'text-muted-foreground hover:text-foreground hover:bg-accent/60'
                      )}
                    >
                      <Icon className="h-3.5 w-3.5" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="right" className="text-xs">{ws.label}</TooltipContent>
                </Tooltip>
              );
            })
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-3 no-scrollbar">
          {visibleSections.map((section, sectionIdx) => {
            const isCollapsed = !!collapsed[section.id];

            return (
              <div key={section.id} className={sectionIdx > 0 ? 'mt-1' : ''}>
                {open && (
                  <button
                    onClick={() => toggleSection(section.id)}
                    className="flex w-full items-center justify-between px-3 py-1.5 group"
                  >
                    <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/60 group-hover:text-muted-foreground transition-colors">
                      {section.label}
                    </span>
                    <ChevronRight
                      className={cn(
                        'h-3 w-3 text-muted-foreground/40 transition-transform duration-200',
                        !isCollapsed && 'rotate-90'
                      )}
                    />
                  </button>
                )}

                {!open && sectionIdx > 0 && (
                  <div className="mx-3 my-2 h-px bg-border/60" />
                )}

                {(!isCollapsed || !open) && (
                  <div className="px-2 space-y-0.5">
                    {section.items.map((item) => {
                      const Icon = item.icon;
                      const active = isActiveRoute(location.pathname, item.path);

                      const linkEl = (
                        <Link
                          key={item.path}
                          to={item.path}
                          className={cn(
                            'sidebar-item group relative flex items-center rounded-md transition-all duration-150',
                            open ? 'gap-2.5 px-2.5 py-1.5' : 'justify-center px-0 py-2',
                            active
                              ? 'sidebar-item-active bg-primary/10 text-primary'
                              : 'text-muted-foreground hover:text-foreground hover:bg-accent/60'
                          )}
                        >
                          {active && (
                            <span className="absolute left-0 top-1/2 -translate-y-1/2 h-4 w-0.5 rounded-full bg-primary" />
                          )}
                          <Icon className={cn('shrink-0 transition-colors h-4 w-4', active ? 'text-primary' : '')} />
                          {open && <span className="truncate text-sm font-medium">{item.label}</span>}
                        </Link>
                      );

                      if (!open) {
                        return (
                          <Tooltip key={item.path}>
                            <TooltipTrigger asChild>{linkEl}</TooltipTrigger>
                            <TooltipContent side="right" className="text-xs">{item.label}</TooltipContent>
                          </Tooltip>
                        );
                      }

                      return linkEl;
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </nav>

        {/* Footer — trading mode */}
        <div className="shrink-0 border-t border-border p-2">
          {open ? (
            <div className="flex items-center gap-2.5 rounded-md px-2.5 py-2 bg-muted/40">
              <span className={cn('h-1.5 w-1.5 rounded-full shrink-0 animate-pulse', mode.color)} />
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium text-foreground truncate">{mode.label} Mode</p>
                <p className="text-[10px] text-muted-foreground">System active</p>
              </div>
            </div>
          ) : (
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="flex justify-center py-1">
                  <span className={cn('h-2 w-2 rounded-full animate-pulse', mode.color)} />
                </div>
              </TooltipTrigger>
              <TooltipContent side="right" className="text-xs">{mode.label} Mode</TooltipContent>
            </Tooltip>
          )}
        </div>
      </aside>
    </TooltipProvider>
  );
};

export default Sidebar;
