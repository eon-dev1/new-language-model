# Components

This document maps the top-level component composition and resource-type routing. It is intentionally not a full component reference — for props, state, and behavior, read the component source directly (`src/components/`, `src/renderer/`).

## Composition Tree

```
App
 ├── TopBar        (always visible — window controls, app menu, chat toggle)
 ├── Homepage      (project list, project creation)
 │    └── LanguageProject (when a project is selected)
 │         ├── BibleReader       — selectedResource === 'bible'
 │         ├── DictionaryViewer  — selectedResource === 'dictionary'
 │         └── MemoriesViewer    — selectedResource === 'memories'
 │              ├── NotesTab          (tab: Notes)
 │              ├── GrammarViewer      (tab: Grammar, embeddedMode=true)
 │              └── CorrectionLogTab  (tab: Correction Log)
 └── ChatDrawer    (side panel, always mounted, outside the content area)
```

## Routing

`LanguageProject` selects a viewer based on `ResourceType` (`'bible' | 'dictionary' | 'memories'`, defined in `src/renderer/types/LanguageProject.ts`). There's no router — navigation is plain conditional rendering driven by component state (`onBack`/`onSuccess` callbacks).

## Non-obvious relationship

`GrammarViewer` is not a standalone routed viewer — it only ever renders as one of three tabs inside `MemoriesViewer` (`embeddedMode={true}`), alongside `NotesTab` and `CorrectionLogTab`.
