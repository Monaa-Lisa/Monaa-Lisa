export default {
  migrate: {
    // Stelle sicher, dass der Datasource-Name hier mit dem Namen in `schema.prisma` übereinstimmt: "db"
    datasource: {
      name: 'db',
      provider: 'postgres',
      url: process.env.DATABASE_URL,
    },
    // Optional: mapping für CLI/Tools, falls mehrere URLs gebraucht werden
    datasourceUrls: {
      db: process.env.DATABASE_URL,
    },
  },
};