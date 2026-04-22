import { useState, useEffect, useCallback, Suspense } from 'react';
import './App.css';
import Login from './components/erp/Login';
import PortalSelector from './components/erp/PortalSelector';
import PortalShell from './components/erp/PortalShell';
import OperatorView from './components/erp/OperatorView';
import ShopFloorTV from './components/erp/ShopFloorTV';
import { MODULE_REGISTRY, DEFAULT_MODULE } from './components/erp/moduleRegistry';
import { ThemeProvider } from './components/theme/ThemeProvider';
import { Toaster } from './components/ui/sonner';

// Default module untuk tiap portal
const PORTAL_DEFAULT_MODULE = {
  management: 'management-dashboard',
  production: 'production-dashboard',
  warehouse:  'warehouse-dashboard',
  finance:    'finance-dashboard',
  hr:         'hr-dashboard',
};

const VALID_PORTALS = Object.keys(PORTAL_DEFAULT_MODULE);

const ModuleSpinner = () => (
  <div className="flex items-center justify-center h-64">
    <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-[hsl(var(--primary))]" />
  </div>
);

// Deteksi apakah URL saat ini /operator
const isOperatorRoute = () => {
  if (typeof window === 'undefined') return false;
  return window.location.pathname.startsWith('/operator');
};

// Deteksi apakah URL saat ini /tv
const isTVRoute = () => {
  if (typeof window === 'undefined') return false;
  return window.location.pathname.startsWith('/tv');
};

function App() {
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedPortal, setSelectedPortal] = useState(null);
  const [currentModule, setCurrentModule] = useState('management-dashboard');
  const [operatorRoute, setOperatorRoute] = useState(isOperatorRoute());
  const [tvRoute, setTVRoute] = useState(isTVRoute());

  // Sync operatorRoute on popstate / navigation
  useEffect(() => {
    const onPop = () => {
      setOperatorRoute(isOperatorRoute());
      setTVRoute(isTVRoute());
    };
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  // Restore session
  useEffect(() => {
    const savedToken = localStorage.getItem('erp_token');
    const savedUser = localStorage.getItem('erp_user');
    const savedPortal = localStorage.getItem('erp_portal');
    if (savedToken && savedUser) {
      try {
        setToken(savedToken);
        const parsed = JSON.parse(savedUser);
        setUser(parsed);
        if (savedPortal && VALID_PORTALS.includes(savedPortal)) {
          setSelectedPortal(savedPortal);
          setCurrentModule(PORTAL_DEFAULT_MODULE[savedPortal]);
        }
      } catch (e) {
        localStorage.removeItem('erp_token');
        localStorage.removeItem('erp_user');
        localStorage.removeItem('erp_portal');
      }
    }
    setLoading(false);
  }, []);

  const handleLogin = useCallback((tokenData, userData) => {
    setToken(tokenData);
    setUser(userData);
    localStorage.setItem('erp_token', tokenData);
    localStorage.setItem('erp_user', JSON.stringify(userData));
    // Role operator → redirect ke Operator View
    if ((userData.role || '').toLowerCase() === 'operator') {
      window.history.pushState({}, '', '/operator');
      setOperatorRoute(true);
    } else {
      setSelectedPortal(null);
      setCurrentModule('management-dashboard');
    }
  }, []);

  const handleLogout = useCallback(() => {
    setToken(null);
    setUser(null);
    setSelectedPortal(null);
    setCurrentModule('management-dashboard');
    localStorage.removeItem('erp_token');
    localStorage.removeItem('erp_user');
    localStorage.removeItem('erp_portal');
    if (isOperatorRoute()) {
      window.history.pushState({}, '', '/');
      setOperatorRoute(false);
    }
  }, []);

  const handleSelectPortal = useCallback((portalId) => {
    if (!VALID_PORTALS.includes(portalId)) return;
    setSelectedPortal(portalId);
    setCurrentModule(PORTAL_DEFAULT_MODULE[portalId]);
    localStorage.setItem('erp_portal', portalId);
  }, []);

  // Hybrid-nav support: switch portal dari pill-nav tanpa balik ke selector
  const handlePortalChange = useCallback((portalId) => {
    if (!VALID_PORTALS.includes(portalId)) return;
    setSelectedPortal(portalId);
    setCurrentModule(PORTAL_DEFAULT_MODULE[portalId]);
    localStorage.setItem('erp_portal', portalId);
  }, []);

  const handleBackToPortals = useCallback(() => {
    setSelectedPortal(null);
    setCurrentModule('management-dashboard');
    localStorage.removeItem('erp_portal');
  }, []);

  const handleNavigate = useCallback((moduleId) => {
    setCurrentModule(moduleId);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-[hsl(var(--background))]">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-[hsl(var(--primary))]"></div>
      </div>
    );
  }

  // TV Mode (Phase 18C) — public, no auth required
  if (tvRoute) {
    return <ShopFloorTV />;
  }

  if (!token || !user) return <Login onLogin={handleLogin} />;

  // Operator View (mobile) on /operator URL OR if user role is operator
  if (operatorRoute || (user.role || '').toLowerCase() === 'operator') {
    return <OperatorView user={user} token={token} onLogout={handleLogout} />;
  }

  if (!selectedPortal) {
    return <PortalSelector user={user} onSelectPortal={handleSelectPortal} onLogout={handleLogout} />;
  }

  const userPerms = user?.permissions || [];
  const hasPerm = (key) => {
    const role = (user?.role || '').toLowerCase();
    if (['superadmin', 'admin', 'owner'].includes(role)) return true;
    return userPerms.includes(key) || userPerms.includes(key.split('.')[0] + '.*') || userPerms.includes('*');
  };

  const ModuleComponent = MODULE_REGISTRY[currentModule] || DEFAULT_MODULE;

  return (
    <PortalShell
      portal={selectedPortal}
      user={user}
      token={token}
      onBack={handleBackToPortals}
      onLogout={handleLogout}
      onPortalChange={handlePortalChange}
      currentModule={currentModule}
      onModuleChange={setCurrentModule}
    >
      <Suspense fallback={<ModuleSpinner />}>
        <ModuleComponent
          token={token}
          user={user}
          userRole={user?.role}
          hasPerm={hasPerm}
          onNavigate={handleNavigate}
          moduleId={currentModule}
        />
      </Suspense>
    </PortalShell>
  );
}

export default function AppWithTheme() {
  return (
    <ThemeProvider defaultTheme="system">
      {/* Ambient decorative layers — pointer-events none, behind everything */}
      <div className="starfield" aria-hidden="true" />
      <div className="noise-overlay fixed inset-0 pointer-events-none" aria-hidden="true" />
      <App />
      <Toaster position="top-right" richColors closeButton />
    </ThemeProvider>
  );
}
