# TypeScript Types and Interfaces

This document describes the TypeScript type definitions used in the NLM front-end application.

## Type Definition Locations

```
src/
├── renderer/
│   ├── types/
│   │   └── LanguageProject.ts   # Main data model interfaces
│   ├── api.ts                   # API-layer types (Language, BibleBookInfo, etc.)
│   └── env.d.ts                 # Global type declarations (Window.api, ImportMetaEnv)
```

---

## Core Data Models

### Language

Represents a target language for translation. This is the **component-layer** interface used in `LanguageProject.ts`.

```typescript
export interface Language {
  id: string;           // Unique identifier
  name: string;         // Display name (e.g., "Bughotu")
  code?: string;        // ISO language code (e.g., "bughotu"), optional
}
```

**Usage**: Identifies the language for a translation project.

For the API-layer `Language` type (returned by `fetchLanguages()`), see [API Layer](./api-layer.md).

---

## Bible Resources

### BibleResource

Top-level Bible resource container.

```typescript
export interface BibleResource {
  id: string;           // Unique identifier
  title: string;        // Bible version title (e.g., "King James Version")
  version: string;      // Version identifier (e.g., "1.0")
  books: BibleBook[];   // Array of Bible books
  available: boolean;   // Whether resource is accessible
}
```

### BibleBook

Individual book of the Bible.

```typescript
export interface BibleBook {
  id: string;               // Unique identifier
  name: string;             // Book name (e.g., "Genesis")
  chapters: BibleChapter[]; // Array of chapters
}
```

### BibleChapter

Chapter within a Bible book.

```typescript
export interface BibleChapter {
  number: number;         // Chapter number (1-based)
  verses: BibleVerse[];   // Array of verses
}
```

### BibleVerse

Individual verse within a chapter.

```typescript
export interface BibleVerse {
  number: number;  // Verse number (1-based)
  text: string;    // Verse content
}
```

**Data Hierarchy**:
```
BibleResource
  └── BibleBook[]
        └── BibleChapter[]
              └── BibleVerse[]
```

---

## Dictionary Resources

The dictionary system uses flat documents — one entry per word. There is no human/AI split in the data model.

### MergedDictionaryEntry

A dictionary entry as stored and returned by the API.

```typescript
export interface MergedDictionaryEntry {
  word: string;
  definition?: string;
  partOfSpeech?: string;
  examples?: string[];
  humanVerified?: boolean;
  createdAt?: string;
  updatedAt?: string;
}
```

> **Note**: This is the component-layer interface in `LanguageProject.ts` (camelCase). The API-layer interface in `api.ts` uses snake_case (`definition`, `part_of_speech`, `human_verified`, etc.) and has `definition` and `examples` as required fields. See [API Layer](./api-layer.md) for the exact API shape.

### DictionaryEntriesResponse

Response from the dictionary API endpoint (component-layer shape).

```typescript
export interface DictionaryEntriesResponse {
  languageCode: string;
  entries: MergedDictionaryEntry[];
  count: number;
}
```

### Legacy Dictionary Types

These types are kept for backward compatibility in `LanguageProject.ts`:

```typescript
export interface Dictionary {
  id: string;
  title: string;
  type: 'human' | 'nlm-generated';
  entries: DictionaryEntry[];
  available: boolean;
}

export interface DictionaryEntry {
  id: string;
  word: string;
  definition: string;
  examples?: string[];
  partOfSpeech?: string;
}
```

---

## Grammar Resources

The grammar system uses flat documents — one entry per category. There is no human/AI split in the data model. Rich vs. simple content is indicated by union types.

### SubcategoryData

Rich subcategory structure (AI-generated content).

```typescript
export interface SubcategoryData {
  name: string;
  content: string;
  examples: string[];
}
```

### ExampleData

Rich example structure (AI-generated content).

```typescript
export interface ExampleData {
  bughotu: string;    // Target language text (legacy field name)
  english: string;    // English translation
  analysis: string;   // Linguistic analysis
}
```

> **Note**: In `api.ts`, `ExampleData` also has `source_text?: string` as a newer language-agnostic alternative to `bughotu`. The `searchFilters.ts` type guards accept both.

### SubcategoryItem / ExampleItem

Union types that handle both simple (human) and rich formats:

```typescript
/** Subcategory can be a simple string (human) or rich object. */
export type SubcategoryItem = string | SubcategoryData;

/** Example can be a simple string (human) or rich object. */
export type ExampleItem = string | ExampleData;
```

### GrammarCategoryVersion

Single version of a grammar category (component-layer model).

```typescript
export interface GrammarCategoryVersion {
  description: string;
  subcategories: SubcategoryItem[];
  notes: string[];
  examples: ExampleItem[];
  aiConfidence?: number;       // AI confidence score (0-1)
  humanVerified: boolean;      // Verification status
  updatedAt?: string;
}
```

### MergedGrammarCategory

Grammar category as stored in the component-layer model (flat, optional fields).

```typescript
export interface MergedGrammarCategory {
  name: string;                        // e.g., "phonology", "syntax"
  description?: string;
  subcategories?: SubcategoryItem[];
  notes?: string[];
  examples?: ExampleItem[];
  humanVerified?: boolean;
  updatedAt?: string;
}
```

> **Note**: The API-layer `MergedGrammarCategory` in `api.ts` has all non-name fields required (not optional). See [API Layer](./api-layer.md) for the exact API shape.

### GrammarCategoriesResponse

Response from the grammar API endpoint (component-layer shape).

```typescript
export interface GrammarCategoriesResponse {
  languageCode: string;
  categories: MergedGrammarCategory[];
  count: number;
}
```

### Legacy Grammar Types

These types are kept for backward compatibility:

```typescript
export interface Grammar {
  id: string;
  title: string;
  type: 'human' | 'nlm-generated';
  sections: GrammarSection[];
  available: boolean;
}

export interface GrammarSection {
  id: string;
  title: string;
  content: string;
  examples?: string[];
}
```

---

## Project Structure Types

### ProjectResources

Container for all resources in a language project.

```typescript
export interface ProjectResources {
  bible: BibleResource | null;               // Bible texts
  dictionary: { available: boolean } | null; // Dictionary availability
  grammar: { available: boolean } | null;    // Grammar/memories availability
}
```

**Note**: Resources are nullable to indicate when a resource type is not yet available for a language. The `grammar` field backs the "Memories" resource card in the UI.

### LanguageProject

Complete project for a language.

```typescript
export interface LanguageProject {
  language: Language;           // Target language
  resources: ProjectResources;  // Available resources
  progress: ProjectProgress;   // Completion progress
}
```

### ProjectProgress

Translation completion percentages.

```typescript
export interface ProjectProgress {
  oldTestamentCompletion: number;   // 0-100 percentage
  newTestamentCompletion: number;   // 0-100 percentage
  overallCompletion: number;        // 0-100 percentage
}
```

---

## Navigation Types

### ResourceType

Union type for resource category selection.

```typescript
export type ResourceType = 'bible' | 'dictionary' | 'memories';
```

**Usage**: Used by `LanguageProject` component to determine which viewer to render:
- `'bible'` → `BibleReader`
- `'dictionary'` → `DictionaryViewer`
- `'memories'` → `MemoriesViewer` (backed by `resources.grammar`)

### NavigationState

Application navigation state (for future use).

```typescript
export interface NavigationState {
  currentView: 'home' | 'project';           // Current screen
  selectedProject: LanguageProject | null;   // Active project
  selectedResource: ResourceType | null;     // Active resource
}
```

**Note**: Currently navigation is managed through component state. This interface is defined for future state management integration.

---

## IPC API Types

### Window API Interface

Exposed to renderer via preload script.

**Location**: `src/main/preload.ts`, `src/renderer/env.d.ts`

```typescript
interface WindowApi {
  // Window controls
  minimize: () => void;
  maximize: () => void;
  close: () => void;

  // File system operations
  selectFolder: () => Promise<string | null>;  // Native folder dialog

  // Opens a URL in the system browser (main process enforces https:// only)
  openExternal: (url: string) => Promise<void>;
}

declare global {
  interface Window {
    api: WindowApi;
  }
}
```

### selectFolder

Opens the native OS folder selection dialog via Electron IPC.

```typescript
// Usage in renderer
const folderPath = await window.api.selectFolder();
if (folderPath) {
  console.log('Selected folder:', folderPath);
}
```

**Returns**: Selected folder path as string, or `null` if user cancelled.

**IPC Channel**: `select-folder` (uses `ipcRenderer.invoke`)

---

## Environment Types

### Vite Environment Variables

**Location**: `src/renderer/env.d.ts`

```typescript
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
```

The `Window`/`api` global interface is also declared in `env.d.ts` (the complete version including `openDevTools`).

**Usage**:
```typescript
const apiUrl = import.meta.env.VITE_API_BASE_URL;
```

---

## Component Prop Types

### TypewriterTextProps

```typescript
interface TypewriterTextProps {
  text: string;        // Text to animate
  speed?: number;      // Milliseconds per character (default: 50)
  sx?: object;         // Style overrides
  [key: string]: any;  // Additional props
}
```

### LanguageProjectProps

```typescript
interface LanguageProjectProps {
  project: LanguageProject;  // Project data
  onBack: () => void;        // Back navigation callback
}
```

### ProjectResourcesProps

```typescript
interface ProjectResourcesProps {
  project: LanguageProject;      // Parent project
  resourceType: ResourceType;    // Resource to display
  onBack: () => void;           // Back navigation callback
}
```

---

## Type Relationships Diagram

```
                    LanguageProject
                          │
           ┌──────────────┼──────────────┐
           ▼              ▼              ▼
       Language    ProjectResources   ProjectProgress
                          │
           ┌──────────────┼─────────────┐
           ▼              ▼             ▼
        bible          dictionary     grammar
    (BibleResource)  ({available})  ({available})
         │
         ▼
      BibleBook
         │
         ▼
     BibleChapter
         │
         ▼
      BibleVerse
```

---

## Type Guards

### Grammar Content Type Guards

Defined in `src/components/searchFilters.ts` and imported by `GrammarViewer` and other components.

```typescript
/** Check if a subcategory is a rich object vs simple string. */
export function isSubcategoryData(item: SubcategoryItem): item is SubcategoryData {
  return typeof item === 'object' && item !== null && 'name' in item;
}

/** Check if an example is a rich object vs simple string. */
export function isExampleData(item: ExampleItem): item is ExampleData {
  return typeof item === 'object' && item !== null && ('source_text' in item || 'bughotu' in item);
}

/** Check if a note is a rich object vs simple string. */
export function isNoteData(item: NoteItem): item is NoteData {
  return typeof item === 'object' && item !== null && 'text' in item;
}
```

**Usage**: These guards determine how to render content and whether editing is allowed:
- Rich content (returns `true`) is displayed as structured, read-only sections
- Simple string content (returns `false`) can be edited inline

### Resource Type Checking (Legacy)

```typescript
function isBibleResource(resource: unknown): resource is BibleResource {
  return (
    resource !== null &&
    typeof resource === 'object' &&
    'books' in resource &&
    'version' in resource
  );
}
```

---

## Best Practices

### Null Handling

Resources can be null. Always check before accessing:

```typescript
if (project.resources.bible) {
  console.log(project.resources.bible.title);
}

// Or with optional chaining
const bookCount = project.resources.bible?.books.length ?? 0;
```

### Type Assertions

Avoid type assertions when possible. Use type guards:

```typescript
// Avoid
const bible = resource as BibleResource;

// Prefer
if (isBibleResource(resource)) {
  console.log(resource.books.length);
}
```

### Exhaustive Type Checking

Use never type for exhaustive checks:

```typescript
function getResourceColor(type: ResourceType): string {
  switch (type) {
    case 'bible':      return '#4CAF50';
    case 'dictionary': return '#2196F3';
    case 'memories':   return '#9C27B0';
    default:
      const _exhaustive: never = type;
      return _exhaustive;
  }
}
```

### Import Types

Use type-only imports when possible:

```typescript
import type { LanguageProject, ResourceType } from '../types/LanguageProject';
```

This helps with tree-shaking and makes intent clear.
