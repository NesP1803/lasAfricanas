import { BrowserRouter, Navigate, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Layout from './components/Layout';
import Configuracion from './pages/Configuracion';
import MiPerfil from './pages/MiPerfil';
import Notificaciones from './pages/Notificaciones';
import Listados from './pages/Listados';
import Articulos from './pages/Articulos';
import Taller from './pages/Taller';
import Ventas from './pages/Ventas';
import CuentasDia from './pages/CuentasDia';
import DetallesCuentas from './pages/DetallesCuentas';
import Facturas from './pages/Facturas';
import Remisiones from './pages/Remisiones';
import Caja from './pages/Caja';
import IntercambioDatosPage from './pages/intercambio/IntercambioDatosPage';
import { NotificationProvider } from './contexts/NotificationContext';
import NotasCreditoPage from './modules/notasCredito/pages/NotasCreditoPage';
import CrearNotaCreditoPage from './modules/notasCredito/pages/CrearNotaCreditoPage';
import DocumentosSoportePage from './modules/documentosSoporte/pages/DocumentosSoportePage';
import CrearDocumentoSoportePage from './modules/documentosSoporte/pages/CrearDocumentoSoportePage';

function App() {
  return (
    <AuthProvider>
      <NotificationProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/" element={<Layout />}>
              <Route index element={<Dashboard />} />
              <Route path="configuracion" element={<Configuracion />} />
              <Route path="mi-perfil" element={<MiPerfil />} />
              <Route path="notificaciones" element={<Notificaciones />} />
              <Route path="listados" element={<Listados />} />
              <Route path="articulos" element={<Articulos />} />
              <Route path="taller" element={<Taller />} />
              <Route path="ventas" element={<Ventas />} />
              <Route path="ventas/cuentas-dia" element={<CuentasDia />} />
              <Route path="ventas/detalles-cuentas" element={<DetallesCuentas />} />
              <Route path="facturacion/facturas" element={<Facturas />} />
              <Route path="facturacion-electronica" element={<Navigate to="/facturacion/facturas" replace />} />
              <Route path="notas-credito" element={<NotasCreditoPage />} />
              <Route path="notas-credito/crear" element={<CrearNotaCreditoPage />} />
              <Route path="documentos-soporte" element={<DocumentosSoportePage />} />
              <Route path="documentos-soporte/crear" element={<CrearDocumentoSoportePage />} />
              <Route path="facturacion/remisiones" element={<Remisiones />} />
              <Route path="facturacion/caja" element={<Caja />} />
              <Route path="intercambio-datos" element={<IntercambioDatosPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </NotificationProvider>
    </AuthProvider>
  );
}

export default App;
