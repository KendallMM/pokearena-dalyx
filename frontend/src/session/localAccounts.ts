/*
 * Cuentas guardadas solo en este navegador. El backend todavía no tiene registro ni
 * inicio de sesión: cuando existan, esto se reemplaza por llamadas a la API. No da
 * acceso a la API, que sigue pidiendo su propio token.
 */
const ACCOUNTS_KEY = "pokearena.accounts";
const CURRENT_KEY = "pokearena.session.account";
const HASH_ITERATIONS = 100_000;

interface StoredAccount {
  id: string;
  name: string;
  email: string;
  salt: string;
  passwordHash: string;
}

export interface Account {
  id: string;
  name: string;
  email: string;
}

/* Problema que se le puede mostrar a la persona tal cual. */
export class AccountError extends Error {}

function toHex(bytes: Uint8Array): string {
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

function fromHex(hex: string): Uint8Array {
  return Uint8Array.from(hex.match(/../g) ?? [], (pair) => parseInt(pair, 16));
}

function randomHex(): string {
  return toHex(crypto.getRandomValues(new Uint8Array(16)));
}

/* La contraseña nunca se guarda: solo un hash con sal. */
async function hashPassword(password: string, salt: string): Promise<string> {
  if (!crypto.subtle) {
    throw new AccountError(
      "Este navegador solo permite cuentas en una conexión segura (HTTPS o localhost).",
    );
  }
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(password),
    "PBKDF2",
    false,
    ["deriveBits"],
  );
  const bits = await crypto.subtle.deriveBits(
    {
      name: "PBKDF2",
      hash: "SHA-256",
      salt: fromHex(salt),
      iterations: HASH_ITERATIONS,
    },
    key,
    256,
  );
  return toHex(new Uint8Array(bits));
}

function readAccounts(): StoredAccount[] {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(ACCOUNTS_KEY) ?? "[]");
    return Array.isArray(parsed) ? (parsed as StoredAccount[]) : [];
  } catch {
    return [];
  }
}

function writeAccounts(accounts: StoredAccount[]) {
  try {
    localStorage.setItem(ACCOUNTS_KEY, JSON.stringify(accounts));
  } catch {
    throw new AccountError("Este navegador no permite guardar la cuenta.");
  }
}

function normalizeEmail(email: string): string {
  return email.trim().toLowerCase();
}

function toAccount({ id, name, email }: StoredAccount): Account {
  return { id, name, email };
}

export async function registerAccount(input: {
  name: string;
  email: string;
  password: string;
}): Promise<Account> {
  const email = normalizeEmail(input.email);
  if (readAccounts().some((account) => account.email === email)) {
    throw new AccountError("Ya existe una cuenta con ese correo.");
  }
  const salt = randomHex();
  const stored: StoredAccount = {
    id: randomHex(),
    name: input.name.trim(),
    email,
    salt,
    passwordHash: await hashPassword(input.password, salt),
  };
  writeAccounts([...readAccounts(), stored]);
  return toAccount(stored);
}

export async function verifyAccount(email: string, password: string): Promise<Account> {
  const stored = readAccounts().find((a) => a.email === normalizeEmail(email));
  // El mismo mensaje en los dos casos, para no revelar qué correos tienen cuenta.
  const invalid = new AccountError("Correo o contraseña incorrectos.");
  if (!stored) throw invalid;
  if ((await hashPassword(password, stored.salt)) !== stored.passwordHash)
    throw invalid;
  return toAccount(stored);
}

/* La sesión dura lo que la pestaña, igual que el token. */
export function readCurrentAccount(): Account | null {
  try {
    const id = sessionStorage.getItem(CURRENT_KEY);
    const stored = readAccounts().find((account) => account.id === id);
    return stored ? toAccount(stored) : null;
  } catch {
    return null;
  }
}

export function saveCurrentAccount(account: Account | null) {
  try {
    if (account) sessionStorage.setItem(CURRENT_KEY, account.id);
    else sessionStorage.removeItem(CURRENT_KEY);
  } catch {
    // Sin almacenamiento, la sesión dura mientras la página siga abierta.
  }
}
