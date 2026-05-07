# React Components

This document describes the React components used in the NLM front-end application, including their props, behavior, and usage patterns.

## Component Overview

```
src/
├── renderer/
│   ├── app.tsx              # Root application component
│   ├── Homepage.tsx         # Main landing page
│   ├── TopBar.tsx           # Custom window title bar
│   ├── contexts/
│   │   ├── SettingsContext.tsx  # App settings state management
│   │   └── ChatContext.tsx      # Chat drawer state management
│   ├── components/
│   │   └── SettingsDialog.tsx   # Font/size settings dialog
│   └── theme/
│       └── createDynamicTheme.ts # Dynamic MUI theme factory
│
└── components/
    ├── LanguageProject.tsx        # Project overview with resource navigation
    ├── BibleReader.tsx            # Three-view Bible navigation
    ├── DictionaryViewer.tsx       # Dictionary viewer and editor
    ├── GrammarViewer.tsx          # Five-category grammar viewer
    ├── MemoriesViewer.tsx         # Grammar/notes/memories viewer
    ├── ChatDrawer.tsx             # AI chat side panel
    ├── ChatMessage.tsx            # Individual chat message renderer
    ├── ChatSettings.tsx           # Chat provider/model settings panel
    ├── NewProjectDialog.tsx       # Project creation with Bible import
    ├── BaseLanguageDialog.tsx     # Base language selection dialog
    ├── NotesTab.tsx               # Language notes tab (Memories)
    ├── CorrectionLogTab.tsx       # Correction log tab (Memories)
    ├── ToolApprovalCard.tsx       # Tool call approval UI card
    ├── ToolDataPreview.tsx        # Tool result data preview
    ├── VerseSelectionToolbar.tsx  # Multi-verse batch selection toolbar
    ├── VerseTranslationCell.tsx   # Per-verse translation cell
    ├── CopyIconButton.tsx         # Reusable copy-to-clipboard button
    ├── useBatchTranslation.ts     # Batch translation state hook
    ├── searchFilters.ts           # Type guards and search filter helpers
    └── ProjectResources.tsx       # Legacy resource detail viewer (unused)
```

---

## App

**Location**: `src/renderer/app.tsx`

The root application component. Renders a static `TopBar`, the `Homepage` (which handles all navigation internally), and a `ChatDrawer` side panel.

### Behavior

- Subscribes to `ChatContext` to determine chat drawer state
- Adjusts the main content area width when the chat drawer is open
- Renders `TopBar` and `Homepage` inside a width-animated `Box`
- Renders `ChatDrawer` outside that box so it overlaps from the right

### Implementation

```typescript
export function App() {
  const { isOpen, drawerWidth, isMaximized } = useChat();

  const pushWidth = Math.min(drawerWidth, DEFAULT_WIDTH);
  const contentWidth = isOpen && !isMaximized
    ? `calc(100% - ${pushWidth}px)`
    : '100%';

  return (
    <>
      <Box sx={{ width: contentWidth, transition: '...', overflow: 'hidden' }}>
        <TopBar />
        <Homepage />
      </Box>
      <ChatDrawer />
    </>
  );
}
```

---

## Homepage

**Location**: `src/renderer/Homepage.tsx`

The main landing page that displays available language projects and provides project creation functionality.

### State

| State | Type | Description |
|-------|------|-------------|
| `projects` | `Project[]` | List of language projects |
| `loading` | `boolean` | API loading indicator |
| `error` | `string \| null` | Error message if API call fails |
| `selectedProject` | `LanguageProjectType \| null` | Currently selected project |
| `newProjectDialogOpen` | `boolean` | New project dialog visibility |
| `baseLanguageDialogOpen` | `boolean` | Base language dialog visibility |

### Behavior

1. On mount, fetches languages from backend via `fetchLanguages()`
2. Filters out base languages (displays only translation languages)
3. Maps API response to `Project` interface
4. Auto-resumes last selected language via `localStorage`
5. Displays loading spinner while fetching
6. Shows error message if fetch fails
7. Renders project list and action buttons

### Project Interface

```typescript
interface Project {
  id: string;
  name: string;
  languageCode: string;
  totalVerses: number;
  verifiedCount: number;
  verificationProgress: VerificationProgress;  // { old_testament, new_testament, total }
  isBaseLanguage: boolean;
}
```

### UI Layout

```
┌─────────────────────────────────────────────────────┐
│              New Language Model                     │
│   "To whom much has been given, much is required."  │
│                                                     │
│  ┌─────────────────────┐  ┌─────────────────────┐  │
│  │  Continue...        │  │  [Create New Project]│  │
│  │                     │  │                     │  │
│  │  [Language 1]  X.X% │  │  [Choose Base Lang] │  │
│  │  [Language 2]  X.X% │  │                     │  │
│  └─────────────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### Handlers

- **`handleCreateNew`**: Opens `NewProjectDialog`
- **`handleChooseBaseLanguage`**: Opens `BaseLanguageDialog`
- **`handleSelectProject`**: Transforms a flat `Project` into a nested `LanguageProjectType` and sets `selectedProject`, navigating to the `LanguageProject` view

When `selectedProject` is non-null, `Homepage` renders `LanguageProject` instead of the project list.

---

## TopBar

**Location**: `src/renderer/TopBar.tsx`

Custom title bar component for the frameless window. Always visible at the top of the viewport.

### Definition

```typescript
export const TopBar: React.FC = () => { ... };
```

### State

| State | Type | Description |
|-------|------|-------------|
| `anchor` | `HTMLElement \| null` | Hamburger menu anchor element |
| `settingsOpen` | `boolean` | SettingsDialog visibility |

### Features

1. **Window Controls**
   - Minimize button (`window.api.minimize()`)
   - Maximize/Restore button (`window.api.maximize()`)
   - Close button (`window.api.close()`)

2. **Application Menu**
   - Hamburger menu icon opens a flat dropdown: File, Edit, Help, Settings, Support
   - Settings opens `SettingsDialog`
   - Support opens `window.api.openExternal(url)` in the system browser

3. **Chat Toggle**
   - Chat icon button calls `toggleChat()` from `ChatContext`

4. **Draggable Region**
   - AppBar has `-webkit-app-region: drag` for window movement
   - Buttons have `-webkit-app-region: no-drag` to remain clickable

### Styling

```typescript
<AppBar
  position="fixed"
  color="transparent"
  elevation={0}
  sx={{
    backdropFilter: 'blur(10px)',
    backgroundColor: 'rgba(0,0,0,0.6)',
    '-webkit-app-region': 'drag'
  }}
>
```

---

## LanguageProject

**Location**: `src/components/LanguageProject.tsx`

Main project overview component that displays available resources and routes to the appropriate viewer.

### Props

```typescript
interface LanguageProjectProps {
  project: LanguageProjectType;
  onBack: () => void;
}
```

| Prop | Type | Description |
|------|------|-------------|
| `project` | `LanguageProjectType` | The project data to display |
| `onBack` | `() => void` | Callback to return to Homepage |

### State

| State | Type | Description |
|-------|------|-------------|
| `selectedResource` | `ResourceType \| null` | Currently selected resource |

### Resource Configuration

The component defines three resource cards:

| Resource Type | Color | Icon | Title |
|---------------|-------|------|-------|
| `bible` | #4CAF50 (green) | MenuBook | Bible |
| `dictionary` | #2196F3 (blue) | Book | Dictionary |
| `memories` | #FFFFFF (white) | School | Memories |

### Progress Display

Shows three progress bars using `project.progress`:
- Old Testament completion (`oldTestamentCompletion`)
- New Testament completion (`newTestamentCompletion`)
- Overall completion (`overallCompletion`)

### Conditional Rendering

When a resource is selected, the component routes to the appropriate viewer:

```typescript
if (selectedResource === 'bible') {
  return <BibleReader languageCode={...} languageName={...} onBack={handleBackToResources} />;
}

if (selectedResource === 'dictionary') {
  return <DictionaryViewer languageCode={...} languageName={...} onBack={handleBackToResources} />;
}

if (selectedResource === 'memories') {
  return <MemoriesViewer languageCode={...} languageName={...} onBack={handleBackToResources} />;
}
```

### Resource Availability

Resources display differently based on availability:
- **Available**: Full opacity, colored border, clickable
- **Unavailable**: Reduced opacity (0.6), gray border, "Coming Soon" chip

---

## NewProjectDialog

**Location**: `src/components/NewProjectDialog.tsx`

Modal dialog for creating new language projects by importing Bible data.

### Props

```typescript
interface NewProjectDialogProps {
  open: boolean;                          // Dialog visibility
  onClose: () => void;                    // Close handler
  onSuccess: (languageCode: string) => void;  // Success callback
}
```

### Features

1. **Language Name Input**: Text field for the display name (e.g., "Bughotu")
2. **Format Selection**: Radio buttons for USFM or HTML import format
3. **Folder Browser**: Native folder selection via `selectFolder()` IPC
4. **Import Progress**: LinearProgress bar during import
5. **Result Display**: Success/error alerts with verse counts

### Internal State

| State | Type | Description |
|-------|------|-------------|
| `languageName` | `string` | User-entered language name |
| `folderPath` | `string` | Selected folder path |
| `format` | `'usfm' \| 'html'` | Import format selection |
| `importState` | `ImportState` | Import progress tracking |

### Import Flow

```
1. User enters language name
2. User selects format (USFM/HTML)
3. User clicks Browse → selectFolder() IPC call
4. User clicks "Create Project"
5. importBible() or importHtmlBible() API call
6. Success → onSuccess(languageCode) callback
```

---

## BibleReader

**Location**: `src/components/BibleReader.tsx`

Three-view Bible navigation component for reading and verifying translations.

### Props

```typescript
interface BibleReaderProps {
  languageCode: string;  // Target language code
  languageName: string;  // Display name
  onBack: () => void;    // Back navigation callback
}
```

### Navigation Views

| View | Description | Content |
|------|-------------|---------|
| `books` | Book selection grid | 66 book cards organized by testament |
| `chapters` | Chapter selection | Grid of chapter number buttons |
| `verses` | Verse reading | Side-by-side English + translation |

### Internal State

| State | Type | Description |
|-------|------|-------------|
| `view` | `ViewState` | Current navigation view (`'books' \| 'chapters' \| 'verses'`) |
| `selectedBook` | `BibleBookInfo \| null` | Currently selected book |
| `selectedChapter` | `number` | Currently selected chapter |
| `books` | `BibleBookInfo[]` | Loaded book metadata |
| `verses` | `VerseData[]` | Loaded verse content |
| `loading` | `boolean` | Loading indicator |

### Verse Display

Each verse shows:
- Verse number
- English text (source)
- Translated text (target language, may be null for untranslated verses)
- Verification checkbox (`human_verified` status)

### API Integration

```typescript
// Load book list on mount
fetchBibleBooks(languageCode)

// Load chapter content on chapter select
fetchChapterVerses(languageCode, bookCode, chapter)

// Toggle verification checkbox
updateVerseVerification(languageCode, bookCode, chapter, verse, status)
```

---

## DictionaryViewer

**Location**: `src/components/DictionaryViewer.tsx`

Dictionary viewer with flat entry structure — one document per word, no human/AI split.

### Props

```typescript
interface DictionaryViewerProps {
  languageCode: string;  // Target language code
  languageName: string;  // Display name
  onBack: () => void;    // Back navigation callback
}
```

### Navigation Views

| View | Description |
|------|-------------|
| `list` | Searchable word list |
| `detail` | Entry detail with inline editing |

### Features

1. **Search**: Real-time filtering by word or definition
2. **Edit Mode**: Create new entries or update existing (inline `TextField`)
3. **Verification**: Mark entries as human-verified

### Internal State

| State | Type | Description |
|-------|------|-------------|
| `view` | `ViewState` | Current navigation view |
| `selectedEntry` | `MergedDictionaryEntry \| null` | Selected entry |
| `entries` | `MergedDictionaryEntry[]` | Loaded entries |
| `searchQuery` | `string` | Search filter text |
| `isEditing` | `boolean` | Edit mode flag |

### Edit Form Fields

- Word (required)
- Definition (required)
- Part of Speech (optional)
- Examples (optional, newline-separated)

### API Integration

```typescript
fetchDictionaryEntries(languageCode)
saveDictionaryEntry(languageCode, entry)
verifyDictionaryEntry(languageCode, word, humanVerified)
```

---

## GrammarViewer

**Location**: `src/components/GrammarViewer.tsx`

Five-category grammar viewer with unified content structure.

### Props

```typescript
interface GrammarViewerProps {
  languageCode: string;      // Target language code
  languageName: string;      // Display name
  onBack: () => void;        // Back navigation callback
  embeddedMode?: boolean;    // Optional: render in embedded context
}
```

### Grammar Categories

| Category | Icon | Color | Description |
|----------|------|-------|-------------|
| `phonology` | RecordVoiceOver | #E91E63 | Sound system and pronunciation |
| `morphology` | Extension | #9C27B0 | Word structure and formation |
| `syntax` | AccountTree | #2196F3 | Sentence structure and word order |
| `semantics` | Psychology | #00BCD4 | Meaning and interpretation |
| `discourse` | Forum | #4CAF50 | Text-level organization |

### Navigation Views

| View | Description |
|------|-------------|
| `categories` | 5-card grid with category icons |
| `detail` | Category content with subcategories, notes, examples |

### Rich vs Simple Content

Grammar content supports two formats, indicated by type guards from `searchFilters.ts`:

**Simple (string)**: Human-authored inline content
```typescript
subcategories: ['consonants', 'vowels', 'tone']
examples: ['Example sentence here']
```

**Rich (object)**: Structured AI-generated content
```typescript
subcategories: [{
  name: 'consonants',
  content: 'Detailed explanation...',
  examples: ['Example 1', 'Example 2']
}]
examples: [{
  source_text: 'Target text',  // or legacy: bughotu
  english: 'Translation',
  analysis: 'Linguistic analysis'
}]
```

### Type Guards

Defined in `src/components/searchFilters.ts` and imported by `GrammarViewer`:

```typescript
// Check if a subcategory is a rich object vs simple string
isSubcategoryData(item): item is SubcategoryData

// Check if an example is a rich object vs simple string
isExampleData(item): item is ExampleData

// Check if a note is a rich object vs simple string
isNoteData(item): item is NoteData
```

### API Integration

```typescript
fetchGrammarCategories(languageCode)
saveGrammarCategory(languageCode, category, content)
verifyGrammarCategory(languageCode, category, humanVerified)
```

### Edit Restrictions

- Simple string content: Editable (notes and examples as plain text)
- Rich object content: Read-only (displayed with structured formatting)

---

## Animation Patterns

### Framer Motion Usage

The application uses Framer Motion for interactive animations:

```typescript
// Hover and tap effects on resource cards
<motion.div
  whileHover={{ scale: 1.05 }}
  whileTap={{ scale: 0.95 }}
>
  <Paper>...</Paper>
</motion.div>

// Fade-in animation on page load
<motion.div
  initial={{ opacity: 0, y: 50 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.8 }}
>
  <Typography>...</Typography>
</motion.div>
```

---

## Styling Patterns

### Consistent Dark Theme

All components use the dark theme with:
- Background gradients: `linear-gradient(135deg, #1A1A1A, #2D2D2D)`
- Semi-transparent papers: `rgba(255,255,255,0.05)`
- White text with reduced opacity for secondary: `rgba(255,255,255,0.7)`

### Responsive Grid

Resource grids use Material-UI's responsive breakpoints:

```typescript
<Grid container spacing={3}>
  <Grid item xs={12} sm={6} md={4}>
    {/* Resource card */}
  </Grid>
</Grid>
```

| Breakpoint | Grid Columns |
|------------|--------------|
| xs (0-599px) | 1 |
| sm (600-899px) | 2 |
| md (900px+) | 3 |

### Layout Pattern for Scrollable Views

Viewer components use flex layout to keep scrollbars inside content area:
- Outer Box: `height: 100vh`, `overflow: hidden`, `display: flex`, `flexDirection: column`
- Content Paper: `flex: 1`, `minHeight: 0`, `overflowY: auto`
