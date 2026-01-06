// src/renderer/app.tsx
import React from 'react';
import { Homepage } from './Homepage';
import { TopBar } from './TopBar';

export function App() {
  return (
    <>
      <TopBar />
      <Homepage />
    </>
  );
}
