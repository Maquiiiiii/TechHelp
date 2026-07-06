const mongoUri = process.env.MONGO_URI || process.env.MONGO_URL || "mongodb://admin:admin123@localhost:27017/techhelp?authSource=admin";
let databaseName = "techhelp";

try {
  const parsed = new URL(mongoUri);
  const path = parsed.pathname.replace(/^\//, "");
  if (path) {
    databaseName = path.split("?")[0];
  }
} catch (e) {
  // Ignorar y usar valor por defecto
}

const config = {
  mongodb: {
    // Configuración de la conexión a MongoDB
    url: mongoUri,
    databaseName: databaseName,
    options: {
      useNewUrlParser: true,
      useUnifiedTopology: true,
    }
  },
  // Directorio donde se guardarán los archivos de migración
  migrationsDir: "migrations",
  // Colección de changelog en MongoDB para registrar las migraciones ejecutadas
  changelogCollectionName: "changelog",
  // Extensión de los archivos de migración (.js o .ts)
  migrationFileExtension: ".js",
  // Habilitar o deshabilitar hashes para verificación de cambios
  useFileHash: false,
  // Sistema de módulos a utilizar ('commonjs' o 'esm')
  moduleSystem: "commonjs"
};

module.exports = config;