/**
 * PT Rahaza ERP — RBAC Helper Library (Phase 15)
 *
 * Provides a consistent, reusable API for checking permissions and guarding
 * UI elements across all modules.
 *
 * Usage:
 *   import { hasPerm, useHasPerm, RequirePerm } from '@/lib/rbac';
 *
 *   // imperative check
 *   if (hasPerm(user, 'shipment.manage')) { ... }
 *
 *   // hook (re-renders when user changes)
 *   const canEdit = useHasPerm(user, 'orders.manage');
 *
 *   // declarative guard
 *   <RequirePerm user={user} keys={['shipment.manage']}>
 *     <Button>Dispatch</Button>
 *   </RequirePerm>
 *
 *   // Fallback render when not allowed
 *   <RequirePerm user={user} keys={['audit.view']} fallback={<Locked />}>
 *     <AuditPage />
 *   </RequirePerm>
 */
import { useMemo } from 'react';

// Roles that bypass ALL permission checks (super-users).
const SUPER_ROLES = new Set(['superadmin', 'admin', 'owner']);

/**
 * Low-level permission check.
 *
 * @param {Object} user  - { role, permissions: ['shipment.view', ...] }
 * @param {string|string[]} keys - required permission key(s). Array = OR (any).
 * @returns {boolean}
 */
export function hasPerm(user, keys) {
  if (!user) return false;
  const role = (user.role || '').toLowerCase();
  if (SUPER_ROLES.has(role)) return true;

  const userPerms = user.permissions || [];
  if (userPerms.includes('*')) return true;

  const required = Array.isArray(keys) ? keys : [keys];
  if (required.length === 0) return true; // no requirement = allow

  return required.some((k) => {
    if (userPerms.includes(k)) return true;
    // wildcard module match, e.g. 'shipment.*' matches 'shipment.view'
    const module = k.split('.')[0];
    if (userPerms.includes(`${module}.*`)) return true;
    return false;
  });
}

/**
 * React hook — same as hasPerm but memoised so consumers re-render only
 * when user or keys change.
 */
export function useHasPerm(user, keys) {
  const serialized = Array.isArray(keys) ? keys.join('|') : keys;
  return useMemo(() => hasPerm(user, keys), [
    user?.role,
    (user?.permissions || []).join('|'),
    serialized,
  // eslint-disable-next-line react-hooks/exhaustive-deps
  ]);
}

/**
 * Render `children` only if `user` satisfies `keys`.
 * Optional `fallback` is rendered when access is denied (default: null).
 *
 * @example
 *   <RequirePerm user={user} keys={['shipment.manage']}>
 *     <DispatchButton />
 *   </RequirePerm>
 */
export function RequirePerm({ user, keys, fallback = null, children }) {
  return hasPerm(user, keys) ? children : fallback;
}

/**
 * Classic "locked" fallback component for gated pages.
 * Used by RequirePerm when the user should see a visible "no access" state.
 */
export function PermissionDenied({ missing = [], className = '' }) {
  const missingLabel = Array.isArray(missing) ? missing.join(', ') : missing;
  return (
    <div
      className={`flex flex-col items-center justify-center text-center p-10 rounded-xl border border-[var(--glass-border)] bg-[var(--card-surface)] ${className}`}
      data-testid="permission-denied"
    >
      <div className="w-12 h-12 rounded-full bg-[hsl(var(--destructive)/0.15)] text-[hsl(var(--destructive))] grid place-items-center mb-3">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect width="18" height="11" x="3" y="11" rx="2" ry="2"></rect>
          <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
        </svg>
      </div>
      <h3 className="text-sm font-semibold text-foreground">Akses Ditolak</h3>
      <p className="text-xs text-muted-foreground mt-1 max-w-md">
        Anda tidak memiliki izin untuk mengakses fitur ini.
        {missingLabel ? <> Hubungi admin untuk meminta izin: <code className="font-mono">{missingLabel}</code></> : null}
      </p>
    </div>
  );
}
