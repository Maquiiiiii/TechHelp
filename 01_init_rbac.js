/**
 * TechHelp - Script de Inicialización de Seguridad para MongoDB (RBAC)
 * Archivo: 01_init_rbac.js
 *
 *Propósito:
 * 1. Establece la base de datos 'techhelp_db'.
 * 2. Crea un rol personalizado 'auditLoggerRole' que SOLO permite insertar y leer
 * documentos en la colección 'audit_logs', garantizando su inmutabilidad (RNF-SEG-004).
 * 3. Crea un usuario de aplicación 'techhelp_app_user' con dos conjuntos de permisos:
 * - Permisos de lectura/escritura estándar ('readWrite') en toda la base de datos.
 * - Asigna el rol 'auditLoggerRole' específicamente para la colección de auditoría.
 * MongoDB prioriza los permisos más específicos, por lo que las restricciones de
 * 'auditLoggerRole' sobre 'audit_logs' prevalecerán sobre los permisos generales de 'readWrite'.
 *
 * Ejecución:
 * Este script se ejecuta automáticamente al iniciar el contenedor de Docker de MongoDB
 * si se monta en el directorio /docker-entrypoint-initdb.d/.
 */

db = db.getSiblingDB('techhelp_db');

print("--- Iniciando script de configuración RBAC para TechHelp ---");

// Paso 1: Crear el Rol Personalizado de Solo Inserción/Lectura para la Auditoría Forense
print("Creando rol 'auditLoggerRole' para la colección 'audit_logs'...");
db.createRole({
  role: "auditLoggerRole",
  privileges: [
    {
      resource: { db: "techhelp_db", collection: "audit_logs" },
      actions: [ "insert", "find" ]
    }
  ],
  roles: []
});
print("Rol 'auditLoggerRole' creado exitosamente.");

// Paso 2: Crear el Usuario de la Aplicación con roles combinados
print("Creando usuario de aplicación 'techhelp_app_user'...");
db.createUser({
  user: "techhelp_app_user",
  pwd: "CHANGE_THIS_STRONG_PASSWORD", // ¡IMPORTANTE! Cambiar esta contraseña en producción.
  roles: [
    { role: "readWrite", db: "techhelp_db" },
    { role: "auditLoggerRole", db: "techhelp_db" }
  ]
});

print("Usuario 'techhelp_app_user' creado y configurado exitosamente.");
print("--- Configuración RBAC finalizada. ---");