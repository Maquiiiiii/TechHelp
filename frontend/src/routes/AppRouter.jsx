import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import ProtectedRoute from '../components/ProtectedRoute';
import DashboardLayout from '../layouts/DashboardLayout';
import Login from '../pages/Login';
import Dashboard from '../pages/Dashboard';
import TicketsList from '../pages/TicketsList';
import CreateTicket from '../pages/CreateTicket';
import TicketDetail from '../pages/TicketDetail';
import Organizations from '../pages/Organizations';
import Technicians from '../pages/Technicians';
import Audit from '../pages/Audit';
import ForcePasswordChange from '../pages/ForcePasswordChange';
import Availability from '../pages/Availability';
import FeedbackSurvey from '../pages/FeedbackSurvey';
import Survey from '../pages/Survey';
import AccountBlocked from '../pages/AccountBlocked';

const AppRouter = () => {
  return (
    <BrowserRouter>
      <Routes>
        {/* Rutas publicas */}
        <Route path="/login" element={<Login />} />
        <Route path="/feedback" element={<FeedbackSurvey />} />
        <Route path="/survey" element={<Survey />} />
        <Route path="/blocked" element={<AccountBlocked />} />

        {/* Página independiente de cambio de contraseña requerida */}
        <Route 
          path="/force-password-change" 
          element={
            <ProtectedRoute>
              <ForcePasswordChange />
            </ProtectedRoute>
          } 
        />

        {/* Rutas protegidas del panel de control */}
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <DashboardLayout />
            </ProtectedRoute>
          }
        >
          {/* Index Route se representa dentro del Outlet de DashboardLayout */}
          <Route index element={<Dashboard />} />
          <Route path="change-password" element={<ForcePasswordChange />} />

          
          {/* Rutas del módulo de billetes de soporte */}
          <Route path="tickets" element={<TicketsList />} />
          <Route path="tickets/assigned" element={<TicketsList />} />
          <Route path="tickets/all" element={<TicketsList />} />
          <Route path="tickets/history" element={<TicketsList />} />
          <Route 
            path="tickets/new" 
            element={
              <ProtectedRoute allowedRoles={['Administrador', 'Cliente']}>
                <CreateTicket />
              </ProtectedRoute>
            } 
          />
          <Route path="tickets/:id" element={<TicketDetail />} />

          {/* Rutas de gestion de administracion */}
          <Route path="organizations" element={<Organizations />} />
          <Route path="technicians" element={<Technicians />} />
          <Route path="audit" element={<Audit />} />
          <Route 
            path="availability" 
            element={
              <ProtectedRoute allowedRoles={['Tecnico']}>
                <Availability />
              </ProtectedRoute>
            } 
          />
        </Route>

        {/* Redirección general alternativa a /iniciar sesión */}
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
};

export default AppRouter;