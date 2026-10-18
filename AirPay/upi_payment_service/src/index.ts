import { createApp } from "./app.js";
import { loadSettings } from "./config.js";
import { buildDependencies } from "./container.js";
import { consoleLogger } from "./logger.js";
import { SqlitePaymentRepository } from "./repositories/sqlitePaymentRepository.js";
import { systemClock } from "./utils/clock.js";

const settings = loadSettings();
const repository = new SqlitePaymentRepository(settings.dbPath);

const app = createApp(
  buildDependencies({ settings, repository, clock: systemClock, logger: consoleLogger }),
);

const server = app.listen(settings.port, () => {
  consoleLogger.info("upi_payment_service_started", {
    url: `http://localhost:${settings.port}`,
    docs: `http://localhost:${settings.port}/docs`,
    approval_delay_ms: settings.approvalDelayMs,
  });
});

function shutdown(signal: string): void {
  consoleLogger.info("shutting_down", { signal });
  server.close(() => {
    repository.close();
    process.exit(0);
  });
}

process.on("SIGINT", () => shutdown("SIGINT"));
process.on("SIGTERM", () => shutdown("SIGTERM"));
