/** Communication skills — email, webhooks, HTTP API calls. */

import nodemailer from "nodemailer";
import https from "https";
import http from "http";

// ─── Email ───────────────────────────────────────────────

const smtpConfig = {
  host: process.env.SMTP_HOST ?? "",
  port: Number(process.env.SMTP_PORT ?? "587"),
  user: process.env.SMTP_USER ?? "",
  pass: process.env.SMTP_PASS ?? "",
  from: process.env.SMTP_FROM ?? "",
};

export async function sendEmail(to: string, subject: string, body: string): Promise<string> {
  if (!smtpConfig.host || !smtpConfig.user) {
    return "Email not configured. Set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM in Railway.";
  }

  try {
    const transport = nodemailer.createTransport({
      host: smtpConfig.host,
      port: smtpConfig.port,
      secure: smtpConfig.port === 465,
      auth: { user: smtpConfig.user, pass: smtpConfig.pass },
    });

    const info = await transport.sendMail({
      from: smtpConfig.from || smtpConfig.user,
      to,
      subject,
      text: body,
    });

    return `Email sent to ${to}\nMessage ID: ${info.messageId}`;
  } catch (e: any) {
    return `Email failed: ${e.message}`;
  }
}

// ─── Webhooks ────────────────────────────────────────────

export async function sendWebhook(url: string, message: string): Promise<string> {
  try {
    const payload = JSON.stringify({ content: message, text: message });
    const result = await httpPost(url, payload, { "Content-Type": "application/json" });
    return `Webhook sent.\n${result}`;
  } catch (e: any) {
    return `Webhook failed: ${e.message}`;
  }
}

export async function sendDiscord(webhookUrl: string, message: string): Promise<string> {
  try {
    const payload = JSON.stringify({ content: message });
    const result = await httpPost(webhookUrl, payload, { "Content-Type": "application/json" });
    return `Discord message sent.\n${result}`;
  } catch (e: any) {
    return `Discord webhook failed: ${e.message}`;
  }
}

export async function sendSlack(webhookUrl: string, message: string): Promise<string> {
  try {
    const payload = JSON.stringify({ text: message });
    const result = await httpPost(webhookUrl, payload, { "Content-Type": "application/json" });
    return `Slack message sent.\n${result}`;
  } catch (e: any) {
    return `Slack webhook failed: ${e.message}`;
  }
}

// ─── HTTP API ────────────────────────────────────────────

export async function apiCall(
  method: string,
  url: string,
  body?: string,
  headers?: Record<string, string>
): Promise<string> {
  if (!url.startsWith("http")) url = "https://" + url;

  const defaultHeaders: Record<string, string> = {
    "User-Agent": "Agent/0.1",
    "Content-Type": "application/json",
    ...headers,
  };

  return new Promise((resolve) => {
    const u = new URL(url);
    const mod = u.protocol === "https:" ? https : http;
    const opts = {
      hostname: u.hostname,
      port: u.port,
      path: u.pathname + u.search,
      method: method.toUpperCase(),
      headers: defaultHeaders,
      timeout: 15_000,
    };

    const req = mod.request(opts, (res) => {
      let data = "";
      res.setEncoding("utf-8");
      res.on("data", (chunk) => {
        data += chunk;
        if (data.length > 5000) res.destroy();
      });
      res.on("end", () => {
        resolve(`HTTP ${res.statusCode}\n${data.slice(0, 4000)}`);
      });
    });

    req.on("error", (e) => resolve(`Error: ${e.message}`));
    req.on("timeout", () => { req.destroy(); resolve("Request timed out."); });

    if (body) req.write(body);
    req.end();
  });
}

// ─── Helpers ─────────────────────────────────────────────

function httpPost(url: string, body: string, headers: Record<string, string>): Promise<string> {
  return apiCall("POST", url, body, headers);
}
