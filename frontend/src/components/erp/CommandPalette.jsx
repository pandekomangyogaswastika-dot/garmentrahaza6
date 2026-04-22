/**
 * CommandPalette (Cmd+K) — Tahap 5 A11y & Quick Nav.
 * Global module search & portal switcher accessible via keyboard.
 */
import { useState, useEffect } from 'react';
import {
  CommandDialog, CommandInput, CommandList, CommandEmpty,
  CommandGroup, CommandItem, CommandSeparator, CommandShortcut,
} from '@/components/ui/command';
import {
  Factory, Warehouse, DollarSign, Users, BarChart3,
  Sun, Moon, Monitor, Terminal, LogOut, Package,
} from 'lucide-react';
import { useTheme } from '@/components/theme/ThemeProvider';

const PORTAL_ITEMS = [
  { id: 'management', label: 'Portal Management', icon: BarChart3 },
  { id: 'production', label: 'Portal Produksi',   icon: Factory },
  { id: 'warehouse',  label: 'Portal Gudang',     icon: Warehouse },
  { id: 'finance',    label: 'Portal Finance',    icon: DollarSign },
  { id: 'hr',         label: 'Portal HR',         icon: Users },
];

/**
 * Props:
 *   open, onOpenChange, currentPortal,
 *   onSelectPortal(portalId),
 *   onSelectModule(moduleId),
 *   moduleSuggestions: [{id, label, portal, icon}],
 *   onLogout
 */
export function CommandPalette({
  open, onOpenChange, currentPortal,
  onSelectPortal, onSelectModule, onLogout,
  moduleSuggestions = [],
}) {
  const { theme, setTheme } = useTheme();

  // Keyboard shortcut: Cmd/Ctrl+K to toggle
  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key?.toLowerCase() === 'k') {
        e.preventDefault();
        onOpenChange(!open);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onOpenChange]);

  const close = () => onOpenChange(false);

  const handlePortal = (pid) => {
    onSelectPortal?.(pid);
    close();
  };

  const handleModule = (mid) => {
    onSelectModule?.(mid);
    close();
  };

  const handleTheme = (mode) => {
    setTheme(mode);
  };

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput placeholder="Ketik perintah atau cari..." data-testid="cmdk-input" />
      <CommandList>
        <CommandEmpty>Tidak ada hasil ditemukan.</CommandEmpty>

        <CommandGroup heading="Pindah Portal">
          {PORTAL_ITEMS.map(p => {
            const Icon = p.icon;
            return (
              <CommandItem
                key={p.id}
                onSelect={() => handlePortal(p.id)}
                disabled={p.id === currentPortal}
                data-testid={`cmdk-portal-${p.id}`}
              >
                <Icon className="mr-2 w-4 h-4" />
                <span>{p.label}</span>
                {p.id === currentPortal && (
                  <CommandShortcut className="text-[hsl(var(--primary))] font-semibold">aktif</CommandShortcut>
                )}
              </CommandItem>
            );
          })}
        </CommandGroup>

        {moduleSuggestions.length > 0 && (
          <>
            <CommandSeparator />
            <CommandGroup heading="Navigasi Menu">
              {moduleSuggestions.map((m) => {
                const Icon = m.icon || Package;
                return (
                  <CommandItem
                    key={m.id}
                    onSelect={() => handleModule(m.id)}
                    data-testid={`cmdk-module-${m.id}`}
                  >
                    <Icon className="mr-2 w-4 h-4 text-foreground/60" />
                    <span>{m.label}</span>
                    {m.portal && <CommandShortcut className="text-[10px] uppercase tracking-wider">{m.portal}</CommandShortcut>}
                  </CommandItem>
                );
              })}
            </CommandGroup>
          </>
        )}

        <CommandSeparator />
        <CommandGroup heading="Tampilan">
          <CommandItem onSelect={() => handleTheme('light')} data-testid="cmdk-theme-light">
            <Sun className="mr-2 w-4 h-4" />
            <span>Mode Terang</span>
            {theme === 'light' && <CommandShortcut>aktif</CommandShortcut>}
          </CommandItem>
          <CommandItem onSelect={() => handleTheme('dark')} data-testid="cmdk-theme-dark">
            <Moon className="mr-2 w-4 h-4" />
            <span>Mode Gelap</span>
            {theme === 'dark' && <CommandShortcut>aktif</CommandShortcut>}
          </CommandItem>
          <CommandItem onSelect={() => handleTheme('classic')} data-testid="cmdk-theme-classic">
            <Terminal className="mr-2 w-4 h-4" />
            <span>Mode Classic (Visual Studio)</span>
            {theme === 'classic' && <CommandShortcut>aktif</CommandShortcut>}
          </CommandItem>
          <CommandItem onSelect={() => handleTheme('system')} data-testid="cmdk-theme-system">
            <Monitor className="mr-2 w-4 h-4" />
            <span>Ikut Sistem</span>
            {theme === 'system' && <CommandShortcut>aktif</CommandShortcut>}
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />
        <CommandGroup heading="Akun">
          <CommandItem onSelect={() => { onLogout?.(); close(); }} data-testid="cmdk-logout">
            <LogOut className="mr-2 w-4 h-4" />
            <span>Keluar dari sistem</span>
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
