db = db.getSiblingDB('techhelp_db');

// Cree la función personalizada para los registros de auditoría que permitan estrictamente "insertar" y "buscar".
// y evita 'actualizar', 'eliminar' o 'dropCollection'
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

// Cree una función de aplicación personalizada para operaciones estándar de lectura y escritura en otras colecciones.
// excluyendo 'audit_logs' para garantizar una verdadera inmutabilidad a nivel del motor de base de datos.
db.createRole({
  role: "appStandardReadWriteRole",
  privileges: [
    {
      resource: { db: "techhelp_db", collection: "organizations" },
      actions: [ "find", "insert", "update", "remove" ]
    },
    {
      resource: { db: "techhelp_db", collection: "tickets" },
      actions: [ "find", "insert", "update", "remove" ]
    },
    {
      resource: { db: "techhelp_db", collection: "technicians" },
      actions: [ "find", "insert", "update", "remove" ]
    },
    {
      resource: { db: "techhelp_db", collection: "users" },
      actions: [ "find", "insert", "update", "remove" ]
    },
    {
      resource: { db: "techhelp_db", collection: "survey_tokens" },
      actions: [ "find", "insert", "update", "remove" ]
    },
    {
      resource: { db: "techhelp_db", collection: "satisfaccion_cliente" },
      actions: [ "find", "insert", "update", "remove" ]
    }
  ],
  roles: []
});

// Cree el usuario de la aplicación vinculada al auditLoggerRole restringido y al rol de colecciones estándar.
db.createUser({
  user: "techhelp_app_user",
  pwd: "app_secure_password_2026",
  roles: [
    { role: "auditLoggerRole", db: "techhelp_db" },
    { role: "appStandardReadWriteRole", db: "techhelp_db" }
  ]
});