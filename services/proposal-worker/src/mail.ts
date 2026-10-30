/**
 * Outbound e-mail for login codes, access requests and approvals.
 * Message text is never logged; provider errors are reduced to a fixed code.
 */
export interface MailMessage { to: string; subject: string; text: string }
export interface Mailer { send(message: MailMessage): Promise<void> }

export class MailError extends Error {
  constructor() { super("mail_failed"); }
}

export const RESEND_ENDPOINT = "https://api.resend.com/emails";

/** Resend HTTP API. The key is a Worker secret; the sender is a reviewed variable. */
export class ResendMailer implements Mailer {
  constructor(private readonly apiKey: string, private readonly from: string, private readonly fetcher: typeof fetch = (input, init) => fetch(input, init)) {}

  async send(message: MailMessage) {
    let response: Response;
    try {
      response = await this.fetcher(RESEND_ENDPOINT, {
        method: "POST", redirect: "manual", signal: AbortSignal.timeout(15_000),
        headers: { authorization: `Bearer ${this.apiKey}`, "content-type": "application/json" },
        body: JSON.stringify({ from: this.from, to: [message.to], subject: message.subject, text: message.text }),
      });
    } catch {
      throw new MailError();
    }
    await response.body?.cancel().catch(() => undefined);
    if (response.status < 200 || response.status >= 300) throw new MailError();
  }
}

/** Null when sending is not configured: callers fail closed with `mail_unavailable`. */
export function configuredMailer(env: { RESEND_API_KEY?: string; MAIL_FROM?: string }, fetcher?: typeof fetch): Mailer | null {
  const from = env.MAIL_FROM?.trim() ?? "";
  if (!env.RESEND_API_KEY || !from || /[\r\n]/.test(from) || !/@[^@\s>]+\.[^@\s>]+>?$/.test(from)) return null;
  return new ResendMailer(env.RESEND_API_KEY, from, fetcher);
}
