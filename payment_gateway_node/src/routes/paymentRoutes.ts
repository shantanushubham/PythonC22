import { Router } from "express";
import { createTransaction, getTransactionStatus } from "../controllers/paymentController";

const router = Router();

// Initiate a credit/debit transaction against a bank account.
// Simulates gateway processing with a 25% random failure rate.
router.post("/transactions", createTransaction);

// Look up the result of a previously processed transaction (in-memory only).
router.get("/transactions/:transactionId", getTransactionStatus);

export default router;
