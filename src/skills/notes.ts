/** Persistent notes/memory — survives restarts via filesystem. */

import fs from "fs";
import path from "path";

const DATA_DIR = process.env.DATA_DIR ?? "/app/data";
const NOTES_FILE = path.join(DATA_DIR, "notes.json");

interface Note {
  id: number;
  content: string;
  created: string;
}

function load(): Note[] {
  try {
    fs.mkdirSync(DATA_DIR, { recursive: true });
    if (!fs.existsSync(NOTES_FILE)) return [];
    return JSON.parse(fs.readFileSync(NOTES_FILE, "utf-8"));
  } catch {
    return [];
  }
}

function save(notes: Note[]) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
  fs.writeFileSync(NOTES_FILE, JSON.stringify(notes, null, 2));
}

export function addNote(content: string): string {
  const notes = load();
  const id = (notes[notes.length - 1]?.id ?? 0) + 1;
  notes.push({ id, content, created: new Date().toISOString() });
  save(notes);
  return `Note #${id} saved.`;
}

export function listNotes(): string {
  const notes = load();
  if (notes.length === 0) return "No notes yet. Use /note <text> to save one.";
  return notes.map((n) => `#${n.id} — ${n.content}\n  ${n.created}`).join("\n\n");
}

export function getNote(id: string): string {
  const nid = parseInt(id, 10);
  if (isNaN(nid)) return "Invalid note ID.";
  const note = load().find((n) => n.id === nid);
  if (!note) return `Note #${nid} not found.`;
  return `#${note.id}\n${note.content}\n\nCreated: ${note.created}`;
}

export function deleteNote(id: string): string {
  const nid = parseInt(id, 10);
  if (isNaN(nid)) return "Invalid note ID.";
  const notes = load();
  const filtered = notes.filter((n) => n.id !== nid);
  if (filtered.length === notes.length) return `Note #${nid} not found.`;
  save(filtered);
  return `Note #${nid} deleted.`;
}

export function clearNotes(): string {
  save([]);
  return "All notes cleared.";
}
