// Reading the game folder in the browser. Chrome and Edge can open a folder and walk it
// ourselves, looking only at match file names: the ~26,000 game pictures in
// Free Fire_64_Data are never opened, so picking is near-instant. Other browsers fall back
// to <input webkitdirectory>, which lists every file first.

import { classify } from "./upload";

/** A match file from the folder. ``read`` returns its current contents each time it's called. */
export type Picked = {
  name: string;
  size: number;
  day: string | null;
  read: () => Promise<File>;
};

type FileHandle = { kind: "file"; name: string; getFile: () => Promise<File> };
type DirHandle = {
  kind: "directory";
  name: string;
  values: () => AsyncIterable<FileHandle | DirHandle>;
  queryPermission?: (o: { mode: "read" }) => Promise<PermissionState>;
  requestPermission?: (o: { mode: "read" }) => Promise<PermissionState>;
};
export type Folder = DirHandle;

type Picker = (o?: { id?: string; mode?: "read" }) => Promise<DirHandle>;

export function canOpenFolder(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof (window as unknown as { showDirectoryPicker?: Picker })
      .showDirectoryPicker === "function"
  );
}

/** Asks for a folder. Null if the person closed the dialog. */
export async function openFolder(): Promise<Folder | null> {
  try {
    return await (
      window as unknown as { showDirectoryPicker: Picker }
    ).showDirectoryPicker({ id: "tdl-upload", mode: "read" });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") return null;
    throw e;
  }
}

/** Walks a folder (and its sub-folders) for match files, reporting how many entries were checked. */
export async function scanFolder(
  dir: Folder,
  onProgress: (checked: number, found: number) => void,
): Promise<Picked[]> {
  const found: Picked[] = [];
  let checked = 0;
  async function walk(d: DirHandle, depth: number) {
    for await (const entry of d.values()) {
      checked += 1;
      if (checked % 250 === 0) {
        onProgress(checked, found.length);
        await new Promise((r) => setTimeout(r, 0)); // let the page repaint
      }
      if (entry.kind === "directory") {
        if (depth < 4) await walk(entry, depth + 1);
        continue;
      }
      const info = classify(entry.name);
      if (!info) continue;
      const file = await entry.getFile();
      found.push({
        name: entry.name,
        size: file.size,
        day: info.day,
        read: () => entry.getFile(),
      });
    }
  }
  await walk(dir, 0);
  onProgress(checked, found.length);
  return found;
}

/** Match files from an <input type="file"> pick. These can't be re-read if the game changes them. */
export function fromFileList(list: FileList | File[]): Picked[] {
  const out: Picked[] = [];
  for (const f of Array.from(list)) {
    const info = classify(f.name);
    if (info)
      out.push({
        name: f.name,
        size: f.size,
        day: info.day,
        read: async () => f,
      });
  }
  return out;
}

/** True once the folder may be read again (after a refresh Chrome asks with a click). */
export async function mayRead(dir: Folder): Promise<boolean> {
  if ((await dir.queryPermission?.({ mode: "read" })) === "granted")
    return true;
  return (await dir.requestPermission?.({ mode: "read" })) === "granted";
}

// The folder is remembered in IndexedDB so a refreshed page can carry on without asking again.
const DB = "tdl-upload";
const STORE = "folders";

function db(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function rememberFolder(dir: Folder | null): Promise<void> {
  try {
    const d = await db();
    await new Promise<void>((resolve, reject) => {
      const tx = d.transaction(STORE, "readwrite");
      if (dir) tx.objectStore(STORE).put(dir, "last");
      else tx.objectStore(STORE).delete("last");
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  } catch {
    // Remembering is a convenience: without it, the page asks for the folder again.
  }
}

export async function rememberedFolder(): Promise<Folder | null> {
  try {
    const d = await db();
    return await new Promise((resolve) => {
      const req = d.transaction(STORE).objectStore(STORE).get("last");
      req.onsuccess = () => resolve((req.result as Folder | undefined) ?? null);
      req.onerror = () => resolve(null);
    });
  } catch {
    return null;
  }
}
