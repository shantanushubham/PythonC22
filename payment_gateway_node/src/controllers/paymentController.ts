import { Request, Response, NextFunction } from "express";
import { transactionSchema } from "../validators/transactionValidator";
import { processTransaction, getTransactionById } from "../services/paymentGatewayService";

export function createTransaction(req: Request, res: Response, next: NextFunction): void {
  try {
    const parseResult = transactionSchema.safeParse(req.body);

    if (!parseResult.success) {
      res.status(400).json({
        success: false,
        message: "Validation failed",
        errors: parseResult.error.issues.map((issue) => ({
          field: issue.path.join("."),
          message: issue.message,
        })),
      });
      return;
    }

    const record = processTransaction(parseResult.data);

    const httpStatus = record.status === "SUCCESS" ? 200 : 402; // 402 Payment Required for failures
    res.status(httpStatus).json({
      success: record.status === "SUCCESS",
      data: record,
    });
  } catch (err) {
    next(err);
  }
}

export function getTransactionStatus(req: Request, res: Response, next: NextFunction): void {
  try {
    const { transactionId } = req.params;
    const record = getTransactionById(transactionId);

    if (!record) {
      res.status(404).json({
        success: false,
        message: `No transaction found with id '${transactionId}'`,
      });
      return;
    }

    res.status(200).json({
      success: true,
      data: record,
    });
  } catch (err) {
    next(err);
  }
}
