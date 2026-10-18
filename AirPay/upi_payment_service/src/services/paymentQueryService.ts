/** Looks up payments that were already started. */

import { PaymentNotFoundError } from "../errors.js";
import type { PaymentMapper } from "../mappers/paymentMapper.js";
import type { PaymentView } from "../models/payment.js";
import type { PaymentReader } from "../repositories/paymentRepository.js";
import type { Clock } from "../utils/clock.js";

/** Depends on `PaymentReader` only, so it cannot create or change payments. */
export class PaymentQueryService {
  private readonly reader: PaymentReader;
  private readonly mapper: PaymentMapper;
  private readonly clock: Clock;

  constructor(reader: PaymentReader, mapper: PaymentMapper, clock: Clock) {
    this.reader = reader;
    this.mapper = mapper;
    this.clock = clock;
  }

  async get(transactionId: string): Promise<PaymentView> {
    const stored = await this.reader.findById(transactionId);
    if (stored === undefined) {
      throw new PaymentNotFoundError(transactionId);
    }
    return this.mapper.toView(stored.payment, this.clock.now());
  }
}
