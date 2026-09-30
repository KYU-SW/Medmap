export type StoredIntakeRecord = {
  id: string;
  createdAt: string;
  transcript: string;
  intake: {
    symptoms: Array<{
      name: string;
      status: "present" | "absent";
      body_site: string | null;
      onset: string | null;
      severity: string | null;
      source_text: string;
    }>;
    medications: string[];
    allergies: string[];
    unrecognized_fragments: string[];
    needs_user_confirmation: boolean;
  };
};

const DATABASE_NAME = "medmap-local";
const DATABASE_VERSION = 1;
const STORE_NAME = "intake-records";

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE_NAME, DATABASE_VERSION);
    request.onupgradeneeded = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(STORE_NAME)) {
        database.createObjectStore(STORE_NAME, { keyPath: "id" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function useStore<T>(
  mode: IDBTransactionMode,
  action: (store: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
  const database = await openDatabase();
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, mode);
    const request = action(transaction.objectStore(STORE_NAME));
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
    transaction.oncomplete = () => database.close();
    transaction.onerror = () => reject(transaction.error);
  });
}

export async function listIntakeRecords(): Promise<StoredIntakeRecord[]> {
  const records = await useStore<StoredIntakeRecord[]>("readonly", (store) => store.getAll());
  return records.sort((left, right) => right.createdAt.localeCompare(left.createdAt));
}

export async function saveIntakeRecord(record: StoredIntakeRecord): Promise<void> {
  await useStore<IDBValidKey>("readwrite", (store) => store.put(record));
}

export async function deleteIntakeRecord(id: string): Promise<void> {
  await useStore<undefined>("readwrite", (store) => store.delete(id));
}
