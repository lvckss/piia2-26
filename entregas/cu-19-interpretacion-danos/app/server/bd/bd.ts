import postgres from "postgres";

const isProd = process.env.NODE_ENV === "production";
const { DATABASE_URL } = process.env;

if (!DATABASE_URL) {
  throw new Error("DATABASE_URL no está definida");
}

const debug = !isProd
  ? (connection: any, query: string, params: any[]) => {
      const pid = connection?.processID ?? "conn";
      console.log(`[pg:${pid}] QUERY:\n${query}`);
      console.log(`[pg:${pid}] PARAMS:`, params);
    }
  : undefined;

const sql = postgres(DATABASE_URL, {
  ssl: isProd ? "require" : false,
  debug,
  max: 10,
  idle_timeout: 20,
  connect_timeout: 10,
});

await sql`select 1`;
console.log("Database connected successfully!");

export default sql;