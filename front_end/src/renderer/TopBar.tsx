// TopBar.tsx

import React from 'react';
import { AppBar, Toolbar, IconButton, Menu, MenuItem, Box, Divider } from '@mui/material';
import MenuIcon       from '@mui/icons-material/Menu';
import MinimizeIcon   from '@mui/icons-material/Minimize';
import CropSquareIcon from '@mui/icons-material/CropSquare';
import CloseIcon      from '@mui/icons-material/Close';
import { SettingsDialog } from './components/SettingsDialog';

/**
 * TopBar - Static application menu bar with window controls.
 * Always visible at top of viewport.
 */
export const TopBar: React.FC = () => {
  console.log('[TopBar] render');
  React.useEffect(() => {
    console.log('[TopBar] mounted');
    return () => console.log('[TopBar] unmounted');
  }, []);

  const [anchor, setAnchor] = React.useState<null | HTMLElement>(null);
  const [viewSubmenu, setViewSubmenu] = React.useState<null | HTMLElement>(null);
  const [settingsOpen, setSettingsOpen] = React.useState(false);

  return (
    // The AppBar is marked as draggable so the window can be moved by dragging this area.
    // Avoid applying drag to interactive elements by overriding with 'no-drag'
    <AppBar
      position="fixed"
      color="transparent"
      elevation={0}
      sx={{
        backdropFilter: 'blur(10px)',
        backgroundColor: 'rgba(0,0,0,0.6)',
        '-webkit-app-region': 'drag'  // Enables dragging of window via this element
      }}
    >
      <Toolbar variant="dense">
        {/* Menu button should remain clickable, so we mark it as no-drag */}
        <IconButton
          color="inherit"
          onClick={e => setAnchor(e.currentTarget)}
          size="small"
          sx={{ '-webkit-app-region': 'no-drag' }} // Prevent dragging on clickable buttons
        >
          <MenuIcon />
        </IconButton>
        <Menu anchorEl={anchor} open={!!anchor} onClose={() => setAnchor(null)}>
          <MenuItem onClick={() => setAnchor(null)}>File</MenuItem>
          <MenuItem onClick={() => setAnchor(null)}>Edit</MenuItem>
          <MenuItem onClick={(e) => {
            console.log('[TopBar] View menu clicked');
            setViewSubmenu(e.currentTarget);
            setAnchor(null);
          }}>View</MenuItem>
          <MenuItem onClick={() => setAnchor(null)}>Help</MenuItem>
        </Menu>

        <Menu anchorEl={viewSubmenu} open={!!viewSubmenu} onClose={() => setViewSubmenu(null)}>
          <MenuItem onClick={() => {
            console.log('[TopBar] Show Console Log clicked');
            window.api.openDevTools();
            setViewSubmenu(null);
          }}>Show Console Log</MenuItem>
          <Divider />
          <MenuItem onClick={() => {
            console.log('[TopBar] Settings clicked');
            setSettingsOpen(true);
            setViewSubmenu(null);
          }}>Settings</MenuItem>
        </Menu>
        <Box sx={{ flexGrow: 1 }} />
        {/* Window control buttons are also excluded from dragging */}
        <IconButton
          color="inherit"
          onClick={() => window.api.minimize()}
          size="small"
          sx={{ '-webkit-app-region': 'no-drag' }}
        >
          <MinimizeIcon />
        </IconButton>
        <IconButton
          color="inherit"
          onClick={() => window.api.maximize()}
          size="small"
          sx={{ '-webkit-app-region': 'no-drag' }}
        >
          <CropSquareIcon />
        </IconButton>
        <IconButton
          color="inherit"
          onClick={() => window.api.close()}
          size="small"
          sx={{ '-webkit-app-region': 'no-drag' }}
        >
          <CloseIcon />
        </IconButton>
      </Toolbar>

      <SettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </AppBar>
  );
};
