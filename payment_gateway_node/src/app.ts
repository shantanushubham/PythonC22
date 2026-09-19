import express, { Application, Request, Response } from "express";
import paymentRoutes from "./routes/paymentRoutes";
import { notFoundHandler, errorHandler } from "./middleware/errorHandler";

export function createApp(): Application {
  const app = express();

  app.use(express.json());

  app.get("/health", (_req: Request, res: Response) => {
    res.status(200).json({ status: "ok" });
  });

  app.use("/api", paymentRoutes);

  app.use(notFoundHandler);
  app.use(errorHandler);

  return app;
}
